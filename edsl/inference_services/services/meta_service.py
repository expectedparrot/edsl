from __future__ import annotations

import os
from typing import Any, List, Optional, TYPE_CHECKING

import aiohttp
import requests

from ..decorators import report_errors_async
from .message_builder import MessageBuilder
from .open_ai_service import OpenAIService

if TYPE_CHECKING:
    from ...invigilators.invigilator_base import InvigilatorBase as InvigilatorAI
    from ...language_models import LanguageModel
    from ...scenarios.file_store import FileStore as Files


class MetaService(OpenAIService):
    """Meta Model API service class."""

    _inference_service_ = "meta"
    _env_key_name_ = "META_API_KEY"
    _fallback_env_key_name_ = "LLAMA_API_KEY"
    _base_url_ = "https://api.meta.ai/v1"
    _responses_url_ = f"{_base_url_}/responses"
    _models_url_ = f"{_base_url_}/models"
    _supports_files_api_ = False
    available_models_url = "https://dev.meta.ai/docs/getting-started/overview/"

    @classmethod
    def _api_key_from_env(cls) -> Optional[str]:
        return os.getenv(cls._env_key_name_) or os.getenv(cls._fallback_env_key_name_)

    @classmethod
    def get_model_info(cls, api_key=None):
        if api_key is None:
            api_key = cls._api_key_from_env()
        if api_key is None:
            raise ValueError(f"API key for {cls._inference_service_} is not set")

        response = requests.get(
            cls._models_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data, list):
            return data
        return []

    @classmethod
    def create_model(
        cls, model_name="muse-spark-1.1", model_class_name=None
    ) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            """Child class of LanguageModel for interacting with Meta models."""

            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            thinking_token_sequence = cls.thinking_token_sequence

            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 1000,
                "top_p": 1,
            }

            @staticmethod
            def _response_text(response: dict[str, Any]) -> str:
                if isinstance(response.get("output_text"), str):
                    return response["output_text"]

                text_parts = []
                for item in response.get("output", []) or []:
                    if not isinstance(item, dict):
                        continue
                    for content in item.get("content", []) or []:
                        if not isinstance(content, dict):
                            continue
                        text = content.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)
                return "\n".join(text_parts)

            @staticmethod
            def _normalized_usage(response: dict[str, Any]) -> dict[str, Any]:
                usage = response.get("usage")
                if not isinstance(usage, dict):
                    return {}
                return {
                    "prompt_tokens": usage.get(
                        "prompt_tokens", usage.get("input_tokens", 0)
                    ),
                    "completion_tokens": usage.get(
                        "completion_tokens", usage.get("output_tokens", 0)
                    ),
                    "total_tokens": usage.get("total_tokens", usage.get("total", 0)),
                }

            def _payload(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["Files"]] = None,
            ) -> dict[str, Any]:
                message_builder = MessageBuilder(
                    model=self.model,
                    files_list=files_list,
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    omit_system_prompt_if_empty=self.omit_system_prompt_if_empty,
                    supports_files_api=False,
                )
                messages = message_builder.get_messages(sync_client=None)
                input_messages = []
                for message in messages:
                    content = message.get("content", "")
                    if isinstance(content, str):
                        content = [{"type": "input_text", "text": content}]
                    else:
                        content = [
                            (
                                {"type": "input_text", "text": item["text"]}
                                if isinstance(item, dict) and item.get("type") == "text"
                                else item
                            )
                            for item in content
                        ]
                    input_messages.append(
                        {
                            "role": message["role"],
                            "content": content,
                        }
                    )

                return {
                    "model": self.model,
                    "input": input_messages,
                    "stream": False,
                }

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                question_name: Optional[str] = None,
                files_list: Optional[List["Files"]] = None,
                invigilator: Optional["InvigilatorAI"] = None,
                cache_key: Optional[str] = None,
                response_schema: Optional[dict] = None,
                response_schema_name: Optional[str] = None,
            ) -> dict[str, Any]:
                payload = self._payload(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    files_list=files_list,
                )
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        cls._responses_url_,
                        headers=headers,
                        json=payload,
                        timeout=120,
                    ) as response:
                        response.raise_for_status()
                        raw_response = await response.json()

                return {
                    **raw_response,
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": self._response_text(raw_response),
                            }
                        }
                    ],
                    "usage": self._normalized_usage(raw_response),
                }

        LLM.__name__ = "LanguageModel"
        LLM.__qualname__ = "LanguageModel"

        return LLM
