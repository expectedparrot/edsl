"""Serializable definitions for durable, respondent-driven workflows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from edsl._data_contracts import check_arity, symbolic_bool, validate_data
from edsl.sharedstate import StateRead, StateWrite, step_from_dict, step_to_dict
from edsl.surveys import Survey


def _encode_expression_value(value: Any) -> Any:
    if isinstance(value, WorkflowExpression):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_encode_expression_value(item) for item in value]
    if isinstance(value, list):
        return [_encode_expression_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode_expression_value(item) for key, item in value.items()}
    return value


def _decode_expression_value(value: Any) -> Any:
    if isinstance(value, Mapping) and value.get("type") == "workflow_expression":
        return WorkflowExpression.from_dict(value)
    if isinstance(value, list):
        return tuple(_decode_expression_value(item) for item in value)
    if isinstance(value, Mapping):
        return {key: _decode_expression_value(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class WorkflowExpression:
    """A data-only expression evaluated by the workflow coordinator."""

    op: str
    args: tuple[Any, ...] = ()
    options: Mapping[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return symbolic_bool()

    def __post_init__(self) -> None:
        allowed = {
            "step_outputs",
            "step_answer",
            "derived_ref",
            "mean",
            "median",
            "minimum",
            "maximum",
            "range",
            "sum",
            "count_value",
            "all_equal",
            "order_statistic",
            "absolute",
            "add",
            "subtract",
            "multiply",
            "divide",
            "at_most",
            "at_least",
            "equals",
            "if_else",
            "step_submissions",
            "payoff_matrix",
            "argmin_by",
            "literal",
            "submission_value",
            "map_submissions",
            "seeded_uniform",
            "seeded_integer",
            "lookup",
            "join_submissions",
            "joined_value",
            "map_joined_submissions",
            "parameter",
            "get_item",
        }
        if self.op not in allowed:
            raise ValueError(f"unsupported workflow expression operator {self.op!r}")
        zero = {
            "step_outputs",
            "step_answer",
            "derived_ref",
            "step_submissions",
            "submission_value",
            "joined_value",
            "parameter",
        }
        unary = {
            "mean",
            "median",
            "minimum",
            "maximum",
            "range",
            "sum",
            "all_equal",
            "order_statistic",
            "absolute",
            "payoff_matrix",
            "literal",
            "lookup",
        }
        if self.op == "join_submissions":
            check_arity(self.op, self.args, 1)
            if len(self.options.get("names", ())) != len(self.args):
                raise ValueError("join_submissions requires a name for each source")
        else:
            arity = (
                0
                if self.op in zero
                else 1 if self.op in unary else 3 if self.op == "if_else" else 2
            )
            check_arity(self.op, self.args, arity, arity)
        required = {
            "step_outputs": {"step_name", "question_name"},
            "step_answer": {"step_name", "question_name"},
            "step_submissions": {"step_name"},
            "derived_ref": {"name", "field", "dependencies"},
            "order_statistic": {"rank", "direction"},
            "payoff_matrix": {"question_name", "matrix"},
            "argmin_by": {"question_name", "ties"},
            "map_submissions": {"question_name"},
            "joined_value": {"source", "question_name"},
            "parameter": {"name"},
            "lookup": {"mapping"},
        }.get(self.op, set())
        if not required <= self.options.keys():
            raise ValueError(f"{self.op} requires options {sorted(required)}")
        validate_data(self.to_dict(), path=f"workflow expression {self.op}")
        if self.op == "payoff_matrix" and "action_codes" in self.options:
            codes = self.options["action_codes"]
            if not isinstance(codes, Mapping) or not codes:
                raise ValueError("payoff-matrix action_codes must be a nonempty mapping")
            if any(not isinstance(code, str) or len(code) != 1 for code in codes.values()):
                raise ValueError("payoff-matrix action codes must be one character")
            if len(set(codes.values())) != len(codes):
                raise ValueError("payoff-matrix action codes must be unique")
        if self.op == "seeded_uniform":
            low, high = self.args
            if (
                isinstance(low, bool)
                or isinstance(high, bool)
                or not isinstance(low, (int, float))
                or not isinstance(high, (int, float))
                or low >= high
            ):
                raise ValueError("seeded_uniform requires numeric low < high")
            if not self.options.get("key"):
                raise ValueError("seeded_uniform key must be non-empty")
        if self.op == "seeded_integer":
            low, high = self.args
            if (
                isinstance(low, bool)
                or isinstance(high, bool)
                or not isinstance(low, int)
                or not isinstance(high, int)
                or low > high
            ):
                raise ValueError("seeded_integer requires integer low <= high")
            if not self.options.get("key"):
                raise ValueError("seeded_integer key must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "workflow_expression",
            "op": self.op,
            "args": _encode_expression_value(self.args),
            "options": _encode_expression_value(dict(self.options)),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkflowExpression":
        if data.get("type") != "workflow_expression":
            raise ValueError("unsupported workflow expression")
        return cls(
            data["op"],
            tuple(_decode_expression_value(item) for item in data.get("args", ())),
            {
                key: _decode_expression_value(value)
                for key, value in data.get("options", {}).items()
            },
        )

    @property
    def dependencies(self) -> frozenset[str]:
        dependencies: set[str] = set(self.options.get("dependencies", ()))
        if self.op in {"step_outputs", "step_answer", "step_submissions"}:
            dependencies.add(str(self.options["step_name"]))

        def collect(value):
            if isinstance(value, WorkflowExpression):
                dependencies.update(value.dependencies)
            elif isinstance(value, (tuple, list)):
                for item in value:
                    collect(item)
            elif isinstance(value, Mapping):
                for item in value.values():
                    collect(item)

        for value in (*self.args, *self.options.values()):
            collect(value)
        return frozenset(dependencies)

    def _binary(self, op: str, other: Any) -> "WorkflowExpression":
        return WorkflowExpression(op, (self, other))

    def __add__(self, other: Any) -> "WorkflowExpression":
        return self._binary("add", other)

    def __sub__(self, other: Any) -> "WorkflowExpression":
        return self._binary("subtract", other)

    def __mul__(self, other: Any) -> "WorkflowExpression":
        return self._binary("multiply", other)

    def __truediv__(self, other: Any) -> "WorkflowExpression":
        return self._binary("divide", other)

    def __radd__(self, other: Any) -> "WorkflowExpression":
        return WorkflowExpression("add", (other, self))

    def __rsub__(self, other: Any) -> "WorkflowExpression":
        return WorkflowExpression("subtract", (other, self))

    def __rmul__(self, other: Any) -> "WorkflowExpression":
        return WorkflowExpression("multiply", (other, self))

    def __rtruediv__(self, other: Any) -> "WorkflowExpression":
        return WorkflowExpression("divide", (other, self))

    def at_most(self, value: Any) -> "ExpressionCondition":
        return ExpressionCondition(self.compare_at_most(value))

    def compare_at_most(self, value: Any) -> "WorkflowExpression":
        return self._binary("at_most", value)

    def at_least(self, value: Any) -> "ExpressionCondition":
        return ExpressionCondition(self.compare_at_least(value))

    def compare_at_least(self, value: Any) -> "WorkflowExpression":
        return self._binary("at_least", value)

    def equals(self, value: Any) -> "ExpressionCondition":
        return ExpressionCondition(self._binary("equals", value))

    def compare_equals(self, value: Any) -> "WorkflowExpression":
        return self._binary("equals", value)

    def absolute(self) -> "WorkflowExpression":
        return WorkflowExpression("absolute", (self,))

    def item(self, key: Any) -> "WorkflowExpression":
        """Select a key or index from a serialized mapping or sequence value."""
        return WorkflowExpression("get_item", (self, key))


class WorkflowCondition:
    """Serializable predicate over workflow steps and their submissions."""

    def __bool__(self) -> bool:
        return symbolic_bool()

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @property
    def dependencies(self) -> frozenset[str]:
        raise NotImplementedError


@dataclass(frozen=True)
class ExpressionCondition(WorkflowCondition):
    expression: WorkflowExpression

    def to_dict(self) -> dict[str, Any]:
        return {"type": "expression", "expression": self.expression.to_dict()}

    @property
    def dependencies(self) -> frozenset[str]:
        return self.expression.dependencies


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
class ChanceCondition(WorkflowCondition):
    """A stable per-instance Bernoulli decision used for probabilistic routing."""

    probability: float
    key: str

    def __post_init__(self) -> None:
        if not 0 <= self.probability <= 1:
            raise ValueError("chance probability must be between 0 and 1")
        if not self.key:
            raise ValueError("chance key must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "chance", "probability": self.probability, "key": self.key}

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset()


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


@dataclass(frozen=True)
class OutputRangeCondition(WorkflowCondition):
    """True when the numeric range of a step's answers is within a threshold."""

    step_name: str
    question_name: str
    maximum: float

    def __post_init__(self) -> None:
        if self.maximum < 0:
            raise ValueError("maximum output range must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "output_range",
            "step_name": self.step_name,
            "question_name": self.question_name,
            "maximum": self.maximum,
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
    if kind == "chance":
        return ChanceCondition(data["probability"], data["key"])
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
    if kind == "output_range":
        return OutputRangeCondition(
            data["step_name"], data["question_name"], data["maximum"]
        )
    if kind == "expression":
        return ExpressionCondition(WorkflowExpression.from_dict(data["expression"]))
    raise ValueError(f"unsupported workflow condition {kind!r}")


@dataclass(frozen=True)
class DerivedValue:
    """Named, serializable values computed from workflow evidence."""

    name: str
    fields: Mapping[str, WorkflowExpression]

    def __post_init__(self) -> None:
        if not self.name or not self.fields:
            raise ValueError("derived values require a name and at least one field")

    @property
    def dependencies(self) -> frozenset[str]:
        return frozenset().union(
            *(expression.dependencies for expression in self.fields.values())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "fields": {
                name: expression.to_dict() for name, expression in self.fields.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DerivedValue":
        return cls(
            data["name"],
            {
                name: WorkflowExpression.from_dict(expression)
                for name, expression in data["fields"].items()
            },
        )


@dataclass(frozen=True)
class RepeatIteration:
    number: int
    step_names: tuple[str, ...]
    until: WorkflowCondition | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "step_names": list(self.step_names),
            "until": self.until.to_dict() if self.until is not None else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RepeatIteration":
        return cls(
            data["number"],
            tuple(data["step_names"]),
            condition_from_dict(data["until"]) if data.get("until") else None,
        )


@dataclass(frozen=True)
class RepeatBlock:
    """A bounded loop whose materialized iterations contain no Python callbacks."""

    name: str
    min_iterations: int
    max_iterations: int
    iterations: tuple[RepeatIteration, ...]

    def __post_init__(self) -> None:
        if not self.name or self.min_iterations < 1:
            raise ValueError("repeat block requires a name and positive minimum")
        if self.max_iterations < self.min_iterations:
            raise ValueError("repeat maximum must be at least its minimum")
        if len(self.iterations) != self.max_iterations:
            raise ValueError("repeat block must materialize every bounded iteration")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "min_iterations": self.min_iterations,
            "max_iterations": self.max_iterations,
            "iterations": [item.to_dict() for item in self.iterations],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RepeatBlock":
        return cls(
            data["name"],
            data["min_iterations"],
            data["max_iterations"],
            tuple(RepeatIteration.from_dict(item) for item in data["iterations"]),
        )


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
        if (
            isinstance(self.count, bool)
            or not isinstance(self.count, int)
            or self.count < 1
        ):
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
class ParticipantSubmissionView:
    """A participant-relative projection of one step's submissions."""

    name: str
    source_step: str
    own_key: str = "self_response"
    others_key: str = "peer_responses"

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("participant submission view name must be non-empty")
        if not self.source_step or not self.source_step.strip():
            raise ValueError(
                "participant submission view source step must be non-empty"
            )
        if not self.own_key or not self.others_key or self.own_key == self.others_key:
            raise ValueError(
                "participant submission view keys must be non-empty and distinct"
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "source_step": self.source_step,
            "own_key": self.own_key,
            "others_key": self.others_key,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ParticipantSubmissionView":
        return cls(
            data["name"],
            data["source_step"],
            data.get("own_key", "self_response"),
            data.get("others_key", "peer_responses"),
        )


@dataclass(frozen=True)
class HumanStep:
    """A survey task that becomes ready after all named predecessor steps finish."""

    name: str
    survey: Survey
    assignee: ParticipantSelector = field(default_factory=ParticipantSelector.all)
    after: tuple[str, ...] = ()
    settled_after: tuple[str, ...] = ()
    enabled_when: WorkflowCondition | None = None
    completion: CompletionPolicy = field(default_factory=AllAssigned)
    output_visibility: tuple[ParticipantSelector, ...] | None = None
    participant_submission_views: tuple[ParticipantSubmissionView, ...] = ()
    reads: tuple[StateRead, ...] = ()
    writes: tuple[StateWrite, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    answer_bounds: Mapping[str, tuple[WorkflowExpression | None, WorkflowExpression | None]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("workflow step name must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "survey": self.survey.to_dict(),
            "assignee": self.assignee.to_dict(),
            "after": list(self.after),
            "settled_after": list(self.settled_after),
            "enabled_when": (
                self.enabled_when.to_dict() if self.enabled_when is not None else None
            ),
            "completion": self.completion.to_dict(),
            "output_visibility": (
                [selector.to_dict() for selector in self.output_visibility]
                if self.output_visibility is not None
                else None
            ),
            "participant_submission_views": [
                view.to_dict() for view in self.participant_submission_views
            ],
            "reads": [step_to_dict(item) for item in self.reads],
            "writes": [step_to_dict(item) for item in self.writes],
            "metadata": dict(self.metadata),
            "answer_bounds": {
                name: [
                    low.to_dict() if low is not None else None,
                    high.to_dict() if high is not None else None,
                ]
                for name, (low, high) in self.answer_bounds.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanStep":
        return cls(
            name=data["name"],
            survey=Survey.from_dict(dict(data["survey"])),
            assignee=ParticipantSelector.from_dict(data.get("assignee", {})),
            after=tuple(data.get("after", ())),
            settled_after=tuple(data.get("settled_after", ())),
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
            participant_submission_views=tuple(
                ParticipantSubmissionView.from_dict(view)
                for view in data.get("participant_submission_views", ())
            ),
            reads=tuple(step_from_dict(item) for item in data.get("reads", ())),
            writes=tuple(step_from_dict(item) for item in data.get("writes", ())),
            metadata=data.get("metadata", {}),
            answer_bounds={
                name: (
                    WorkflowExpression.from_dict(bounds[0]) if bounds[0] else None,
                    WorkflowExpression.from_dict(bounds[1]) if bounds[1] else None,
                )
                for name, bounds in data.get("answer_bounds", {}).items()
            },
        )


@dataclass(frozen=True)
class HumanWorkflow:
    """A detached workflow snapshot whose edges express response dependencies."""

    name: str
    steps: tuple[HumanStep, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    derived_values: tuple[DerivedValue, ...] = ()
    repeat_blocks: tuple[RepeatBlock, ...] = ()

    def __init__(
        self,
        name: str,
        steps: Sequence[HumanStep],
        metadata: Mapping[str, Any] | None = None,
        derived_values: Sequence[DerivedValue] = (),
        repeat_blocks: Sequence[RepeatBlock] = (),
    ):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "steps", deepcopy(tuple(steps)))
        object.__setattr__(self, "metadata", deepcopy(dict(metadata or {})))
        object.__setattr__(self, "derived_values", deepcopy(tuple(derived_values)))
        object.__setattr__(self, "repeat_blocks", deepcopy(tuple(repeat_blocks)))
        self._validate()

    def _validate(self) -> None:
        validate_data(self.to_dict(), path="workflow definition")
        names = [step.name for step in self.steps]
        derived_names = [item.name for item in self.derived_values]
        repeat_names = [item.name for item in self.repeat_blocks]
        if not self.name or not self.name.strip():
            raise ValueError("workflow name must be non-empty")
        if not names or len(names) != len(set(names)):
            raise ValueError("workflow steps must have unique, non-empty names")
        if len(derived_names) != len(set(derived_names)):
            raise ValueError("workflow derived values must have unique names")
        if len(repeat_names) != len(set(repeat_names)):
            raise ValueError("workflow repeat blocks must have unique names")
        repeated_steps: set[str] = set()
        for block in self.repeat_blocks:
            for expected_number, iteration in enumerate(block.iterations, start=1):
                if iteration.number != expected_number:
                    raise ValueError("repeat iteration numbers must be consecutive")
                for step_name in iteration.step_names:
                    if step_name not in names:
                        raise ValueError(
                            f"repeat block {block.name!r} references unknown step "
                            f"{step_name!r}"
                        )
                    if step_name in repeated_steps:
                        raise ValueError(f"step {step_name!r} belongs to two repeats")
                    repeated_steps.add(step_name)
        known_derived: dict[str, DerivedValue] = {}
        for derived in self.derived_values:
            for expression in derived.fields.values():
                for node in self._expression_nodes(expression):
                    if node.op != "derived_ref":
                        continue
                    source = known_derived.get(node.options.get("name"))
                    if source is None:
                        raise ValueError(
                            f"derived value {derived.name!r} references unknown or "
                            "later derived value"
                        )
                    if node.options.get("field") not in source.fields:
                        raise ValueError(
                            f"derived value {derived.name!r} references unknown field"
                        )
                    if (
                        frozenset(node.options.get("dependencies", ()))
                        != source.dependencies
                    ):
                        raise ValueError(
                            "derived reference dependencies do not match source"
                        )
            known_derived[derived.name] = derived
        known: set[str] = set()
        for step in self.steps:
            missing = (set(step.after) | set(step.settled_after)) - known
            if missing:
                raise ValueError(
                    f"step {step.name!r} depends on unknown or later steps: {sorted(missing)}"
                )
            view_names = [view.name for view in step.participant_submission_views]
            if len(view_names) != len(set(view_names)):
                raise ValueError(
                    f"step {step.name!r} participant submission view names must be unique"
                )
            view_sources = {
                view.source_step for view in step.participant_submission_views
            }
            if view_sources - set((*step.after, *step.settled_after)):
                raise ValueError(
                    f"step {step.name!r} participant submission views must reference dependencies"
                )
            if step.enabled_when is not None:
                missing_conditions = set(step.enabled_when.dependencies) - set(
                    (*step.after, *step.settled_after)
                )
                if missing_conditions:
                    raise ValueError(
                        f"step {step.name!r} condition references steps not listed in after: "
                        f"{sorted(missing_conditions)}"
                    )
            question_names = {q.question_name for q in step.survey.questions}
            if set(step.answer_bounds) - question_names:
                raise ValueError(f"step {step.name!r} has bounds for an unknown question")
            bound_dependencies = {
                dependency
                for bounds in step.answer_bounds.values()
                for expression in bounds
                if expression is not None
                for dependency in expression.dependencies
            }
            if bound_dependencies - set((*step.after, *step.settled_after)):
                raise ValueError(f"step {step.name!r} answer bounds reference non-dependencies")
            self._validate_output_visibility(step, known)
            known.add(step.name)
        for derived in self.derived_values:
            missing = set(derived.dependencies) - set(names)
            if missing:
                raise ValueError(
                    f"derived value {derived.name!r} references unknown steps: "
                    f"{sorted(missing)}"
                )

    @staticmethod
    def _expression_nodes(expression: WorkflowExpression):
        if isinstance(expression, WorkflowExpression):
            yield expression
            for value in (*expression.args, *expression.options.values()):
                yield from HumanWorkflow._expression_nodes(value)
        elif isinstance(expression, Mapping):
            for value in expression.values():
                yield from HumanWorkflow._expression_nodes(value)
        elif isinstance(expression, (tuple, list)):
            for value in expression:
                yield from HumanWorkflow._expression_nodes(value)

    def _validate_output_visibility(self, consumer: HumanStep, known: set[str]) -> None:
        """Reject statically identifiable unauthorized references."""
        from .visibility import OWN, participant_keyed, template_references

        definitions = {
            definition.name: definition for definition in self.derived_values
        }
        sources = {view.source_step for view in consumer.participant_submission_views}
        for reference in template_references(consumer.survey.to_dict()):
            if len(reference) < 3 or reference[0] != "workflow":
                continue
            if reference[1] in {"answers", "outputs", "submissions"}:
                if reference[2] in known:
                    sources.add(reference[2])
            elif reference[1] == "derived" and reference[2] in definitions:
                definition = definitions[reference[2]]
                expression = (
                    definition.fields.get(reference[3]) if len(reference) >= 4 else None
                )
                if (
                    expression is not None
                    and len(reference) >= 5
                    and reference[4] is OWN
                    and participant_keyed(expression, definitions)
                ):
                    continue
                sources.update(
                    expression.dependencies
                    if expression is not None
                    else definition.dependencies
                )
        for source_name in sources:
            source = self.step(source_name)
            if source.output_visibility is None:
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
            "version": 2,
            "name": self.name,
            "steps": [step.to_dict() for step in self.steps],
            "metadata": dict(self.metadata),
            "derived_values": [item.to_dict() for item in self.derived_values],
            "repeat_blocks": [item.to_dict() for item in self.repeat_blocks],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HumanWorkflow":
        if data.get("type") != "human_workflow" or data.get("version") not in {1, 2}:
            raise ValueError("unsupported human workflow serialization")
        return cls(
            data["name"],
            [HumanStep.from_dict(step) for step in data["steps"]],
            data.get("metadata", {}),
            [DerivedValue.from_dict(item) for item in data.get("derived_values", ())],
            [RepeatBlock.from_dict(item) for item in data.get("repeat_blocks", ())],
        )
