"""Typed authoring layer that compiles to the durable workflow data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from edsl.sharedstate import StateRead, StateWrite
from edsl.surveys import Survey

from .definition import (
    AllAssigned,
    AllCondition,
    AnswerCondition,
    AnyCondition,
    HumanStep,
    HumanWorkflow,
    NotCondition,
    OutputCountCondition,
    OutputDisagreementCondition,
    OutputMajorityCondition,
    ParticipantSelector,
    CompletionPolicy,
    Quorum,
    StepCompletedCondition,
    WorkflowCondition,
)


def role(name: str) -> ParticipantSelector:
    return ParticipantSelector.role(name)


def quorum(count: int) -> Quorum:
    return Quorum(count)


def all_assigned() -> AllAssigned:
    return AllAssigned()


def all_of(*conditions: WorkflowCondition) -> AllCondition:
    if not conditions:
        raise ValueError("all_of requires at least one condition")
    return AllCondition(tuple(conditions))


def any_of(*conditions: WorkflowCondition) -> AnyCondition:
    if not conditions:
        raise ValueError("any_of requires at least one condition")
    return AnyCondition(tuple(conditions))


def not_(condition: WorkflowCondition) -> NotCondition:
    return NotCondition(condition)


def join_any(*conditions: WorkflowCondition) -> AnyCondition:
    return any_of(*conditions)


def join_all(*conditions: WorkflowCondition) -> AllCondition:
    return all_of(*conditions)


@dataclass(frozen=True)
class Branch:
    then: WorkflowCondition
    otherwise: WorkflowCondition


def if_(condition: WorkflowCondition) -> Branch:
    """Return complementary typed predicates for an if/else branch."""
    return Branch(then=condition, otherwise=not_(condition))


@dataclass(frozen=True)
class StepAnswerRef:
    step_name: str
    question_name: str

    def equals(self, value: Any) -> AnswerCondition:
        return AnswerCondition(self.step_name, self.question_name, value)

    @property
    def expression(self) -> str:
        return (
            "workflow.answers["
            + repr(self.step_name)
            + "]["
            + repr(self.question_name)
            + "]"
        )

    @property
    def template(self) -> str:
        return "{{ " + self.expression + " }}"

    def template_or(self, fallback: "StepAnswerRef | Any") -> str:
        fallback_expression = (
            fallback.expression
            if isinstance(fallback, StepAnswerRef)
            else repr(fallback)
        )
        expression = (
            "workflow.answers.get("
            + repr(self.step_name)
            + ", {}).get("
            + repr(self.question_name)
            + ", "
            + fallback_expression
            + ")"
        )
        return "{{ " + expression + " }}"


@dataclass(frozen=True)
class StepOutputsRef:
    step_name: str
    question_name: str | None = None

    @property
    def template(self) -> str:
        base = "workflow.outputs[" + repr(self.step_name) + "]"
        if self.question_name is None:
            return "{{ " + base + " }}"
        return (
            "{{ "
            + base
            + " | map(attribute="
            + repr(self.question_name)
            + ") | list }}"
        )

    def _question(self) -> str:
        if self.question_name is None:
            raise ValueError("aggregation requires outputs(question), not outputs()")
        return self.question_name

    def count(self, value: Any) -> "OutputCountRef":
        return OutputCountRef(self.step_name, self._question(), value)

    @property
    def has_disagreement(self) -> OutputDisagreementCondition:
        return OutputDisagreementCondition(self.step_name, self._question())

    def majority_is(self, value: Any) -> OutputMajorityCondition:
        return OutputMajorityCondition(self.step_name, self._question(), value)


@dataclass(frozen=True)
class OutputCountRef:
    step_name: str
    question_name: str
    value: Any

    def at_least(self, count: int) -> OutputCountCondition:
        if count < 1:
            raise ValueError("output count threshold must be positive")
        return OutputCountCondition(
            self.step_name, self.question_name, self.value, count
        )


class StepHandle:
    def __init__(self, builder: "Workflow", name: str, survey: Survey):
        self._builder, self.name, self.survey = builder, name, survey

    def answer(self, question: str | Any) -> StepAnswerRef:
        question_name = (
            question
            if isinstance(question, str)
            else getattr(question, "question_name")
        )
        known = {item.question_name for item in self.survey.questions}
        if question_name not in known:
            raise ValueError(
                f"step {self.name!r} has no question {question_name!r}; "
                f"available questions: {sorted(known)}"
            )
        return StepAnswerRef(self.name, question_name)

    def outputs(self, question: str | Any | None = None) -> StepOutputsRef:
        if question is None:
            return StepOutputsRef(self.name)
        answer = self.answer(question)
        return StepOutputsRef(self.name, answer.question_name)

    @property
    def completed(self) -> StepCompletedCondition:
        return StepCompletedCondition(self.name)

    def __repr__(self) -> str:
        return f"StepHandle({self.name!r})"


class Workflow:
    """Incremental builder whose typed handles remove stringly workflow references."""

    def __init__(self, name: str, *, metadata: Mapping[str, Any] | None = None):
        self.name = name
        self.metadata = dict(metadata or {})
        self._steps: list[HumanStep] = []
        self._handles: dict[str, StepHandle] = {}

    def step(
        self,
        name: str,
        survey: Survey,
        *,
        assigned_to: ParticipantSelector | None = None,
        after: StepHandle | Sequence[StepHandle] | None = None,
        when: WorkflowCondition | None = None,
        completion: CompletionPolicy | None = None,
        visible_to: ParticipantSelector | Sequence[ParticipantSelector] | None = None,
        reads: Iterable[StateRead] = (),
        writes: Iterable[StateWrite] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> StepHandle:
        if name in self._handles:
            raise ValueError(f"workflow step {name!r} already exists")
        dependencies = self._dependencies(after)
        if when is not None:
            dependencies.extend(
                dependency
                for dependency in sorted(when.dependencies)
                if dependency not in dependencies
            )
        unknown = set(dependencies) - set(self._handles)
        if unknown:
            raise ValueError(
                f"step {name!r} refers to unknown or later steps: {sorted(unknown)}"
            )
        step = HumanStep(
            name=name,
            survey=survey,
            assignee=assigned_to or ParticipantSelector.all(),
            after=tuple(dependencies),
            enabled_when=when,
            completion=completion or AllAssigned(),
            output_visibility=self._visibility(visible_to),
            reads=tuple(reads),
            writes=tuple(writes),
            metadata=dict(metadata or {}),
        )
        handle = StepHandle(self, name, survey)
        self._steps.append(step)
        self._handles[name] = handle
        return handle

    @staticmethod
    def _visibility(
        visible_to: ParticipantSelector | Sequence[ParticipantSelector] | None,
    ) -> tuple[ParticipantSelector, ...] | None:
        if visible_to is None:
            return None
        selectors = (
            [visible_to]
            if isinstance(visible_to, ParticipantSelector)
            else list(visible_to)
        )
        if not selectors or not all(
            isinstance(selector, ParticipantSelector) for selector in selectors
        ):
            raise TypeError("visible_to accepts role()/ParticipantSelector values")
        return tuple(selectors)

    def compile(self) -> HumanWorkflow:
        return HumanWorkflow(self.name, self._steps, self.metadata)

    @staticmethod
    def _dependencies(
        after: StepHandle | Sequence[StepHandle] | None,
    ) -> list[str]:
        if after is None:
            return []
        handles = [after] if isinstance(after, StepHandle) else list(after)
        if not all(isinstance(item, StepHandle) for item in handles):
            raise TypeError("after accepts StepHandle objects, not step-name strings")
        return [item.name for item in handles]
