from abc import ABC, abstractmethod
from dataclasses import dataclass
import re
from typing import Any

from .refs import AnswerRef
from .store import Operation, WriteResult


@dataclass(frozen=True)
class StepContext:
    answers: dict[str, Any]
    interview_id: str
    scope: str | None = None
    agent_traits: dict[str, Any] | None = None
    run_context: dict[str, Any] | None = None


class Step(ABC):
    @abstractmethod
    def execute(self, context: StepContext) -> WriteResult: ...


class WriteStep(Step):
    def __init__(self, primitive, op: str, args: dict[str, Any]):
        self.primitive = primitive
        self.op = op
        self.args = args

    def execute(self, context: StepContext) -> WriteResult:
        resolved = self._resolve_args(context)
        state = self.primitive.parent
        return state.store.apply(
            Operation(
                scope=context.scope or state.scope,
                target=self.primitive.name,
                op=self.op,
                args=resolved,
                interview_id=context.interview_id,
            )
        )

    def _resolve_args(self, context: StepContext) -> dict[str, Any]:
        def resolve(value):
            if isinstance(value, AnswerRef):
                return value.resolve(context.answers)
            if isinstance(value, str):
                match = re.fullmatch(r"\s*{{\s*agent\.([A-Za-z_]\w*)\s*}}\s*", value)
                if match:
                    trait = match.group(1)
                    traits = context.agent_traits or {}
                    if trait not in traits:
                        raise KeyError(f"missing agent trait '{trait}'")
                    return traits[trait]
                match = re.fullmatch(r"\s*{{\s*run\.([A-Za-z_]\w*)\s*}}\s*", value)
                if match:
                    key = match.group(1)
                    run_context = context.run_context or {}
                    if key not in run_context:
                        raise KeyError(f"missing run context '{key}'")
                    return run_context[key]
            return value

        return {key: resolve(value) for key, value in self.args.items()}

    @property
    def answer_refs(self) -> list[AnswerRef]:
        return [value for value in self.args.values() if isinstance(value, AnswerRef)]

    def to_dict(self) -> dict:
        return {
            "target": self.primitive.name,
            "op": self.op,
            "args": {
                key: {"answer_ref": value.to_dict()}
                if isinstance(value, AnswerRef)
                else value
                for key, value in self.args.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict, state) -> "WriteStep":
        args = {
            key: AnswerRef.from_dict(value["answer_ref"])
            if isinstance(value, dict) and "answer_ref" in value
            else value
            for key, value in data["args"].items()
        }
        return cls(state.primitives[data["target"]], data["op"], args)


class BeforeQuestionAction(WriteStep):
    """Atomic shared-state operation executed immediately before prompt render."""

    def __init__(self, primitive, op: str, args: dict[str, Any], question_name: str):
        super().__init__(primitive, op, args)
        self.question_name = question_name

    def execute(self, context: StepContext) -> WriteResult:
        state = self.primitive.parent
        return state.store.apply(
            Operation(
                scope=context.scope or state.scope,
                target=self.primitive.name,
                op=self.op,
                args=self._resolve_args(context),
                interview_id=context.interview_id,
                idempotency_key=(
                    f"{context.interview_id}:before:{self.question_name}:"
                    f"{self.primitive.name}:{self.op}"
                ),
            )
        )

    def to_dict(self) -> dict:
        return super().to_dict() | {"before_question": self.question_name}

    @classmethod
    def from_dict(cls, data: dict, state) -> "BeforeQuestionAction":
        step = WriteStep.from_dict(data, state)
        return cls(
            step.primitive,
            step.op,
            step.args,
            question_name=data["before_question"],
        )
