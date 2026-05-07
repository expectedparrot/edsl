from __future__ import annotations

from typing import Any, Optional

import httpx

from .language_model import LanguageModel
from ..key_management.key_lookup import KeyLookup
from ..inference_services.services.message_builder import MessageBuilder


class HostedOpenAICompatibleLanguageModel(LanguageModel):
    """Standalone model for OpenAI-compatible hosted endpoints.

    This path is intentionally separate from EDSL's built-in OpenAI service
    so custom endpoints can be used without mutating global provider config.
    """

    _model_ = None
    _inference_service_ = "openai"
    key_sequence = ["choices", 0, "message", "content"]
    usage_sequence = ["usage"]
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"
    thinking_token_sequence = ["completion_tokens_details", "reasoning_tokens"]
    _parameters_ = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "logprobs": False,
        "top_logprobs": 3,
        "reasoning_effort": None,
        "base_url": None,
        "protocol": "openai",
        "hosted": True,
    }

    def __init__(
        self,
        remote_model_name: str,
        *,
        base_url: str,
        api_token: Optional[str] = None,
        **kwargs: Any,
    ):
        kwargs = kwargs.copy()
        kwargs["base_url"] = base_url.rstrip("/")
        kwargs.setdefault("key_lookup", KeyLookup({}))
        if "protocol" not in kwargs:
            kwargs["protocol"] = "openai"
        if "hosted" not in kwargs:
            kwargs["hosted"] = True
        if api_token is not None:
            kwargs["api_token"] = api_token
        super().__init__(**kwargs)
        if api_token is None:
            self._api_token = ""
        self.model = remote_model_name

    def has_valid_api_key(self) -> bool:
        """Hosted endpoints may be intentionally unauthenticated."""
        return True

    @property
    def api_token(self) -> str:
        """Return an explicit token if set, otherwise an empty string."""
        return getattr(self, "_api_token", "")

    async def async_execute_model_call(
        self,
        user_prompt: str,
        system_prompt: str = "",
        question_name: Optional[str] = None,
        files_list=None,
        invigilator=None,
        cache_key: Optional[str] = None,
        response_schema: Optional[dict] = None,
        response_schema_name: Optional[str] = None,
    ) -> dict[str, Any]:
        if files_list:
            raise NotImplementedError(
                "HostedModel does not currently support file attachments."
            )

        message_builder = MessageBuilder(
            model=self.model,
            files_list=files_list,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            omit_system_prompt_if_empty=self.omit_system_prompt_if_empty,
            supports_files_api=False,
        )
        messages = message_builder.get_messages()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "logprobs": self.logprobs,
            "top_logprobs": self.top_logprobs if self.logprobs else None,
        }

        if response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema_name or "response_schema",
                    "strict": True,
                    "schema": response_schema,
                },
            }

        headers = {"Content-Type": "application/json"}
        if getattr(self, "_api_token", None):
            headers["Authorization"] = f"Bearer {self._api_token}"

        timeout = max(self._compute_timeout(files_list), 300)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()


class HostedModel:
    """Sugar constructor for OpenAI-compatible hosted endpoints."""

    def __new__(
        cls,
        model_name: str,
        *,
        base_url: str,
        api_token: Optional[str] = None,
        **kwargs: Any,
    ) -> HostedOpenAICompatibleLanguageModel:
        return HostedOpenAICompatibleLanguageModel(
            model_name,
            base_url=base_url,
            api_token=api_token,
            **kwargs,
        )
