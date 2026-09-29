"""PostgreSQL shared state, isolated by a server-owned execution namespace.

Schema creation is explicit: deployments must run their migration before binding
state. All operations on one state map take its definition row lock, so snapshots,
deduplication, transitions and event sequence allocation share one transaction.
"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    insert,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.engine import Connection

from edsl._data_contracts import canonical_data, definition_fingerprint, validate_data
from .backend import AdvisoryWriteOutcome, ObservedState, StateSnapshot
from .dsl_runtime import default_runtime
from .exceptions import SharedStateRuntimeError
from .model import ScopeKey, SharedStateMap


metadata = MetaData()
definitions = Table(
    "runner_state_definitions",
    metadata,
    Column("namespace", Text, primary_key=True),
    Column("state_id", Text, primary_key=True),
    Column("definition_hash", String(64), nullable=False),
    Column("definition", JSONB, nullable=False),
    Column("runtime_version", Integer, nullable=False),
    Column("sequence", BigInteger, nullable=False),
)
events = Table(
    "runner_state_events",
    metadata,
    Column("namespace", Text, primary_key=True),
    Column("state_id", Text, primary_key=True),
    Column("sequence", BigInteger, primary_key=True),
    Column("scope_canonical", Text, nullable=False),
    Column("kind", String(8), nullable=False),
    Column("event_id", Text, nullable=False),
    Column("idempotency_key", Text),
    Column("payload", JSONB, nullable=False),
    UniqueConstraint("namespace", "state_id", "event_id"),
    UniqueConstraint("namespace", "state_id", "idempotency_key"),
)


checkpoints = Table(
    "runner_state_checkpoints",
    metadata,
    Column("namespace", Text, primary_key=True),
    Column("state_id", Text, primary_key=True),
    Column("checkpoint_key", Text, primary_key=True),
    Column("sequence", BigInteger, nullable=False),
)


class PostgresStateBackend:
    """Bind state to an engine or an existing application transaction.

    An engine gives each operation its own transaction. A Connection must already
    have an active transaction: operations use savepoints, and the caller owns the
    final commit/rollback. This lets an accepted human answer and its state effects
    commit together. Rebind after the caller's transaction ends.
    """

    def __init__(self, state_map, engine, *, namespace, runtime=None):
        if not namespace or not isinstance(namespace, str):
            raise ValueError("a server-owned state namespace is required")
        self.state_map = SharedStateMap.from_dict(state_map.to_dict())
        self.engine = engine
        self._bound_transaction = None
        if isinstance(engine, Connection):
            self._bound_transaction = (
                engine.get_nested_transaction() or engine.get_transaction()
            )
            if self._bound_transaction is None or not self._bound_transaction.is_active:
                raise SharedStateRuntimeError(
                    "a bound connection requires an active caller-owned transaction"
                )
        self.namespace = namespace
        self.runtime = runtime or default_runtime()
        self.definition_hash = definition_fingerprint(
            self.state_map.definition.to_dict()
        )
        for machine in self.state_map.definition.machines.values():
            self.runtime.validate_capabilities(machine)
        self._definition_key = and_(
            definitions.c.namespace == namespace,
            definitions.c.state_id == self.state_map.state_id,
        )
        self._event_key = and_(
            events.c.namespace == namespace,
            events.c.state_id == self.state_map.state_id,
        )
        with self._connection() as conn:
            conn.execute(
                pg_insert(definitions)
                .values(
                    namespace=namespace,
                    state_id=self.state_map.state_id,
                    definition_hash=self.definition_hash,
                    definition=self.state_map.definition.to_dict(),
                    runtime_version=1,
                    sequence=0,
                )
                .on_conflict_do_nothing()
            )
        with self._transaction():
            pass

    @staticmethod
    def create_schema(engine):
        """For explicit development/test setup; production uses migrations."""
        metadata.create_all(engine)

    @contextmanager
    def _connection(self):
        if isinstance(self.engine, Connection):
            current = (
                self.engine.get_nested_transaction() or self.engine.get_transaction()
            )
            if current is not self._bound_transaction or not current.is_active:
                raise SharedStateRuntimeError(
                    "the bound transaction ended or changed; bind a new state backend"
                )
            # A failed operation must not leave partial event/sequence writes even
            # if the application catches its exception and continues the request.
            with self.engine.begin_nested():
                yield self.engine
        else:
            with self.engine.begin() as conn:
                yield conn

    @contextmanager
    def _transaction(self):
        if (
            definition_fingerprint(self.state_map.definition.to_dict())
            != self.definition_hash
        ):
            raise SharedStateRuntimeError("state definition was mutated after binding")
        with self._connection() as conn:
            row = (
                conn.execute(
                    select(definitions).where(self._definition_key).with_for_update()
                )
                .mappings()
                .one()
            )
            if (
                row["definition_hash"] != self.definition_hash
                or row["runtime_version"] != 1
                or definition_fingerprint(row["definition"]) != self.definition_hash
            ):
                raise SharedStateRuntimeError(
                    "state definition changed; use a new state_id or an explicit migration"
                )
            yield conn, row["sequence"]

    def _check_id(self, state_id):
        if state_id != self.state_map.state_id:
            raise SharedStateRuntimeError("operation targets a different state backend")

    def _history(self, conn, *, scope=None, at_sequence=None, after_sequence=0):
        query = select(events.c.payload).where(
            self._event_key, events.c.sequence > after_sequence
        )
        if scope is not None:
            query = query.where(events.c.scope_canonical == scope)
        if at_sequence is not None:
            query = query.where(events.c.sequence <= at_sequence)
        return list(conn.execute(query.order_by(events.c.sequence)).scalars())

    def _materialized(self, conn, scope, at_sequence=None):
        query = select(events.c.payload).where(
            self._event_key, events.c.scope_canonical == scope, events.c.kind == "write"
        )
        if at_sequence is not None:
            query = query.where(events.c.sequence <= at_sequence)
        event = conn.execute(
            query.order_by(events.c.sequence.desc()).limit(1)
        ).scalar_one_or_none()
        if event is not None:
            return deepcopy(event["state"]), event["version"]
        return {
            name: self.runtime.initial_state(machine)
            for name, machine in self.state_map.definition.machines.items()
        }, 0

    def _append(self, conn, sequence, event):
        validate_data(event)
        conn.execute(
            insert(events).values(
                namespace=self.namespace,
                state_id=self.state_map.state_id,
                sequence=sequence + 1,
                scope_canonical=event["scope_canonical"],
                kind=event["kind"],
                event_id=event["event_id"],
                idempotency_key=event.get("idempotency_key"),
                payload=event,
            )
        )
        conn.execute(
            update(definitions)
            .where(self._definition_key)
            .values(sequence=sequence + 1)
        )

    def _duplicate(self, conn, key):
        return conn.execute(
            select(events.c.payload).where(
                self._event_key, events.c.idempotency_key == key
            )
        ).scalar_one_or_none()

    @staticmethod
    def _ack(event, duplicate=False):
        return AdvisoryWriteOutcome(
            True,
            None if duplicate else event["changed"],
            event["version"],
            event["status"],
            event.get("reason_code"),
        )

    def _write_event(self, scope, target, command, state, version, result, **extra):
        return dict(
            format=1,
            definition_hash=self.definition_hash,
            kind="write",
            event_id=f"{self.state_map.state_id}:{scope.canonical}:{version}",
            state_id=self.state_map.state_id,
            scope=scope.value,
            scope_canonical=scope.canonical,
            version=version,
            target=target,
            command=command,
            state=state,
            changed=result.event["changed"],
            status=result.event["status"],
            reason_code=result.event["reason_code"],
            timestamp=datetime.now(timezone.utc).isoformat(),
            **extra,
        )

    def apply(self, operation):
        self._check_id(operation.state_id)
        validate_data(operation.to_dict())
        with self._transaction() as (conn, sequence):
            previous = self._duplicate(conn, operation.idempotency_key)
            if previous is not None:
                expected = dict(
                    state_id=operation.state_id,
                    scope=operation.scope.value,
                    target=operation.target,
                    command=operation.command,
                    inputs=dict(operation.inputs),
                    step_id=operation.step_id,
                    execution_id=operation.execution_id,
                    runtime_context=dict(operation.runtime_context),
                )
                if any(
                    canonical_data(previous.get(k)) != canonical_data(v)
                    for k, v in expected.items()
                ):
                    raise SharedStateRuntimeError(
                        "state idempotency key was reused with different content or runtime context"
                    )
                return self._ack(previous, duplicate=True)
            state, version = self._materialized(conn, operation.scope.canonical)
            machine = self.state_map.definition.machines[operation.target]
            result = (
                self.runtime.close_result(machine, state[operation.target])
                if operation.command == "$close"
                else self.runtime.execute(
                    machine,
                    state[operation.target],
                    operation.command,
                    dict(operation.inputs),
                    current=dict(operation.runtime_context),
                )
            )
            state[operation.target] = result.state
            event = self._write_event(
                operation.scope,
                operation.target,
                operation.command,
                state,
                version + 1,
                result,
                inputs=dict(operation.inputs),
                step_id=operation.step_id,
                execution_id=operation.execution_id,
                runtime_context=dict(operation.runtime_context),
                idempotency_key=operation.idempotency_key,
            )
            self._append(conn, sequence, event)
            return self._ack(event)

    def read(self, operation, *, at_sequence=None):
        """Pin a read ID to its first observation, including across retries."""
        self._check_id(operation.state_id)
        request = dict(
            state_id=operation.state_id,
            scope=operation.scope.value,
            target=operation.target,
            step_id=operation.step_id,
            execution_id=operation.execution_id,
            runtime_context=dict(operation.runtime_context),
            at_sequence=at_sequence,
        )
        validate_data(request)
        with self._transaction() as (conn, sequence):
            previous = conn.execute(
                select(events.c.payload).where(
                    self._event_key, events.c.event_id == operation.read_id
                )
            ).scalar_one_or_none()
            if previous is not None:
                if previous["kind"] != "read" or canonical_data(
                    previous.get("request")
                ) != canonical_data(request):
                    raise SharedStateRuntimeError(
                        "state read ID was reused with different content or runtime context"
                    )
                return ObservedState(
                    operation.read_id,
                    operation.state_id,
                    operation.scope.value,
                    operation.target,
                    previous["version"],
                    previous["value"],
                )
            state, version = self._materialized(
                conn, operation.scope.canonical, at_sequence
            )
            closed = any(
                e.get("target") == operation.target
                and e.get("command") == "$close"
                and e.get("status") != "rejected"
                for e in self._history(
                    conn, scope=operation.scope.canonical, at_sequence=at_sequence
                )
            )
            value = self.runtime.render_view(
                self.state_map.definition.machines[operation.target],
                state[operation.target],
                current=dict(operation.runtime_context),
                closed=closed,
            )
            event = dict(
                format=1,
                definition_hash=self.definition_hash,
                kind="read",
                event_id=operation.read_id,
                read_id=operation.read_id,
                state_id=operation.state_id,
                scope=operation.scope.value,
                scope_canonical=operation.scope.canonical,
                version=version,
                target=operation.target,
                step_id=operation.step_id,
                execution_id=operation.execution_id,
                request=request,
                value=value,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._append(conn, sequence, event)
            return ObservedState(
                operation.read_id,
                operation.state_id,
                operation.scope.value,
                operation.target,
                version,
                value,
            )

    def finalize(self, condition, scope, *, execution_id):
        self._check_id(condition.state_id)
        if (
            definition_fingerprint(condition.definition.to_dict())
            != self.definition_hash
        ):
            raise SharedStateRuntimeError(
                "completion condition uses a different state definition"
            )
        key = ScopeKey(scope)
        close_key = f"{condition.state_id}:{key.canonical}:{condition.target}:close"
        rejected_key = f"{close_key}:rejected:{canonical_data(execution_id)}"
        with self._transaction() as (conn, sequence):
            previous = self._duplicate(conn, rejected_key) or self._duplicate(
                conn, close_key
            )
            if previous is not None:
                return self._ack(previous, duplicate=True)
            state, version = self._materialized(conn, key.canonical)
            machine = condition.definition.machines[condition.target]
            if not self.runtime.complete(machine, state[condition.target]):
                return AdvisoryWriteOutcome(True, False, version, "noop")
            result = self.runtime.close_result(machine, state[condition.target])
            state[condition.target] = result.state
            event = self._write_event(
                key,
                condition.target,
                "$close",
                state,
                version + 1,
                result,
                inputs={},
                step_id="$finalize",
                execution_id=execution_id,
                idempotency_key=(
                    rejected_key if result.event["status"] == "rejected" else close_key
                ),
            )
            self._append(conn, sequence, event)
            return self._ack(event)

    def snapshot(self, scope, *, at_sequence=None):
        with self._transaction() as (conn, _):
            state, version = self._materialized(
                conn, ScopeKey(scope).canonical, at_sequence
            )
            return StateSnapshot(self.state_map.state_id, scope, version, state)

    def is_finalized(self, scope, target):
        """Report a committed close, including one whose acknowledgement was lost."""
        with self._transaction() as (conn, _):
            return any(
                event.get("target") == target
                and event.get("command") == "$close"
                and event.get("status") != "rejected"
                for event in self._history(conn, scope=ScopeKey(scope).canonical)
            )

    def checkpoint(self):
        with self._transaction() as (_, sequence):
            return sequence

    def pin_checkpoint(self, key):
        """Atomically pin a named boundary; all processes reuse its first value."""
        validate_data(key)
        encoded = canonical_data(key)
        with self._transaction() as (conn, sequence):
            previous = conn.execute(
                select(checkpoints.c.sequence).where(
                    checkpoints.c.namespace == self.namespace,
                    checkpoints.c.state_id == self.state_map.state_id,
                    checkpoints.c.checkpoint_key == encoded,
                )
            ).scalar_one_or_none()
            if previous is not None:
                return previous
            conn.execute(
                insert(checkpoints).values(
                    namespace=self.namespace,
                    state_id=self.state_map.state_id,
                    checkpoint_key=encoded,
                    sequence=sequence,
                )
            )
            return sequence

    def history(self, *, after_sequence=0):
        with self._transaction() as (conn, _):
            return self._history(conn, after_sequence=after_sequence)
