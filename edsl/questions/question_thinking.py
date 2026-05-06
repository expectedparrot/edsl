"""A question type that sends its text directly to a specified model, bypassing agent/persona.

Also provides ``thinking_question()``, a function that wraps any existing
question to use a dedicated model and system prompt while keeping the
original question type's validation, answering instructions, and options.
"""

from __future__ import annotations
import copy
from typing import Optional
from uuid import uuid4

from .question_base import QuestionBase
from .question_free_text import FreeTextResponse, FreeTextResponseValidator
from .decorators import inject_exception


class QuestionThinking(QuestionBase):
    """A question that sends question_text directly to a specified model.

    Unlike other question types, QuestionThinking:
    - Uses its own model, not the survey-level model
    - Uses its own system_prompt (default empty), ignoring agent persona
    - Sends question_text as the user prompt
    - Returns the model's raw text response as the answer

    Examples:
        >>> q = QuestionThinking(question_name="t1", question_text="Say hello", model="test")
        >>> q.question_type
        'thinking'
    """

    question_type = "thinking"
    _response_model = FreeTextResponse
    response_validator_class = FreeTextResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        model=None,
        system_prompt: str = "",
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        from ..language_models import Model, LanguageModel

        self.question_name = question_name
        self.question_text = question_text
        self._system_prompt = system_prompt
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

        if model is None:
            self._model = Model()
        elif isinstance(model, str):
            self._model = Model(model)
        elif isinstance(model, dict):
            self._model = LanguageModel.from_dict(model)
        else:
            self._model = model

    @property
    def _invigilator_class(self):
        from ..invigilators.invigilator_thinking import InvigilatorThinking
        return InvigilatorThinking

    def to_dict(self, add_edsl_version: bool = True):
        d = super().to_dict(add_edsl_version=add_edsl_version)
        d["model"] = self._model.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionThinking":
        from ..language_models import LanguageModel

        local_data = data.copy()
        # Remove edsl metadata fields
        local_data.pop("edsl_version", None)
        local_data.pop("edsl_class_name", None)
        local_data.pop("question_type", None)

        model_data = local_data.pop("model", None)
        if model_data is not None:
            local_data["model"] = LanguageModel.from_dict(model_data)

        return cls(**local_data)

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionThinking":
        """Return an example QuestionThinking.

        >>> q = QuestionThinking.example()
        >>> q.question_name
        'thinking_example'
        """
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="thinking_example",
            question_text=f"What is 2 + 2?{addition}",
            model="test",
        )


def thinking_question(q: "QuestionBase", model=None, system_prompt: str = "") -> "QuestionBase":
    """Wrap any question to use a dedicated model and system prompt.

    The returned question keeps the original's type, options, validation,
    answering instructions, and question presentation — but bypasses the
    agent persona and uses its own model for inference.

    Args:
        q: Any QuestionBase instance.
        model: Model name (str), Model instance, dict, or None for default.
        system_prompt: Replaces the agent persona in the system prompt.

    Returns:
        A deep copy of *q* configured to use the specified model/system_prompt.
    """
    from ..language_models import Model, LanguageModel
    from ..invigilators.invigilator_thinking_ai import InvigilatorThinkingAI

    new_q = copy.deepcopy(q)

    # Resolve the model
    if model is None:
        resolved_model = Model()
    elif isinstance(model, str):
        resolved_model = Model(model)
    elif isinstance(model, dict):
        resolved_model = LanguageModel.from_dict(model)
    else:
        resolved_model = model

    new_q._model = resolved_model
    new_q._system_prompt = system_prompt
    new_q._is_thinking_question = True

    # Store serializable form for to_dict round-trip
    new_q._thinking_model = resolved_model.to_dict()
    new_q._thinking_system_prompt = system_prompt

    # Override invigilator selection — this attribute is checked first
    # in agents/agent_invigilator.py get_invigilator_class()
    new_q._invigilator_class = InvigilatorThinkingAI

    return new_q
