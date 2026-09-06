"""Execution backends for backend-neutral shared-state operations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Protocol, runtime_checkable

from edsl._data_contracts import canonical_data, definition_fingerprint, validate_data

from .dsl_runtime import Runtime, default_runtime
from .exceptions import SharedStateRuntimeError
from .model import ReadOperation, SharedStateMap, StateCondition, WriteOperation


@dataclass(frozen=True)
class AdvisoryWriteOutcome:
    """Advisory acknowledgement; never a transactional state receipt."""

    accepted: bool
    changed: bool | None = None
    observed_version: int | None = None


@dataclass(frozen=True)
class ObservedState:
    read_id: str
    state_id: str
    scope: Any
    target: str
    version: int
    value: Any


@dataclass(frozen=True)
class StateSnapshot:
    state_id: str
    scope: Any
    version: int
    state: dict[str, Any]


@runtime_checkable
class StateBackend(Protocol):
    """The complete execution contract required by EDSL shared state."""

    state_map: SharedStateMap

    def apply(self, operation: WriteOperation) -> AdvisoryWriteOutcome: ...

    def read(
        self, operation: ReadOperation, *, at_sequence: int | None = None
    ) -> ObservedState: ...

    def snapshot(self, scope: Any, *, at_sequence: int | None = None) -> StateSnapshot: ...

    def history(self, *, after_sequence: int = 0) -> list[dict[str, Any]]: ...

    def checkpoint(self) -> int: ...

    def finalize(
        self, condition: StateCondition, scope: Any, *, execution_id: str
    ) -> AdvisoryWriteOutcome: ...


class SQLiteStateBackend:
    """Transactional local backend safe across threads and Python processes.

    SQLite serializes write transactions. Reads are logged in the same database,
    so the event history remains an audit of exactly what each interview observed.
    """

    def __init__(
        self,
        state_map: SharedStateMap,
        path: str | Path,
        *,
        runtime: Runtime | None = None,
        adopt_legacy_definition: bool = False,
    ):
        self.state_map = SharedStateMap.from_dict(state_map.to_dict())
        self.definition_hash = definition_fingerprint(
            self.state_map.definition.to_dict()
        )
        self._adopt_legacy_definition = adopt_legacy_definition
        self.path = str(path)
        self.runtime = runtime or default_runtime()
        for machine in self.state_map.definition.machines.values():
            for capability in machine.algorithms:
                name, version = capability.rsplit("@", 1)
                if (
                    name,
                    int(version),
                ) not in self.runtime.algorithms and capability != "lmsr_prices@1":
                    raise SharedStateRuntimeError(
                        f"unregistered algorithm capability {capability!r}"
                    )
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS state_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    state_id TEXT NOT NULL,
                    scope_canonical TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    kind TEXT NOT NULL CHECK (kind IN ('read', 'write')),
                    idempotency_key TEXT UNIQUE,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS state_events_lookup "
                "ON state_events(state_id, scope_canonical, sequence)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS state_definitions ("
                "state_id TEXT PRIMARY KEY, definition_hash TEXT NOT NULL, "
                "definition TEXT NOT NULL, runtime_version INTEGER NOT NULL, adopted_legacy INTEGER NOT NULL)"
            )
            connection.execute("BEGIN IMMEDIATE")
            stored = connection.execute(
                "SELECT * FROM state_definitions WHERE state_id = ?",
                (self.state_map.state_id,),
            ).fetchone()
            if stored is not None:
                if (
                    stored["definition_hash"] != self.definition_hash
                    or stored["runtime_version"] != 1
                ):
                    raise SharedStateRuntimeError(
                        "state definition changed; use a new state_id or an explicit migration"
                    )
                if (
                    definition_fingerprint(json.loads(stored["definition"]))
                    != stored["definition_hash"]
                ):
                    raise SharedStateRuntimeError(
                        "persisted state definition does not match its fingerprint"
                    )
            else:
                legacy = (
                    connection.execute(
                        "SELECT 1 FROM state_events WHERE state_id = ? LIMIT 1",
                        (self.state_map.state_id,),
                    ).fetchone()
                    is not None
                )
                if legacy and not self._adopt_legacy_definition:
                    raise SharedStateRuntimeError(
                        "legacy state store has no pinned definition; verify its original definition and explicitly set adopt_legacy_definition=True, or use a new state_id"
                    )
                connection.execute(
                    "INSERT INTO state_definitions VALUES (?, ?, ?, 1, ?)",
                    (
                        self.state_map.state_id,
                        self.definition_hash,
                        canonical_data(self.state_map.definition.to_dict()),
                        int(legacy),
                    ),
                )
            connection.commit()

    def _initial_state(self) -> dict[str, Any]:
        return {
            name: self.runtime.initial_state(machine)
            for name, machine in self.state_map.definition.machines.items()
        }

    def _is_closed(
        self,
        connection: sqlite3.Connection,
        state_id: str,
        scope_canonical: str,
        target: str,
        *,
        at_sequence: int | None = None,
    ) -> bool:
        sequence_clause = "AND sequence <= ?" if at_sequence is not None else ""
        parameters: tuple[Any, ...] = (state_id, scope_canonical)
        if at_sequence is not None:
            parameters += (at_sequence,)
        rows = connection.execute(
            f"""
            SELECT payload FROM state_events
            WHERE state_id = ? AND scope_canonical = ? AND kind = 'write'
            {sequence_clause}
            ORDER BY sequence
            """,
            parameters,
        ).fetchall()
        return any(
            event.get("target") == target and event.get("command") == "$close"
            for event in (json.loads(row["payload"]) for row in rows)
        )

    def _materialized(
        self,
        connection: sqlite3.Connection,
        state_id: str,
        scope_canonical: str,
        *,
        at_sequence: int | None = None,
    ) -> tuple[dict[str, Any], int]:
        sequence_clause = "AND sequence <= ?" if at_sequence is not None else ""
        parameters: tuple[Any, ...] = (state_id, scope_canonical)
        if at_sequence is not None:
            parameters += (at_sequence,)
        row = connection.execute(
            f"""
            SELECT payload, version FROM state_events
            WHERE state_id = ? AND scope_canonical = ? AND kind = 'write'
            {sequence_clause}
            ORDER BY sequence DESC LIMIT 1
            """,
            parameters,
        ).fetchone()
        if row is None:
            return self._initial_state(), 0
        return json.loads(row["payload"])["state"], row["version"]

    def apply(self, operation: WriteOperation) -> AdvisoryWriteOutcome:
        self._check_state_id(operation.state_id)
        validate_data(operation.to_dict())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                "SELECT version, payload FROM state_events WHERE idempotency_key = ?",
                (operation.idempotency_key,),
            ).fetchone()
            if duplicate is not None:
                previous = json.loads(duplicate["payload"])
                for name, value in (
                    ("state_id", operation.state_id),
                    ("scope", operation.scope.value),
                    ("target", operation.target),
                    ("command", operation.command),
                    ("inputs", dict(operation.inputs)),
                    ("step_id", operation.step_id),
                    ("execution_id", operation.execution_id),
                ):
                    if canonical_data(previous.get(name)) != canonical_data(value):
                        raise SharedStateRuntimeError(
                            "state idempotency key was reused with different content"
                        )
                if "runtime_context" in previous and canonical_data(
                    previous["runtime_context"]
                ) != canonical_data(dict(operation.runtime_context)):
                    raise SharedStateRuntimeError(
                        "state idempotency key was reused with different runtime context"
                    )
                connection.commit()
                return AdvisoryWriteOutcome(True, None, duplicate["version"])

            state, version = self._materialized(
                connection, operation.state_id, operation.scope.canonical
            )
            try:
                machine = self.state_map.definition.machines[operation.target]
            except KeyError as exc:
                raise SharedStateRuntimeError(
                    f"unknown state target {operation.target!r}"
                ) from exc
            if operation.command == "$close":
                before_target = deepcopy(state[operation.target])
                state[operation.target] = self.runtime.close(
                    machine, state[operation.target]
                )
                changed = state[operation.target] != before_target
            else:
                result = self.runtime.execute(
                    machine,
                    state[operation.target],
                    operation.command,
                    dict(operation.inputs),
                    current=dict(operation.runtime_context),
                )
                state[operation.target] = result.state
                changed = result.event["changed"]
            new_version = version + 1
            event = {
                "format": 1,
                "definition_hash": self.definition_hash,
                "kind": "write",
                "event_id": (
                    f"{operation.state_id}:{operation.scope.canonical}:{new_version}"
                ),
                "state_id": operation.state_id,
                "scope": operation.scope.value,
                "scope_canonical": operation.scope.canonical,
                "version": new_version,
                "target": operation.target,
                "command": operation.command,
                "inputs": dict(operation.inputs),
                "step_id": operation.step_id,
                "execution_id": operation.execution_id,
                "runtime_context": dict(operation.runtime_context),
                "idempotency_key": operation.idempotency_key,
                "changed": changed,
                "state": state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            connection.execute(
                "INSERT INTO state_events "
                "(event_id,state_id,scope_canonical,version,kind,idempotency_key,payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    event["event_id"],
                    event["state_id"],
                    event["scope_canonical"],
                    event["version"],
                    event["kind"],
                    event["idempotency_key"],
                    canonical_data(event),
                ),
            )
            connection.commit()
            return AdvisoryWriteOutcome(True, changed, new_version)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def read(
        self, operation: ReadOperation, *, at_sequence: int | None = None
    ) -> ObservedState:
        self._check_state_id(operation.state_id)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            state, version = self._materialized(
                connection,
                operation.state_id,
                operation.scope.canonical,
                at_sequence=at_sequence,
            )
            try:
                machine = self.state_map.definition.machines[operation.target]
            except KeyError as exc:
                raise SharedStateRuntimeError(
                    f"unknown state target {operation.target!r}"
                ) from exc
            value = self.runtime.render_view(
                machine,
                state[operation.target],
                current=dict(operation.runtime_context),
                closed=self._is_closed(
                    connection,
                    operation.state_id,
                    operation.scope.canonical,
                    operation.target,
                    at_sequence=at_sequence,
                ),
            )
            event = {
                "format": 1,
                "definition_hash": self.definition_hash,
                "kind": "read",
                "event_id": operation.read_id,
                "read_id": operation.read_id,
                "state_id": operation.state_id,
                "scope": operation.scope.value,
                "scope_canonical": operation.scope.canonical,
                "version": version,
                "target": operation.target,
                "step_id": operation.step_id,
                "execution_id": operation.execution_id,
                "value": value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            connection.execute(
                "INSERT INTO state_events "
                "(event_id,state_id,scope_canonical,version,kind,idempotency_key,payload) "
                "VALUES (?,?,?,?,?,NULL,?)",
                (
                    event["event_id"],
                    event["state_id"],
                    event["scope_canonical"],
                    event["version"],
                    event["kind"],
                    canonical_data(event),
                ),
            )
            connection.commit()
            return ObservedState(
                operation.read_id,
                operation.state_id,
                operation.scope.value,
                operation.target,
                version,
                value,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def finalize(
        self, condition: StateCondition, scope: Any, *, execution_id: str
    ) -> AdvisoryWriteOutcome:
        """Atomically apply close effects once when completion is satisfied."""
        from .model import ScopeKey

        self._check_state_id(condition.state_id)
        if (
            definition_fingerprint(condition.definition.to_dict())
            != self.definition_hash
        ):
            raise SharedStateRuntimeError(
                "completion condition uses a different state definition"
            )
        key = ScopeKey(scope)
        idempotency_key = f"{condition.state_id}:{key.canonical}:{condition.target}:close"
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            duplicate = connection.execute(
                "SELECT version FROM state_events WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if duplicate is not None:
                connection.commit()
                return AdvisoryWriteOutcome(True, None, duplicate["version"])
            state, version = self._materialized(
                connection, condition.state_id, key.canonical
            )
            machine = condition.definition.machines[condition.target]
            if not self.runtime.complete(machine, state[condition.target]):
                connection.commit()
                return AdvisoryWriteOutcome(True, False, version)
            before = deepcopy(state[condition.target])
            state[condition.target] = self.runtime.close(machine, before)
            new_version = version + 1
            event = {
                "format": 1,
                "definition_hash": self.definition_hash,
                "kind": "write",
                "event_id": f"{condition.state_id}:{key.canonical}:{new_version}",
                "state_id": condition.state_id,
                "scope": scope,
                "scope_canonical": key.canonical,
                "version": new_version,
                "target": condition.target,
                "command": "$close",
                "inputs": {},
                "step_id": "$finalize",
                "execution_id": execution_id,
                "idempotency_key": idempotency_key,
                "changed": state[condition.target] != before,
                "state": state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            connection.execute(
                "INSERT INTO state_events "
                "(event_id,state_id,scope_canonical,version,kind,idempotency_key,payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    event["event_id"],
                    event["state_id"],
                    event["scope_canonical"],
                    event["version"],
                    event["kind"],
                    event["idempotency_key"],
                    canonical_data(event),
                ),
            )
            connection.commit()
            return AdvisoryWriteOutcome(True, event["changed"], new_version)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def snapshot(
        self, scope: Any, *, at_sequence: int | None = None
    ) -> StateSnapshot:
        from .model import ScopeKey

        self._check_state_id(self.state_map.state_id)
        key = ScopeKey(scope)
        with self._connect() as connection:
            state, version = self._materialized(
                connection,
                self.state_map.state_id,
                key.canonical,
                at_sequence=at_sequence,
            )
        return StateSnapshot(self.state_map.state_id, scope, version, deepcopy(state))

    def history(self, *, after_sequence: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM state_events WHERE state_id = ? AND sequence > ? ORDER BY sequence",
                (self.state_map.state_id, after_sequence),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def checkpoint(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) AS sequence FROM state_events"
            ).fetchone()
        return int(row["sequence"])

    def _check_state_id(self, state_id: str) -> None:
        if state_id != self.state_map.state_id:
            raise SharedStateRuntimeError("operation targets a different state backend")
        if (
            definition_fingerprint(self.state_map.definition.to_dict())
            != self.definition_hash
        ):
            raise SharedStateRuntimeError("state definition was mutated after binding")
