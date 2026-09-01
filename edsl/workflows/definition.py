"""Serializable definitions for durable, respondent-driven workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from edsl.sharedstate import StateRead, StateWrite, step_from_dict, step_to_dict
from edsl.surveys import Survey


class WorkflowCondition:
    """Serializable predicate over workflow steps and their submissions."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def dependencies(self) -> frozenset[str]:
        raise NotImplementedError


@dataclass(frozen=True)
class AnswerCondition(WorkflowCondition):
    """Enable a step when a predecessor submitted the expected answer."""

    step_name: str
    question_name: str
    equals: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "answer_equals",
            "step_name": self.step_name,
            "question_name": self.question_name,
            "equals": self.equals,
        }

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset({self.step_name})

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AnswerCondition":
        if data.get("type") != "answer_equals":
            raise ValueError("unsupported workflow answer condition")
        return cls(data["step_name"], data["question_name"], data["equals"])


@dataclass(frozen=True)
class StepCompletedCondition(WorkflowCondition):
    step_name: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": "step_completed", "step_name": self.step_name}

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset({self.step_name})


@dataclass(frozen=True)
class AllCondition(WorkflowCondition):
    conditions: tuple[WorkflowCondition, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "all",
            "conditions": [item.to_dict() for item in self.conditions],
        }

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset().union(*(item.dependencies for item in self.conditions))


@dataclass(frozen=True)
class AnyCondition(WorkflowCondition):
    conditions: tuple[WorkflowCondition, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "any",
            "conditions": [item.to_dict() for item in self.conditions],
        }

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset().union(*(item.dependencies for item in self.conditions))


@dataclass(frozen=True)
class NotCondition(WorkflowCondition):
    condition: WorkflowCondition

    def to_dict(self) -> dict[str, Any]:
        return {"type": "not", "condition": self.condition.to_dict()}

    @property
    def dependencies(self) -> frozenset[str]:
        return self.condition.dependencies


@dataclass(frozen=True)
class OutputCountCondition(WorkflowCondition):
    step_name: str
    question_name: str
    value: Any
    minimum: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "output_count",
            "step_name": self.step_name,
            "question_name": self.question_name,
            "value": self.value,
            "minimum": self.minimum,
        }

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset({self.step_name})


@dataclass(frozen=True)
class OutputDisagreementCondition(WorkflowCondition):
    step_name: str
    question_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "output_disagreement",
            "step_name": self.step_name,
            "question_name": self.question_name,
        }

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset({self.step_name})


@dataclass(frozen=True)
class OutputMajorityCondition(WorkflowCondition):
    step_name: str
    question_name: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "output_majority",
            "step_name": self.step_name,
            "question_name": self.question_name,
            "value": self.value,
        }

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset({self.step_name})


def condition_from_dict(data: Mapping[str, Any]) -> WorkflowCondition:
    kind = data.get("type")
    if kind == "answer_equals":
        return AnswerCondition.from_dict(data)
    if kind == "step_completed":
        return StepCompletedCondition(data["step_name"])
    if kind == "all":
        return AllCondition(
            tuple(condition_from_dict(item) for item in data["conditions"])
        )
    if kind == "any":
        return AnyCondition(
            tuple(condition_from_dict(item) for item in data["conditions"])
        )
    if kind == "not":
        return NotCondition(condition_from_dict(data["condition"]))
    if kind == "output_count":
        return OutputCountCondition(
            data["step_name"], data["question_name"], data["value"], data["minimum"]
        )
    if kind == "output_disagreement":
        return OutputDisagreementCondition(data["step_name"], data["question_name"])
    if kind == "output_majority":
        return OutputMajorityCondition(
            data["step_name"], data["question_name"], data["value"]
        )
    raise ValueError(f"unsupported workflow condition {kind!r}")


class CompletionPolicy:
    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class AllAssigned(CompletionPolicy):
    def to_dict(self) -> dict[str, Any]:
        return {"type": "all_assigned"}


@dataclass(frozen=True)
class Quorum(CompletionPolicy):
    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("quorum count must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "quorum", "count": self.count}


def completion_from_dict(data: Mapping[str, Any] | None) -> CompletionPolicy:
    if data is None or data.get("type") == "all_assigned":
        return AllAssigned()
    if data.get("type") == "quorum":
        return Quorum(data["count"])
    raise ValueError(f"unsupported completion policy {data.get('type')!r}")


@dataclass(frozen=True)
class ParticipantSelector:
    """Select participants by exact trait values (or select everyone)."""

    traits: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def all(cls) -> "ParticipantSelector":
        return cls()

    @classmethod
    def role(cls, role: str) -> "ParticipantSelector":
        return cls({"role": role})

    def matches(self, traits: Mapping[str, Any]) -> bool:
        return all(traits.get(key) == value for key, value in self.traits.items())

    def to_dict(self) -> dict[str, Any]:
        return {"traits": dict(self.traits)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ParticipantSelector":
        return cls(data.get("traits", {}))


@dataclass(frozen=True)
class HumanStep:
    """A survey task that becomes ready after all named predecessor steps finish."""

    name: str
    survey: Survey
    assignee: ParticipantSelector = field(default_factory=ParticipantSelector.all)
    after: tuple[str, ...] = ()
    enabled_when: WorkflowCondition | None = None
    completion: CompletionPolicy = field(default_factory=AllAssigned)
    output_visibility: tuple[ParticipantSelector, ...] | None = None
    reads: tuple[StateRead, ...] = ()
    writes: tuple[StateWrite, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("workflow step name must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "survey": self.survey.to_dict(),
            "assignee": self.assignee.to_dict(),
            "after": list(self.after),
            "enabled_when": (
                self.enabled_when.to_dict() if self.enabled_when is not None else None
            ),
            "completion": self.completion.to_dict(),
            "output_visibility": (
                [selector.to_dict() for selector in self.output_visibility]
                if self.output_visibility is not None
                else None
            ),
            "reads": [step_to_dict(item) for item in self.reads],
            "writes": [step_to_dict(item) for item in self.writes],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanStep":
        return cls(
            name=data["name"],
            survey=Survey.from_dict(dict(data["survey"])),
            assignee=ParticipantSelector.from_dict(data.get("assignee", {})),
            after=tuple(data.get("after", ())),
            enabled_when=(
                condition_from_dict(data["enabled_when"])
                if data.get("enabled_when") is not None
                else None
            ),
            completion=completion_from_dict(data.get("completion")),
            output_visibility=(
                tuple(
                    ParticipantSelector.from_dict(selector)
                    for selector in data["output_visibility"]
                )
                if data.get("output_visibility") is not None
                else None
            ),
            reads=tuple(step_from_dict(item) for item in data.get("reads", ())),
            writes=tuple(step_from_dict(item) for item in data.get("writes", ())),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class HumanWorkflow:
    """An immutable workflow graph whose edges express response dependencies."""

    name: str
    steps: tuple[HumanStep, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        steps: Sequence[HumanStep],
        metadata: Mapping[str, Any] | None = None,
    ):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "steps", tuple(steps))
        object.__setattr__(self, "metadata", dict(metadata or {}))
        self._validate()

    def _validate(self) -> None:
        names = [step.name for step in self.steps]
        if not self.name or not self.name.strip():
            raise ValueError("workflow name must be non-empty")
        if not names or len(names) != len(set(names)):
            raise ValueError("workflow steps must have unique, non-empty names")
        known: set[str] = set()
        for step in self.steps:
            missing = set(step.after) - known
            if missing:
                raise ValueError(
                    f"step {step.name!r} depends on unknown or later steps: {sorted(missing)}"
                )
            if step.enabled_when is not None:
                missing_conditions = set(step.enabled_when.dependencies) - set(
                    step.after
                )
                if missing_conditions:
                    raise ValueError(
                        f"step {step.name!r} condition references steps not listed in after: "
                        f"{sorted(missing_conditions)}"
                    )
            self._validate_output_visibility(step, known)
            known.add(step.name)

    def _validate_output_visibility(self, consumer: HumanStep, known: set[str]) -> None:
        """Reject typed references that the consumer's role can never read."""
        import json

        serialized_survey = json.dumps(consumer.survey.to_dict())
        for source_name in known:
            source = self.step(source_name)
            if source.output_visibility is None:
                continue
            markers = (
                f"workflow.answers['{source_name}']",
                f'workflow.answers["{source_name}"]',
                f"workflow.outputs['{source_name}']",
                f'workflow.outputs["{source_name}"]',
            )
            if not any(marker in serialized_survey for marker in markers):
                continue
            if not any(
                all(
                    consumer.assignee.traits.get(key) == value
                    for key, value in selector.traits.items()
                )
                for selector in source.output_visibility
            ):
                raise ValueError(
                    f"step {consumer.name!r} references outputs from {source_name!r}, "
                    "but its assignee is not included in that step's output visibility"
                )

    def step(self, name: str) -> HumanStep:
        return next(step for step in self.steps if step.name == name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "human_workflow",
            "version": 1,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanWorkflow":
        if data.get("type") != "human_workflow" or data.get("version") != 1:
            raise ValueError("unsupported human workflow serialization")
        return cls(
            data["name"],
            [HumanStep.from_dict(step) for step in data["steps"]],
            data.get("metadata", {}),
        )
