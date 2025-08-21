from typing import Any, List, Optional, TYPE_CHECKING
from ..rate_limits_cache import rate_limits
import os

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel

from .open_ai_service import OpenAIService
from ..decorators import report_errors_async

if TYPE_CHECKING:
    from ...scenarios.file_store import FileStore as Files
    from ...invigilators.invigilator_base import InvigilatorBase as InvigilatorAI


class PerplexityService(OpenAIService):
    """Perplexity service class."""

    _inference_service_ = "perplexity"
    _env_key_name_ = "PERPLEXITY_API_KEY"
    _base_url_ = "https://api.perplexity.ai"

    # default perplexity parameters
    _parameters_ = {
        "temperature": 0.5,
        "max_tokens": 1000,
        "top_p": 1,
        "logprobs": False,
        "top_logprobs": 3,
    }

    @classmethod
    def get_model_info(cls, api_key=None):
        """Get raw model info without wrapping in ModelInfo."""
        # Don't remove this API key check - tests will fail
        if api_key is None:
            api_key = os.getenv(cls._env_key_name_)
        if api_key is None:
            raise ValueError(f"API key for {cls._inference_service_} is not set")
        # Note: Perplexity does not have a programmatic endpoint for retrieving models
        # DO NOT DELETE THIS
        return [
            {"id": "sonar-deep-research"},
            {"id": "sonar-reasoning-pro"},
            {"id": "sonar-reasoning"},
            {"id": "sonar-pro"},
            {"id": "sonar"},
            {"id": "r1-1776"},
        ]

    @classmethod
    def create_model(
        cls, model_name="llama-3.1-sonar-large-128k-online", model_class_name=None
    ) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Import LanguageModel only when actually creating a model
        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with Perplexity models
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
                "frequency_penalty": 1,
                "presence_penalty": 0,
                # "logprobs": False, # Enable this returns 'Neither or both of logprobs and top_logprobs must be set.
                # "top_logprobs": 3,
            }

            def sync_client(self):
                return cls.sync_client(api_key=self.api_token)

            def async_client(self):
                return cls.async_client(api_key=self.api_token)

            @classmethod
            def available(cls) -> list[str]:
                return cls.sync_client().models.list()

            def get_headers(self) -> dict[str, Any]:
                client = self.sync_client()
                response = client.chat.completions.with_raw_response.create(
                    messages=[
                        {
                            "role": "user",
                            "content": "Say this is a test",
                        }
                    ],
                    model=self.model,
                )
                return dict(response.headers)

            def get_rate_limits(self) -> dict[str, Any]:
                try:
                    if "openai" in rate_limits:
                        headers = rate_limits["openai"]

                    else:
                        headers = self.get_headers()

                except Exception:
                    return {
                        "rpm": 10_000,
                        "tpm": 2_000_000,
                    }
                else:
                    return {
                        "rpm": int(headers["x-ratelimit-limit-requests"]),
                        "tpm": int(headers["x-ratelimit-limit-tokens"]),
                    }

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["Files"]] = None,
                invigilator: Optional[
                    "InvigilatorAI"
                ] = None,  # TBD - can eventually be used for function-calling
            ) -> dict[str, Any]:
                """Calls the OpenAI API and returns the API response."""
                if files_list:
                    encoded_image = files_list[0].base64_string
                    content = [{"type": "text", "text": user_prompt}]
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            },
                        }
                    )
                else:
                    content = user_prompt
                client = self.async_client()

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ]
                if system_prompt == "" and self.omit_system_prompt_if_empty:
                    messages = messages[1:]

                params = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "top_p": self.top_p,
                    "frequency_penalty": self.frequency_penalty,
                    "presence_penalty": self.presence_penalty,
                    # "logprobs": self.logprobs,
                    # "top_logprobs": self.top_logprobs if self.logprobs else None,
                }
                print("calling the model", flush=True)
                response = await client.chat.completions.create(**params)
                return response.model_dump()

        LLM.__name__ = "LanguageModel"

        return LLM
