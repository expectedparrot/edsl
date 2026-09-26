from dataclasses import dataclass
from typing import Any

from .exceptions import SharedStateResolutionError


@dataclass(frozen=True)
class AnswerRef:
    question_name: str

    def resolve(self, answers: dict) -> Any:
        if self.question_name not in answers:
            raise SharedStateResolutionError(
                f"answer for question '{self.question_name}' is not available; "
                "place the write step after that question"
            )
        return answers[self.question_name]

    def to_dict(self) -> dict:
        return {"question_name": self.question_name}

    @classmethod
    def from_dict(cls, data: dict) -> "AnswerRef":
        return cls(data["question_name"])


@dataclass(frozen=True)
class ContextRef:
    """A serializable reference such as ``current.agent.name``."""

    path: tuple[str, ...] = ()

    def __getattr__(self, name: str) -> "ContextRef":
        if name.startswith("_"):
            raise AttributeError(name)
        return ContextRef(self.path + (name,))

    def __call__(self, path: str, default: Any = None):
        """Build a machine-runtime reference such as ``current("closed")``.

        Attribute access remains the authoring-context form, for example
        ``current.agent.name``. Supporting both on the public object avoids a
        second, easily confused ``current`` import for DSL expressions.
        """
        if self.path:
            raise TypeError("only the root 'current' object is callable")
        from .dsl import current as current_expression

        return current_expression(path, default)

    def resolve(self, context) -> Any:
        if not self.path:
            return context
        root, *parts = self.path
        if root == "agent":
            value: Any = context.agent_traits or {}
        elif root == "run":
            value = context.run_context or {}
        elif root == "interview_id":
            value = context.interview_id
        else:
            raise SharedStateResolutionError(
                f"unknown current context root '{root}'"
            )
        for part in parts:
            try:
                value = value[part] if isinstance(value, dict) else getattr(value, part)
            except (KeyError, AttributeError) as exc:
                raise SharedStateResolutionError(
                    f"current.{'.'.join(self.path)} is not available"
                ) from exc
        return value

    def to_dict(self) -> dict:
        return {"path": list(self.path)}

    @classmethod
    def from_dict(cls, data: dict) -> "ContextRef":
        return cls(tuple(data["path"]))


current = ContextRef()
