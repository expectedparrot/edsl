"""Serializable performer routing for workflow work items."""

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from .definition import ParticipantSelector


@dataclass(frozen=True)
class ExecutorSpec:
    kind: str
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in {"human", "llm", "scripted"}:
            raise ValueError(f"unsupported executor kind {self.kind!r}")

    def to_dict(self):
        return {"kind": self.kind, "options": dict(self.options)}

    @classmethod
    def from_dict(cls, data):
        return cls(data["kind"], data.get("options", {}))


def human(**options) -> ExecutorSpec:
    return ExecutorSpec("human", options)


def llm(**options) -> ExecutorSpec:
    return ExecutorSpec("llm", options)


def scripted(**options) -> ExecutorSpec:
    return ExecutorSpec("scripted", options)


@dataclass(frozen=True)
class ExecutionBinding:
    selector: ParticipantSelector
    executor: ExecutorSpec

    def to_dict(self):
        return {"selector": self.selector.to_dict(), "executor": self.executor.to_dict()}


class ExecutionPlan:
    """Ordered, serializable participant-to-executor bindings."""

    def __init__(self, bindings: Sequence[ExecutionBinding] = ()):
        self.bindings = tuple(bindings)

    def bind(self, selector: ParticipantSelector, executor: ExecutorSpec):
        return ExecutionPlan((*self.bindings, ExecutionBinding(selector, executor)))

    def resolve(self, traits: Mapping[str, Any]) -> ExecutorSpec:
        matches = [binding.executor for binding in self.bindings if binding.selector.matches(traits)]
        if len(matches) != 1:
            raise ValueError(f"execution plan expected one binding, found {len(matches)}")
        return matches[0]

    def to_dict(self):
        return {"type": "workflow_execution_plan", "version": 1, "bindings": [b.to_dict() for b in self.bindings]}

    @classmethod
    def from_dict(cls, data):
        if data.get("type") != "workflow_execution_plan" or data.get("version") != 1:
            raise ValueError("unsupported workflow execution plan serialization")
        return cls(tuple(ExecutionBinding(ParticipantSelector.from_dict(b["selector"]), ExecutorSpec.from_dict(b["executor"])) for b in data["bindings"]))


@dataclass(frozen=True)
class MatchingPlan:
    """Deterministically partition eligible participants into fixed-size groups."""

    selector: ParticipantSelector
    size: int
    strategy: str = "sequential"

    def __post_init__(self):
        if self.size < 1 or self.strategy != "sequential":
            raise ValueError("matching requires positive size and sequential strategy")

    def groups(self, participants):
        eligible = sorted(
            (agent for agent in participants if self.selector.matches(agent.traits)),
            key=lambda agent: agent.name or "",
        )
        if len(eligible) % self.size:
            raise ValueError("eligible participant count is not divisible by match size")
        return tuple(tuple(eligible[i : i + self.size]) for i in range(0, len(eligible), self.size))

    def to_dict(self):
        return {"type": "workflow_matching_plan", "version": 1, "selector": self.selector.to_dict(), "size": self.size, "strategy": self.strategy}

    @classmethod
    def from_dict(cls, data):
        if data.get("type") != "workflow_matching_plan" or data.get("version") != 1:
            raise ValueError("unsupported matching plan serialization")
        return cls(ParticipantSelector.from_dict(data["selector"]), data["size"], data.get("strategy", "sequential"))


def match(selector: ParticipantSelector, *, size: int, strategy: str = "sequential") -> MatchingPlan:
    return MatchingPlan(selector, size, strategy)
