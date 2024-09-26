import os
import httpx
import requests
from typing import Any, Dict
import re
from datetime import datetime
from anthropic import AsyncAnthropic
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models.LanguageModel import LanguageModel


class AnthropicService(InferenceServiceABC):
    """Anthropic service class."""

    _inference_service_ = "anthropic"
    _env_key_name_ = "ANTHROPIC_API_KEY"
    key_sequence = ["content", 0, "text"]  # ["content"][0]["text"]
    usage_sequence = ["usage"]
    input_token_name = "input_tokens"
    output_token_name = "output_tokens"
    model_exclude_list = []

    @classmethod
    def available(cls):
        # TODO - replace with an API call
        return [
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]

    @classmethod
    def create_model(
        cls, model_name: str = "claude-3-opus-20240229", model_class_name=None
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with OpenAI models
            """

            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name

            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 1000,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "logprobs": False,
                "top_logprobs": 3,
            }

            _tpm = cls.get_tpm(cls)
            _rpm = cls.get_rpm(cls)

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str = ""
            ) -> dict[str, Any]:
                """Calls the OpenAI API and returns the API response."""

                api_key = os.environ.get("ANTHROPIC_API_KEY")
                client = AsyncAnthropic(api_key=api_key)

                response = await client.messages.create(
                    model=model_name,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,
                    messages=[
                        #                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                return response.model_dump()

            def get_headers(self) -> Dict[str, str]:
                """
                Makes a minimal API call to Anthropic and returns the response headers.

                Returns:
                    A dictionary containing the response headers.
                """
                api_key = os.environ.get("ANTHROPIC_API_KEY")

                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }

                # Minimal request body to get a response with headers
                data = {
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "Hello"}],
                }

                response = requests.post(
                    "https://api.anthropic.com/v1/messages", headers=headers, json=data
                )

                response.raise_for_status()

                return dict(response.headers)

            def get_rate_limits(self) -> Dict[str, any]:
                """
                Retrieves the current rate limits (RPM and TPM) for the Anthropic API.

                Returns:
                    A dictionary containing rate limit information from the response headers.
                """
                headers = self.get_headers()

                return {
                    "requests_limit": int(
                        headers.get("anthropic-ratelimit-requests-limit", 0)
                    ),
                    "requests_remaining": int(
                        headers.get("anthropic-ratelimit-requests-remaining", 0)
                    ),
                    # "requests_reset": datetime.fromisoformat(
                    #     headers.get("anthropic-ratelimit-requests-reset", "")
                    # ).isoformat(),
                    "tokens_limit": int(
                        headers.get("anthropic-ratelimit-tokens-limit", 0)
                    ),
                    "tokens_remaining": int(
                        headers.get("anthropic-ratelimit-tokens-remaining", 0)
                    ),
                    # "tokens_reset": datetime.fromisoformat(
                    #     headers.get("anthropic-ratelimit-tokens-reset", "")
                    # ).isoformat(),
                    "retry_after": int(headers.get("retry-after", 0)),
                }

        LLM.__name__ = model_class_name

        return LLM
