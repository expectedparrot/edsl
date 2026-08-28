from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

CLOSE = "__close__"


@dataclass(frozen=True)
class Operation:
    scope: str
    target: str
    op: str
    args: dict[str, Any]
    interview_id: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class WriteResult:
    ok: bool
    version: int


@dataclass(frozen=True)
class Snapshot:
    state: dict[str, Any]
    version: int
    closed: bool


@dataclass(frozen=True)
class StateEvent:
    scope: str
    target: str | None
    operation: str
    arguments: dict[str, Any]
    interview_id: str | None
    timestamp: datetime
    version: int


class StateStore(Protocol):
    def apply(self, operation: Operation) -> WriteResult: ...
    def read(
        self, scope: str, config: Any, context=None, at_version: int | None = None
    ) -> Snapshot: ...
    def close(self, scope: str) -> None: ...
    def scopes(self) -> list[str]: ...
    def history(
        self, scope: str | None = None, target: str | None = None
    ) -> list[StateEvent]: ...
    def to_dict(self) -> dict: ...
