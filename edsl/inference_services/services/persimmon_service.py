"""Persimmon's conversation API, used by EDSL interview questions."""

from __future__ import annotations

import os
from typing import Any, List, TYPE_CHECKING

import httpx
import requests

from .open_ai_service import OpenAIService

if TYPE_CHECKING:
    from ...language_models import LanguageModel


class PersimmonService(OpenAIService):
    """Service metadata and credentials for the Persimmon user model.

    Persimmon generates turns in a saved multi-participant conversation rather
    than completing a standalone prompt. EDSL routes ``QuestionInterview``
    through its conversation API, and adapts a single EDSL prompt to a brief
    questioner/respondent conversation for standard question types.
    """

    _inference_service_ = "persimmon"
    _env_key_name_ = "PERSIMMON_API_KEY"
    _base_url_ = "https://api.persimmon.humansand.ai/v1"
    _supports_files_api_ = False
    available_models_url = "https://persimmon.humansand.ai/docs"

    @classmethod
    def get_model_info(cls, api_key=None):
        api_key = api_key or os.getenv(cls._env_key_name_)
        if not api_key:
            raise ValueError("PERSIMMON_API_KEY is not set")
        response = requests.get(
            f"{cls._base_url_}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("data", []) if isinstance(data, dict) else data

    @classmethod
    def create_model(
        cls, model_name="persimmon-v0.1", model_class_name=None
    ) -> "LanguageModel":
        model = super().create_model(model_name, model_class_name=model_class_name)
        model._parameters_ = {
            **model._parameters_,
            "tier": "standard",
            "max_tokens": 256,
        }

        async def async_execute_model_call(
            self,
            user_prompt: str,
            system_prompt: str = "",
            question_name=None,
            files_list=None,
            invigilator=None,
            cache_key=None,
            response_schema=None,
            response_schema_name=None,
        ):
            """Answer one EDSL question as a simulated conversation participant."""
            if files_list:
                raise NotImplementedError("Persimmon does not support file inputs.")

            respondent_description = system_prompt.strip()
            if invigilator is not None:
                prompt_constructor = invigilator.prompt_constructor
                persona_parts = (
                    prompt_constructor.agent_instructions_prompt.text,
                    prompt_constructor.agent_persona_prompt.text,
                )
                respondent_description = "\n\n".join(
                    part for part in persona_parts if part
                ) or respondent_description

            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            base_url = cls._base_url_
            timeout = 180
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{base_url}/conversations",
                    headers=headers,
                    json={
                        "model": self.model,
                        "setting": (
                            "A simulated respondent is answering one survey question. "
                            "Respond naturally as the respondent, following the "
                            "question and instructions in the conversation history.\n\n"
                            f"EDSL context and instructions: {system_prompt}"
                        ),
                        "participants": [
                            {
                                "name": "Questioner",
                                "generate_content": False,
                            },
                            {
                                "name": "Respondent",
                                "description": respondent_description[:32000],
                            },
                        ],
                    },
                )
                response.raise_for_status()
                conversation_id = response.json()["id"]
                response = await client.post(
                    f"{base_url}/conversations/{conversation_id}/turns",
                    headers=headers,
                    json={
                        "turns": [{"name": "Questioner", "content": user_prompt}],
                        "speaker": "Respondent",
                        "tier": self.parameters.get("tier", "standard"),
                        "max_tokens": self.parameters.get("max_tokens", 256),
                    },
                )
                response.raise_for_status()
                turn = response.json()

            content = turn.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Persimmon returned no respondent content.")
            usage = turn.get("usage", {})
            return {
                "id": turn.get("id", conversation_id),
                "model": self.model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": turn.get("finish_reason", "stop"),
                        "message": {"role": "assistant", "content": content.strip()},
                    }
                ],
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                "persimmon_turn": turn,
            }

        model.async_execute_model_call = async_execute_model_call
        return model
