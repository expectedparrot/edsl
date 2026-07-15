from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from types import SimpleNamespace
from typing import Any, Dict, Optional

from jinja2 import Template

from ..base.data_transfer_models import EDSLResultObjectInput
from ..prompts import Prompt
from .invigilators import InvigilatorBase


class PangramConfigurationError(RuntimeError):
    """Raised when Pangram local inference is not configured."""


class PangramClient:
    base_url = "https://text.external-api.pangram.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("PANGRAM_API_KEY")
        if not self.api_key:
            raise PangramConfigurationError(
                "QuestionSlop requires PANGRAM_API_KEY for local Pangram inference."
            )

    async def score_text(
        self,
        text: str,
        *,
        public_dashboard_link: bool = False,
        timeout_seconds: float = 300,
        poll_interval: float = 0.5,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._score_text_sync,
            text,
            public_dashboard_link=public_dashboard_link,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
        )

    def _score_text_sync(
        self,
        text: str,
        *,
        public_dashboard_link: bool,
        timeout_seconds: float,
        poll_interval: float,
    ) -> dict[str, Any]:
        submit = self._request_json(
            "POST",
            "/task",
            {
                "text": text,
                "public_dashboard_link": public_dashboard_link,
            },
        )
        task_id = submit.get("task_id")
        if not task_id:
            raise RuntimeError("Pangram response did not include task_id.")

        deadline = time.monotonic() + timeout_seconds
        while True:
            result = self._request_json("GET", f"/task/{task_id}")
            stage = result.get("stage")
            if stage in {"STAGE_SUCCESS", "STAGE_FAILED"}:
                return result
            if time.monotonic() >= deadline:
                raise TimeoutError("Timed out waiting for Pangram task completion.")
            time.sleep(poll_interval)

    def _request_json(
        self, method: str, path: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise PangramHTTPError(exc.code, body) from exc


class PangramHTTPError(RuntimeError):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"Pangram HTTP {status_code}: {body}")


class InvigilatorSlop(InvigilatorBase):
    """Invigilator that scores rendered question text with Pangram."""

    client_class = PangramClient

    def _render_text(self) -> str:
        prior_answers = self._prior_answer_template_context(self.current_answers)
        context = dict(self.scenario) | prior_answers | {"agent": self.agent.traits}
        context["scenario"] = {
            key: value for key, value in context.items() if not key.startswith("_")
        }
        return Template(self.question.question_text).render(context)

    @staticmethod
    def _prior_answer_template_context(current_answers: dict) -> dict:
        context = {}
        for key, value in (current_answers or {}).items():
            if key.endswith("_comment") or key.endswith("_generated_tokens"):
                continue
            context[key] = SimpleNamespace(answer=value)
        return context

    def get_prompts(self) -> Dict[str, Any]:
        return {
            "user_prompt": Prompt(self._render_text()),
            "system_prompt": Prompt(""),
        }

    async def async_answer_question(self) -> EDSLResultObjectInput:
        rendered_text = self._render_text()
        prompts = {
            "user_prompt": Prompt(rendered_text),
            "system_prompt": Prompt(""),
        }

        answer: dict[str, Any]
        raw_response: Optional[dict[str, Any]]
        comment = None

        if (
            len(rendered_text) < self.question.min_text_length
            and self.question.on_short_text != "score_anyway"
        ):
            if self.question.on_short_text == "raise":
                raise ValueError(
                    f"QuestionSlop text length {len(rendered_text)} is shorter than "
                    f"min_text_length={self.question.min_text_length}."
                )
            raw_response = None
            answer = self._too_short_answer(rendered_text)
        else:
            try:
                client = self.client_class()
                raw_response = await client.score_text(
                    rendered_text,
                    public_dashboard_link=self.question.public_dashboard_link,
                    timeout_seconds=self.question.timeout_seconds,
                    poll_interval=self.question.poll_interval,
                )
                answer = self._normalize_response(
                    raw_response,
                    rendered_text=rendered_text,
                    include_segments=self.question.include_segments,
                    include_raw_response=self.question.include_raw_response,
                )
            except PangramConfigurationError:
                raise
            except Exception as exc:
                raw_response = None
                answer = self._error_answer(rendered_text, exc)
                comment = str(exc)

        data = {
            "answer": answer,
            "generated_tokens": rendered_text,
            "comment": comment,
            "question_name": self.question.question_name,
            "prompts": prompts,
            "cached_response": None,
            "raw_model_response": raw_response,
            "cache_used": False,
            "cache_key": None,
            "validated": True,
            "exception_occurred": None,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "input_price_per_million_tokens": None,
            "output_price_per_million_tokens": None,
            "total_cost": None,
        }
        return EDSLResultObjectInput(**data)

    @staticmethod
    def _too_short_answer(rendered_text: str) -> dict[str, Any]:
        return {
            "classification": "too_short",
            "headline": None,
            "prediction": None,
            "ai_score": None,
            "ai_assisted_score": None,
            "human_score": None,
            "confidence": None,
            "provider": "pangram",
            "provider_model": None,
            "text_length": len(rendered_text),
            "num_ai_segments": None,
            "num_ai_assisted_segments": None,
            "num_human_segments": None,
            "dashboard_link": None,
            "segments": None,
            "raw_response": None,
        }

    @staticmethod
    def _error_answer(rendered_text: str, exc: Exception) -> dict[str, Any]:
        return {
            "classification": "error",
            "headline": None,
            "prediction": None,
            "ai_score": None,
            "ai_assisted_score": None,
            "human_score": None,
            "confidence": None,
            "provider": "pangram",
            "provider_model": None,
            "text_length": len(rendered_text),
            "num_ai_segments": None,
            "num_ai_assisted_segments": None,
            "num_human_segments": None,
            "dashboard_link": None,
            "segments": None,
            "raw_response": None,
            "error_code": InvigilatorSlop._error_code(exc),
            "error_message": str(exc),
        }

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if isinstance(exc, TimeoutError):
            return "timeout"
        if isinstance(exc, PangramHTTPError):
            if exc.status_code == 402:
                return "insufficient_credits"
            if exc.status_code == 403:
                return "forbidden"
            if exc.status_code == 413:
                return "payload_too_large"
            if exc.status_code == 422:
                return "invalid_text"
            if exc.status_code == 429:
                return "rate_limited"
            return f"http_{exc.status_code}"
        return "provider_error"

    @staticmethod
    def _normalize_response(
        raw_response: dict[str, Any],
        *,
        rendered_text: str,
        include_segments: bool,
        include_raw_response: bool,
    ) -> dict[str, Any]:
        windows = raw_response.get("windows") or []
        segments = None
        if include_segments:
            segments = [
                {
                    "text": window.get("text"),
                    "start": window.get("start_index"),
                    "end": window.get("end_index"),
                    "label": window.get("label"),
                    "ai_assistance_score": window.get("ai_assistance_score"),
                    "confidence": window.get("confidence"),
                    "word_count": window.get("word_count"),
                    "token_length": window.get("token_length"),
                }
                for window in windows
            ]

        return {
            "classification": InvigilatorSlop._classification(
                raw_response.get("prediction_short")
            ),
            "headline": raw_response.get("headline"),
            "prediction": raw_response.get("prediction"),
            "ai_score": raw_response.get("fraction_ai"),
            "ai_assisted_score": raw_response.get("fraction_ai_assisted"),
            "human_score": raw_response.get("fraction_human"),
            "confidence": None,
            "provider": "pangram",
            "provider_model": raw_response.get("version"),
            "text_length": len(rendered_text),
            "num_ai_segments": raw_response.get("num_ai_segments"),
            "num_ai_assisted_segments": raw_response.get("num_ai_assisted_segments"),
            "num_human_segments": raw_response.get("num_human_segments"),
            "dashboard_link": raw_response.get("dashboard_link"),
            "segments": segments,
            "raw_response": raw_response if include_raw_response else None,
        }

    @staticmethod
    def _classification(prediction_short: Optional[str]) -> str:
        mapping = {
            "AI": "ai",
            "AI-Assisted": "ai_assisted",
            "Human": "human",
            "Mixed": "mixed",
        }
        return mapping.get(prediction_short or "", "uncertain")

