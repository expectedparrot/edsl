import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .exceptions import SharedStateAuthoringError, SharedStateRuntimeError
from .store import CLOSE, Operation, Snapshot, StateEvent, WriteResult


class FileStateStore:
    _locks = {}
    _locks_guard = threading.Lock()

    def __init__(self, path):
        self.path = str(path)
        with self._locks_guard:
            self._lock = self._locks.setdefault(
                str(Path(self.path).resolve()), threading.Lock()
            )

    def _lines(self):
        path = Path(self.path)
        if not path.exists():
            return []
        result = []
        with path.open(encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                if line.strip():
                    try:
                        result.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise SharedStateRuntimeError(
                            f"malformed shared-state log line {number} in '{self.path}'"
                        ) from exc
        return result

    def _append(self, record):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(record, separators=(",", ":")) + "\n").encode()
        fd = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)

    def apply(self, operation: Operation) -> WriteResult:
        with self._lock:
            lines = self._lines()
            scope_version = 0
            for row in lines:
                if row.get("scope") != operation.scope:
                    continue
                scope_version += 1
                if (
                    operation.idempotency_key
                    and row.get("idempotency_key") == operation.idempotency_key
                ):
                    return WriteResult(ok=True, version=scope_version)
            if any(
                row.get("scope") == operation.scope and row.get("op") == CLOSE
                for row in lines
            ):
                raise SharedStateRuntimeError(
                    f"scope '{operation.scope}' is closed; no further writes are accepted"
                )
            record = {
                "v": 0,
                "scope": operation.scope,
                "target": operation.target,
                "op": operation.op,
                "args": operation.args,
                "interview": operation.interview_id,
                "idempotency_key": operation.idempotency_key,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            self._append(record)
            version = sum(1 for row in lines if row.get("scope") == operation.scope) + 1
            return WriteResult(ok=True, version=version)

    def close(self, scope: str):
        with self._lock:
            if any(
                row.get("scope") == scope and row.get("op") == CLOSE
                for row in self._lines()
            ):
                return
            self._append(
                {
                    "v": 0,
                    "scope": scope,
                    "op": CLOSE,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            )

    def scopes(self):
        """Return scopes in the order they first appear in the event log."""
        with self._lock:
            lines = self._lines()
        return list(dict.fromkeys(row["scope"] for row in lines if row.get("scope")))

    def history(self, scope=None, target=None):
        """Return typed, storage-independent events from the append-only log."""
        with self._lock:
            lines = self._lines()
        versions = {}
        events = []
        for row in lines:
            event_scope = row.get("scope")
            if not event_scope:
                continue
            versions[event_scope] = versions.get(event_scope, 0) + 1
            event_target = row.get("target")
            if scope is not None and event_scope != scope:
                continue
            if target is not None and event_target != target:
                continue
            timestamp = datetime.fromisoformat(row["ts"])
            events.append(
                StateEvent(
                    scope=event_scope,
                    target=event_target,
                    operation=row["op"],
                    arguments=dict(row.get("args", {})),
                    interview_id=row.get("interview"),
                    timestamp=timestamp,
                    version=versions[event_scope],
                )
            )
        return events

    def read(self, scope: str, config, context=None, at_version=None) -> Snapshot:
        states = {
            name: primitive.initial() for name, primitive in config.primitives.items()
        }
        version = 0
        closed = False
        with self._lock:
            lines = self._lines()
        for row in lines:
            if row.get("scope") != scope:
                continue
            if at_version is not None and version >= at_version:
                break
            version += 1
            if row.get("op") == CLOSE:
                closed = True
                continue
            target = row.get("target")
            if target not in config.primitives:
                raise SharedStateAuthoringError(
                    f"log targets unknown primitive '{target}'"
                )
            primitive = config.primitives[target]
            states[target] = primitive.apply(
                states[target], row["op"], row.get("args", {}), row.get("interview", "")
            )
        if closed:
            for name, primitive in config.primitives.items():
                states[name] = primitive.at_close(states[name])
        return Snapshot(
            state={
                name: config.primitives[name].view(state, closed, context)
                for name, state in states.items()
            },
            version=version,
            closed=closed,
        )

    def to_dict(self):
        return {"type": "file", "path": self.path}

    @classmethod
    def from_dict(cls, data):
        if data.get("type") != "file":
            raise SharedStateAuthoringError(
                f"unknown state store type '{data.get('type')}'"
            )
        return cls(data["path"])
