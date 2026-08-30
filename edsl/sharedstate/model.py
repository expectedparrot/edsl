"""Backend-neutral shared-state definitions and operation envelopes.

These objects describe *what* should happen.  They contain no file paths,
database connections, locks, or transaction machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping
from uuid import uuid4

from .dsl import Machine
from .exceptions import SharedStateAuthoringError
from .refs import AnswerRef, ContextRef


def canonical_json(value: Any) -> str:
    """Return a stable encoding suitable for identity and idempotency keys."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass(frozen=True)
class ScopeKey:
    """A structured scope key; unlike concatenated strings it cannot collide."""

    value: Any

    @property
    def canonical(self) -> str:
        return canonical_json(self.value)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScopeKey":
        return cls(data["value"])


@dataclass(frozen=True)
class SharedState:
    """A serializable collection of named state machines."""

    machines: Mapping[str, Machine]
    definition_version: int = 1

    def __init__(self, **machines: Machine):
        if not machines:
            raise SharedStateAuthoringError("SharedState requires at least one machine")
        for name, machine in machines.items():
            if not name.isidentifier() or name.startswith("_"):
                raise SharedStateAuthoringError(f"invalid machine name {name!r}")
            if not isinstance(machine, Machine):
                raise SharedStateAuthoringError(
                    f"{name!r} must be a Machine, not {type(machine).__name__}"
                )
            machine.validate()
        object.__setattr__(self, "machines", dict(machines))
        object.__setattr__(self, "definition_version", 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "shared_state_definition",
            "version": self.definition_version,
            "machines": {name: machine.to_dict() for name, machine in self.machines.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SharedState":
        if data.get("type") != "shared_state_definition" or data.get("version") != 1:
            raise SharedStateAuthoringError("unsupported SharedState serialization")
        return cls(
            **{
                name: Machine.from_dict(machine)
                for name, machine in data["machines"].items()
            }
        )


def _stable_id(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()[:24]


@dataclass(frozen=True)
class StateStep:
    state_id: str
    definition: SharedState
    scope: Any
    target: str
    step_id: str


@dataclass(frozen=True)
class StateWrite(StateStep):
    command: str
    inputs: Mapping[str, Any]

    @classmethod
    def create(
        cls,
        *,
        state_id: str,
        definition: SharedState,
        scope: Any,
        target: str,
        command: str,
        inputs: Mapping[str, Any],
        step_id: str | None = None,
    ) -> "StateWrite":
        return cls(
            state_id=state_id,
            definition=definition,
            scope=scope,
            target=target,
            step_id=step_id or str(uuid4()),
            command=command,
            inputs=dict(inputs),
        )


@dataclass(frozen=True)
class StateRead(StateStep):
    pass


@dataclass(frozen=True)
class StateCondition:
    """A typed reference to a machine's declarative completion predicate."""

    state_id: str
    definition: SharedState
    scope: Any
    target: str

    def to_dict(self) -> dict[str, Any]:
        """Return a portable reference to the predicate and its state target."""
        return {
            "type": "state_condition",
            "version": 1,
            "state_id": self.state_id,
            "definition": self.definition.to_dict(),
            "scope": _encode_ref(self.scope),
            "target": self.target,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StateCondition":
        if data.get("type") != "state_condition" or data.get("version") != 1:
            raise SharedStateAuthoringError("unsupported state condition format")
        return cls(
            state_id=data["state_id"],
            definition=SharedState.from_dict(data["definition"]),
            scope=_decode_ref(data["scope"]),
            target=data["target"],
        )


@dataclass(frozen=True)
class WriteOperation:
    state_id: str
    scope: ScopeKey
    target: str
    command: str
    inputs: Mapping[str, Any]
    step_id: str
    execution_id: str
    runtime_context: Mapping[str, Any]
    idempotency_key: str


@dataclass(frozen=True)
class ReadOperation:
    state_id: str
    scope: ScopeKey
    target: str
    step_id: str
    execution_id: str
    runtime_context: Mapping[str, Any]
    read_id: str = field(default_factory=lambda: str(uuid4()))


class MachineHandle:
    def __init__(self, owner: "ScopedState", name: str, machine: Machine):
        self.owner, self.name, self.machine = owner, name, machine

    def command(self, name: str, **inputs: Any) -> StateWrite:
        if name not in self.machine.commands:
            raise SharedStateAuthoringError(
                f"{self.machine.name} has no command {name!r}"
            )
        expected, supplied = set(self.machine.commands[name].inputs), set(inputs)
        if expected != supplied:
            raise SharedStateAuthoringError(
                f"{self.machine.name}.{name} input mismatch; "
                f"missing={sorted(expected-supplied)}, extra={sorted(supplied-expected)}"
            )
        return StateWrite.create(
            state_id=self.owner.state_id,
            definition=self.owner.definition,
            scope=self.owner.scope,
            target=self.name,
            command=name,
            inputs=inputs,
        )

    def read(self, *, step_id: str | None = None) -> StateRead:
        return StateRead(
            state_id=self.owner.state_id,
            definition=self.owner.definition,
            scope=self.owner.scope,
            target=self.name,
            step_id=step_id or str(uuid4()),
        )

    def is_complete(self) -> StateCondition:
        if self.machine.complete_when is None:
            raise SharedStateAuthoringError(
                f"{self.machine.name} has no complete_when expression"
            )
        return StateCondition(
            state_id=self.owner.state_id,
            definition=self.owner.definition,
            scope=self.owner.scope,
            target=self.name,
        )

    def close(self, *, step_id: str | None = None) -> StateWrite:
        """Create an explicit, idempotent close transition."""
        return StateWrite.create(
            state_id=self.owner.state_id,
            definition=self.owner.definition,
            scope=self.owner.scope,
            target=self.name,
            command="$close",
            inputs={},
            step_id=step_id,
        )

    def __getattr__(self, name: str):
        if name in self.machine.commands:
            return lambda **inputs: self.command(name, **inputs)
        raise AttributeError(name)


class ScopedState:
    def __init__(self, owner: "SharedStateMap", scope: Any):
        self.definition = owner.definition
        self.state_id = owner.state_id
        self.scope = scope

    def __getattr__(self, name: str) -> MachineHandle:
        try:
            machine = self.definition.machines[name]
        except KeyError as exc:
            raise AttributeError(name) from exc
        return MachineHandle(self, name, machine)


class SharedStateMap:
    """Names a durable state resource whose entries are selected by scope."""

    def __init__(self, definition: SharedState, *, state_id: str | None = None):
        if not isinstance(definition, SharedState):
            raise SharedStateAuthoringError("definition must be a SharedState")
        if state_id is not None and (not isinstance(state_id, str) or not state_id.strip()):
            raise SharedStateAuthoringError("state_id must be a non-empty string")
        self.definition = definition
        self.state_id = state_id or str(uuid4())

    def by(self, scope: Any) -> ScopedState:
        return ScopedState(self, scope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "shared_state_map",
            "version": 1,
            "state_id": self.state_id,
            "definition": self.definition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SharedStateMap":
        return cls(
            SharedState.from_dict(data["definition"]), state_id=data["state_id"]
        )


def _encode_ref(value: Any) -> Any:
    if isinstance(value, AnswerRef):
        return {"$answer": value.question_name}
    if isinstance(value, ContextRef):
        return {"$current": list(value.path)}
    if isinstance(value, Mapping):
        return {key: _encode_ref(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_encode_ref(item) for item in value]
    return value


def resolve(value: Any, context) -> Any:
    if isinstance(value, AnswerRef):
        return value.resolve(context.answers)
    if isinstance(value, ContextRef):
        return value.resolve(context)
    if isinstance(value, Mapping):
        return {key: resolve(item, context) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [resolve(item, context) for item in value]
    return value


def resolve_write(step: StateWrite, context) -> WriteOperation:
    scope = ScopeKey(resolve(step.scope, context))
    inputs = resolve(step.inputs, context)
    key_payload = {
        "state_id": step.state_id,
        "scope": scope.value,
        "step_id": step.step_id,
        "execution_id": context.interview_id,
        "inputs": inputs,
    }
    return WriteOperation(
        state_id=step.state_id,
        scope=scope,
        target=step.target,
        command=step.command,
        inputs=inputs,
        step_id=step.step_id,
        execution_id=context.interview_id,
        runtime_context=_runtime_context(context),
        idempotency_key=_stable_id(key_payload),
    )


def resolve_read(step: StateRead, context) -> ReadOperation:
    return ReadOperation(
        state_id=step.state_id,
        scope=ScopeKey(resolve(step.scope, context)),
        target=step.target,
        step_id=step.step_id,
        execution_id=context.interview_id,
        runtime_context=_runtime_context(context),
    )


def _runtime_context(context) -> dict[str, Any]:
    """Expose declared execution capabilities to the pure DSL runtime.

    Agent and run values are flattened because machine expressions use
    ``current("name")``, ``current("role")``, and ``current("round")``.  Reserved
    execution identifiers cannot be overridden by traits.
    """

    values = dict(context.agent_traits or {})
    values.update(context.run_context or {})
    values["interview_id"] = context.interview_id
    values["execution_id"] = context.interview_id
    return values


def step_to_dict(step: StateStep) -> dict[str, Any]:
    result = {
        "kind": "write" if isinstance(step, StateWrite) else "read",
        "state_id": step.state_id,
        "definition": step.definition.to_dict(),
        "scope": _encode_ref(step.scope),
        "target": step.target,
        "step_id": step.step_id,
    }
    if isinstance(step, StateWrite):
        result |= {"command": step.command, "inputs": _encode_ref(step.inputs)}
    return result


def _decode_ref(value: Any) -> Any:
    if isinstance(value, Mapping) and set(value) == {"$answer"}:
        return AnswerRef(value["$answer"])
    if isinstance(value, Mapping) and set(value) == {"$current"}:
        return ContextRef(tuple(value["$current"]))
    if isinstance(value, Mapping):
        return {key: _decode_ref(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_ref(item) for item in value]
    return value


def step_from_dict(data: Mapping[str, Any]) -> StateStep:
    common = dict(
        state_id=data["state_id"],
        definition=SharedState.from_dict(data["definition"]),
        scope=_decode_ref(data["scope"]),
        target=data["target"],
        step_id=data["step_id"],
    )
    if data["kind"] == "read":
        return StateRead(**common)
    if data["kind"] == "write":
        return StateWrite(
            **common,
            command=data["command"],
            inputs=_decode_ref(data["inputs"]),
        )
    raise SharedStateAuthoringError(f"unknown state step kind {data['kind']!r}")
