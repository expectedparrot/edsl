"""Pangram AI detection as a composable, self-answering survey question."""

from __future__ import annotations

import asyncio
import math
import os
from html import escape
from typing import Any, Optional

from pydantic import BaseModel

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class DetectAIResponse(BaseModel):
    answer: dict[str, Any]
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None


class DetectAIResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": {"fraction_ai": 0.9}}, {})]
    invalid_examples = [({"answer": "AI"}, {}, "The answer must be a JSON object.")]


class QuestionDetectAI(QuestionBase):
    """Analyze text with Pangram and store its full JSON object in ``answer``.

    Install ``pangram-sdk`` and set ``PANGRAM_API_KEY`` in the execution
    environment. Credentials are read only at execution and never serialized.
    Pangram calls are external API requests even when EDSL runs locally, and
    Pangram bills them separately. They do not use EDSL's LLM response cache.

    ``question_text`` is required and accepts literal text or ordinary EDSL
    templates, including scenario fields and prior answers. Later questions can use
    ``{{ detection.answer.fraction_ai }}``, and skip rules can use
    ``detection['fraction_ai'] > 0.5``.

    >>> q = QuestionDetectAI(question_name="detection", question_text="{{ essay.answer }}")
    >>> q.question_type
    'detect_ai'
    """

    question_type = "detect_ai"
    _response_model = DetectAIResponse
    response_validator_class = DetectAIResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        *,
        timeout: float = 300,
        poll_interval: float = 0.5,
    ):
        for name, value in (("timeout", timeout), ("poll_interval", poll_interval)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite positive number.")

        self.question_name = question_name
        if not isinstance(question_text, str) or not question_text.strip():
            raise ValueError("DetectAI requires non-empty question_text.")
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self._timeout = timeout
        self._poll_interval = poll_interval

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def poll_interval(self) -> float:
        return self._poll_interval

    def answer_question_directly(self, scenario, agent_traits=None):
        """Render the input and return the completed Pangram result unchanged."""
        context = scenario.data if hasattr(scenario, "data") else scenario
        text = self.render(context, return_dict=True)["question_text"]
        if not text.strip():
            raise ValueError("DetectAI requires non-empty text.")

        api_key = os.environ.get("PANGRAM_API_KEY")
        if not api_key or not api_key.strip():
            raise ValueError("Set PANGRAM_API_KEY to run a DetectAI question.")

        try:
            from pangram import Pangram
        except ImportError as exc:
            raise ImportError(
                "DetectAI requires pangram-sdk. Install it with "
                "`pip install --upgrade pangram-sdk`."
            ) from exc

        result = Pangram(api_key=api_key).predict(
            text,
            model="default",
            public_dashboard_link=False,
            timeout=self.timeout,
            poll_interval=self.poll_interval,
        )
        if isinstance(result, dict) and result.get("stage") == "STAGE_FAILED":
            raise ValueError("Pangram failed to analyze the text.")
        return self._response_model(answer=result).model_dump()

    async def async_answer_question_directly(self, scenario, agent_traits=None):
        """Keep Pangram's blocking polling off the survey's event loop."""
        return await asyncio.to_thread(
            self.answer_question_directly, scenario, agent_traits
        )

    @property
    def question_html_content(self) -> str:
        return f'<pre class="detect-ai-question">{escape(self.question_text)}</pre>'

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionDetectAI":
        from uuid import uuid4

        text = "This is an example passage to analyze with Pangram."
        if randomize:
            text += f" {uuid4()}"
        return cls(question_name="detection", question_text=text)


DetectAI = QuestionDetectAI
