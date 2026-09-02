"""Typed authoring layer that compiles to the durable workflow data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from edsl.sharedstate import StateRead, StateWrite
from edsl.surveys import Survey

from .definition import (
    AllAssigned,
    AllCondition,
    AnswerCondition,
    AnyCondition,
    ChanceCondition,
    DerivedValue,
    ExpressionCondition,
    HumanStep,
    HumanWorkflow,
    NotCondition,
    OutputCountCondition,
    OutputDisagreementCondition,
    OutputMajorityCondition,
    OutputRangeCondition,
    ParticipantSelector,
    CompletionPolicy,
    Quorum,
    RepeatBlock,
    RepeatIteration,
    StepCompletedCondition,
    WorkflowCondition,
    WorkflowExpression,
)


def role(name: str) -> ParticipantSelector:
    return ParticipantSelector.role(name)


def quorum(count: int) -> Quorum:
    return Quorum(count)


def all_assigned() -> AllAssigned:
    return AllAssigned()


def chance(probability: float, *, key: str) -> ChanceCondition:
    """Continue with ``probability``, stably sampled once per workflow instance/key."""
    return ChanceCondition(probability, key)


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


def choose(condition: WorkflowExpression, then: Any, otherwise: Any) -> WorkflowExpression:
    """A serializable piecewise expression."""
    return WorkflowExpression("if_else", (condition, then, otherwise))


def _expression(value: Any) -> WorkflowExpression:
    return value if isinstance(value, WorkflowExpression) else WorkflowExpression("literal", (value,))


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
    def value(self) -> WorkflowExpression:
        return WorkflowExpression("step_answer", options={"step_name": self.step_name, "question_name": self.question_name})

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

    def optional(self, default: Any = ()) -> str:
        """Render outputs as an empty/default value when an optional step was skipped."""
        base = "workflow.outputs.get(" + repr(self.step_name) + ", " + repr(list(default)) + ")"
        if self.question_name is None:
            return "{{ " + base + " }}"
        return "{{ " + base + " | map(attribute=" + repr(self.question_name) + ") | list }}"

    def count(self, value: Any) -> "OutputCountRef":
        return OutputCountRef(self.step_name, self._question(), value)

    @property
    def has_disagreement(self) -> OutputDisagreementCondition:
        return OutputDisagreementCondition(self.step_name, self._question())

    def majority_is(self, value: Any) -> OutputMajorityCondition:
        return OutputMajorityCondition(self.step_name, self._question(), value)

    def range_at_most(self, maximum: float) -> OutputRangeCondition:
        return OutputRangeCondition(self.step_name, self._question(), maximum)

    @property
    def value(self) -> WorkflowExpression:
        return WorkflowExpression(
            "step_outputs",
            options={
                "step_name": self.step_name,
                "question_name": self._question(),
            },
        )

    def mean(self) -> WorkflowExpression:
        return WorkflowExpression("mean", (self.value,))

    def median(self) -> WorkflowExpression:
        return WorkflowExpression("median", (self.value,))

    def minimum(self) -> WorkflowExpression:
        return WorkflowExpression("minimum", (self.value,))

    def maximum(self) -> WorkflowExpression:
        return WorkflowExpression("maximum", (self.value,))

    def range(self) -> WorkflowExpression:
        return WorkflowExpression("range", (self.value,))


@dataclass(frozen=True)
class DerivedFieldRef:
    derived_name: str
    field_name: str
    dependencies: frozenset[str]

    @property
    def expression(self) -> WorkflowExpression:
        return WorkflowExpression(
            "derived_ref",
            options={
                "name": self.derived_name,
                "field": self.field_name,
                "dependencies": sorted(self.dependencies),
            },
        )

    @property
    def template(self) -> str:
        return (
            "{{ workflow.derived["
            + repr(self.derived_name)
            + "]["
            + repr(self.field_name)
            + "] }}"
        )

    def at_most(self, value: Any) -> ExpressionCondition:
        return self.expression.at_most(value)

    def at_least(self, value: Any) -> ExpressionCondition:
        return self.expression.at_least(value)

    def equals(self, value: Any) -> ExpressionCondition:
        return self.expression.equals(value)

    def for_participant(self) -> str:
        return "{{ workflow.derived[" + repr(self.derived_name) + "][" + repr(self.field_name) + "][participant.name] }}"


@dataclass(frozen=True)
class DerivedValuesRef:
    definition: DerivedValue

    def field(self, name: str) -> DerivedFieldRef:
        if name not in self.definition.fields:
            raise KeyError(f"unknown derived field {name!r}")
        return DerivedFieldRef(self.definition.name, name, self.definition.dependencies)


@dataclass(frozen=True)
class StepSubmissionsRef:
    """Identity-preserving submissions for scoring and personalized routing."""

    step_name: str

    @property
    def expression(self) -> str:
        return "workflow.submissions[" + repr(self.step_name) + "]"

    @property
    def template(self) -> str:
        return "{{ " + self.expression + " }}"

    @property
    def value(self) -> WorkflowExpression:
        return WorkflowExpression("step_submissions", options={"step_name": self.step_name})

    def payoff_matrix(
        self,
        question: str,
        matrix: Mapping[str, Sequence[float]],
        *,
        action_codes: Mapping[Any, str] | None = None,
    ) -> WorkflowExpression:
        """Compute two-player payoffs using explicit, stable action codes.

        ``action_codes`` maps submitted answers to the one-character codes used by
        the matrix keys.  It is optional for compatibility; without it, the
        historical first-character convention is used.
        """
        options: dict[str, Any] = {
            "question_name": question,
            "matrix": {str(key): list(value) for key, value in matrix.items()},
        }
        if action_codes is not None:
            codes = {str(action): str(code) for action, code in action_codes.items()}
            if not codes:
                raise ValueError("action_codes cannot be empty")
            if any(len(code) != 1 for code in codes.values()):
                raise ValueError("payoff-matrix action codes must be one character")
            if len(set(codes.values())) != len(codes):
                raise ValueError("payoff-matrix action codes must be unique")
            options["action_codes"] = codes
        return WorkflowExpression("payoff_matrix", (self.value,), options)

    def closest_to(self, question: str, target: WorkflowExpression, *, ties: str = "all") -> WorkflowExpression:
        if ties not in {"all", "first"}:
            raise ValueError("ties must be 'all' or 'first'")
        return WorkflowExpression("argmin_by", (self.value, target), {"question_name": question, "ties": ties})


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
    def submissions(self) -> StepSubmissionsRef:
        return StepSubmissionsRef(self.name)

    @property
    def completed(self) -> StepCompletedCondition:
        return StepCompletedCondition(self.name)

    def __repr__(self) -> str:
        return f"StepHandle({self.name!r})"


@dataclass(frozen=True)
class RepeatResult:
    block: RepeatBlock
    tails: tuple[StepHandle, ...]

    @property
    def final_tail(self) -> StepHandle:
        return self.tails[-1]


class RepeatIterationBuilder:
    """Authoring context for one materialized iteration of a repeat block."""

    def __init__(
        self,
        workflow: "Workflow",
        block_name: str,
        number: int,
        previous_tail: StepHandle | None,
        continuation: WorkflowCondition | None,
    ):
        self.workflow = workflow
        self.block_name = block_name
        self.number = number
        self.previous_tail = previous_tail
        self.continuation = continuation
        self.handles: list[StepHandle] = []
        self.until: WorkflowCondition | None = None

    def step(self, name: str, survey: Survey, **kwargs: Any) -> StepHandle:
        after = kwargs.pop("after", None)
        when = kwargs.pop("when", None)
        if not self.handles and self.previous_tail is not None:
            after = after or self.previous_tail
            if self.continuation is not None:
                when = (
                    self.continuation
                    if when is None
                    else all_of(self.continuation, when)
                )
        metadata = {
            **dict(kwargs.pop("metadata", {}) or {}),
            "repeat": {"name": self.block_name, "iteration": self.number},
        }
        handle = self.workflow.step(
            f"{name}-{self.number}",
            survey,
            after=after,
            when=when,
            metadata=metadata,
            **kwargs,
        )
        self.handles.append(handle)
        return handle

    def stop_when(self, condition: WorkflowCondition) -> None:
        self.until = condition


RepeatFactory = Callable[[RepeatIterationBuilder], None]


class Workflow:
    """Incremental builder whose typed handles remove stringly workflow references."""

    def __init__(self, name: str, *, metadata: Mapping[str, Any] | None = None):
        self.name = name
        self.metadata = dict(metadata or {})
        self._steps: list[HumanStep] = []
        self._handles: dict[str, StepHandle] = {}
        self._derived_values: list[DerivedValue] = []
        self._repeat_blocks: list[RepeatBlock] = []

    def derive(self, name: str, **fields: WorkflowExpression) -> DerivedValuesRef:
        if any(item.name == name for item in self._derived_values):
            raise ValueError(f"derived value {name!r} already exists")
        if not all(isinstance(value, WorkflowExpression) for value in fields.values()):
            raise TypeError("derived fields must be serializable workflow expressions")
        definition = DerivedValue(name, fields)
        self._derived_values.append(definition)
        return DerivedValuesRef(definition)

    def repeat(
        self,
        name: str,
        *,
        max_iterations: int,
        build: RepeatFactory,
        min_iterations: int = 1,
        after: StepHandle | None = None,
    ) -> RepeatResult:
        """Materialize a bounded loop whose compiled form contains only data."""
        if max_iterations < min_iterations or min_iterations < 1:
            raise ValueError("repeat bounds must satisfy 1 <= min <= max")
        if any(item.name == name for item in self._repeat_blocks):
            raise ValueError(f"repeat block {name!r} already exists")
        previous_tail = after
        previous_until: WorkflowCondition | None = None
        iterations: list[RepeatIteration] = []
        tails: list[StepHandle] = []
        for number in range(1, max_iterations + 1):
            continuation = (
                not_(previous_until)
                if previous_until is not None and number > min_iterations
                else None
            )
            iteration = RepeatIterationBuilder(
                self, name, number, previous_tail, continuation
            )
            build(iteration)
            if not iteration.handles:
                raise ValueError("repeat iteration must define at least one step")
            if number < max_iterations and iteration.until is None:
                raise ValueError("repeat iteration must define a stop condition")
            previous_tail = iteration.handles[-1]
            previous_until = iteration.until
            tails.append(previous_tail)
            iterations.append(
                RepeatIteration(
                    number,
                    tuple(handle.name for handle in iteration.handles),
                    iteration.until,
                )
            )
        block = RepeatBlock(name, min_iterations, max_iterations, tuple(iterations))
        self._repeat_blocks.append(block)
        return RepeatResult(block, tuple(tails))

    def step(
        self,
        name: str,
        survey: Survey,
        *,
        assigned_to: ParticipantSelector | None = None,
        after: StepHandle | Sequence[StepHandle] | None = None,
        after_settled: StepHandle | Sequence[StepHandle] | None = None,
        when: WorkflowCondition | None = None,
        completion: CompletionPolicy | None = None,
        visible_to: ParticipantSelector | Sequence[ParticipantSelector] | None = None,
        reads: Iterable[StateRead] = (),
        writes: Iterable[StateWrite] = (),
        metadata: Mapping[str, Any] | None = None,
        answer_bounds: Mapping[str | Any, tuple[Any, Any]] | None = None,
    ) -> StepHandle:
        if name in self._handles:
            raise ValueError(f"workflow step {name!r} already exists")
        dependencies = self._dependencies(after)
        settled_dependencies = self._dependencies(after_settled)
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
            settled_after=tuple(settled_dependencies),
            enabled_when=when,
            completion=completion or AllAssigned(),
            output_visibility=self._visibility(visible_to),
            reads=tuple(reads),
            writes=tuple(writes),
            metadata=dict(metadata or {}),
            answer_bounds={
                (key if isinstance(key, str) else key.question_name): (_expression(low), _expression(high))
                for key, (low, high) in (answer_bounds or {}).items()
            },
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
        return HumanWorkflow(
            self.name,
            self._steps,
            self.metadata,
            self._derived_values,
            self._repeat_blocks,
        )

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
