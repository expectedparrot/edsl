from __future__ import annotations
from typing import Any, List, Optional, Dict, NewType, TYPE_CHECKING
import os

import openai

from ..inference_service_abc import InferenceServiceABC
from .message_builder import MessageBuilder
from ..decorators import report_errors_async
from .service_enums import OPENAI_REASONING_MODELS

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel

rate_limits = {}

if TYPE_CHECKING:
    from ...scenarios.file_store import FileStore as Files
    from ...invigilators.invigilator_base import InvigilatorBase as InvigilatorAI


APIToken = NewType("APIToken", str)


class OpenAIParameterBuilder:
    """Helper class to construct API parameters based on model type."""

    @staticmethod
    def build_params(model: str, messages: list, **model_params) -> dict:
        """Build API parameters, adjusting for specific model types."""

        default_max_tokens = model_params.get("max_tokens", 1000)
        default_temperature = model_params.get("temperature", 0.5)
        if model in OPENAI_REASONING_MODELS:
            # For reasoning models, use much higher completion tokens to allow for reasoning + response
            max_tokens = max(default_max_tokens, 5000)
            temperature = 1
        else:
            max_tokens = default_max_tokens
            temperature = default_temperature

        # Base parameters
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "top_p": model_params.get("top_p", 1),
            "frequency_penalty": model_params.get("frequency_penalty", 0),
            "presence_penalty": model_params.get("presence_penalty", 0),
            "logprobs": model_params.get("logprobs", False),
            "top_logprobs": (
                model_params.get("top_logprobs", 3)
                if model_params.get("logprobs", False)
                else None
            ),
        }

        return params


class OpenAIService(InferenceServiceABC):
    """OpenAI service class."""

    _inference_service_ = "openai"
    _env_key_name_ = "OPENAI_API_KEY"
    _base_url_ = None

    _sync_client_ = openai.OpenAI
    _async_client_ = openai.AsyncOpenAI

    _sync_client_instances: Dict[APIToken, openai.OpenAI] = {}
    _async_client_instances: Dict[APIToken, openai.AsyncOpenAI] = {}

    key_sequence = ["choices", 0, "message", "content"]
    usage_sequence = ["usage"]
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"

    available_models_url = "https://platform.openai.com/docs/models/gp"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # so subclasses that use the OpenAI api key have to create their own instances of the clients
        cls._sync_client_instances = {}
        cls._async_client_instances = {}

    @classmethod
    def sync_client(cls, api_key):
        if api_key not in cls._sync_client_instances:
            client = cls._sync_client_(
                api_key=api_key,
                base_url=cls._base_url_,
            )
            cls._sync_client_instances[api_key] = client
        client = cls._sync_client_instances[api_key]
        return client

    @classmethod
    def async_client(cls, api_key):
        if api_key not in cls._async_client_instances:
            client = cls._async_client_(
                api_key=api_key,
                base_url=cls._base_url_,
            )
            cls._async_client_instances[api_key] = client
        client = cls._async_client_instances[api_key]
        return client

    @classmethod
    def get_model_info(cls, api_key=None):
        """Get raw model info without wrapping in ModelInfo."""
        if api_key is None:
            api_key = os.getenv(cls._env_key_name_)
        if api_key is None:
            raise ValueError(f"API key for {cls._inference_service_} is not set")
        raw_list = cls.sync_client(api_key).models.list()
        if hasattr(raw_list, "data"):
            return raw_list.data
        else:
            return raw_list

    # @classmethod
    # def available(cls, api_token=None) -> List[str]:
    #     if api_token is None:
    #         api_token = os.getenv(cls._env_key_name_)
    #     if not cls._models_list_cache:
    #         try:
    #             cls._models_list_cache = [
    #                 m.id
    #                 for m in cls.get_model_list(api_key=api_token)
    #                 if m.id not in cls.model_exclude_list
    #             ]
    #         except Exception:
    #             raise
    #     return cls._models_list_cache

    @classmethod
    def create_model(cls, model_name, model_class_name=None) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Import LanguageModel only when actually creating a model
        from ...language_models import LanguageModel

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

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 1000,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "logprobs": False,
                "top_logprobs": 3,
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

            def _filter_parameters_for_service(self, params: dict) -> dict:
                """
                Apply service-specific parameter filtering before sending to API.

                Args:
                    params: Dictionary of API parameters

                Returns:
                    Filtered parameters dictionary with service-specific adjustments
                """
                # XAI service specific filtering
                if self._inference_service_ == "xai":
                    if "grok-4" in self.model:
                        # Grok-4 models don't support penalty parameters
                        params.pop("presence_penalty", None)
                        params.pop("frequency_penalty", None)

                # Add additional service-specific filtering logic here as needed
                # Example:
                # elif self._inference_service_ == "another_service":
                #     # Apply other service-specific filters
                #     pass

                return params

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                question_name: Optional[str] = None,
                files_list: Optional[List["Files"]] = None,
                invigilator: Optional[
                    "InvigilatorAI"
                ] = None,  # TBD - can eventually be used for function-calling
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> dict[str, Any]:
                """Calls the OpenAI API and returns the API response.

                Args:
                    user_prompt: The user message or input prompt
                    system_prompt: The system message or context
                    question_name: Optional name of the question being asked
                    files_list: Optional list of files to include
                    invigilator: Optional invigilator for function-calling
                    remote_proxy: Optional URL of remote proxy to use instead of direct API call
                """

                # Check if we should use remote proxy
                if self.remote_proxy:
                    # Use remote proxy mode
                    from .remote_proxy_handler import RemoteProxyHandler

                    print("remote proxy enabled")
                    handler = RemoteProxyHandler(
                        model=self.model,
                        inference_service=self._inference_service_,
                        job_uuid=getattr(self, "job_uuid", None),
                    )

                    # Get fresh parameter
                    fresh_value = getattr(self, "fresh", False)

                    return await handler.execute_model_call(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        files_list=files_list,
                        cache_key=cache_key,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        top_p=self.top_p,
                        frequency_penalty=self.frequency_penalty,
                        presence_penalty=self.presence_penalty,
                        logprobs=self.logprobs,
                        top_logprobs=self.top_logprobs,
                        omit_system_prompt_if_empty=self.omit_system_prompt_if_empty,
                        fresh=fresh_value,  # Pass fresh parameter
                    )

                # Use MessageBuilder to construct messages
                message_builder = MessageBuilder(
                    model=self.model,
                    files_list=files_list,
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    omit_system_prompt_if_empty=self.omit_system_prompt_if_empty,
                )

                client = self.async_client()
                messages = message_builder.get_messages(sync_client=self.sync_client())

                # Use OpenAIParameterBuilder to construct parameters
                params = OpenAIParameterBuilder.build_params(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    frequency_penalty=self.frequency_penalty,
                    presence_penalty=self.presence_penalty,
                    logprobs=self.logprobs,
                    top_logprobs=self.top_logprobs,
                )
                # Apply service-specific parameter filtering
                params = self._filter_parameters_for_service(params)

                response = await client.chat.completions.create(**params)
                return response.model_dump()

        # Ensure the class name is "LanguageModel" for proper serialization
        LLM.__name__ = "LanguageModel"
        LLM.__qualname__ = "LanguageModel"

        return LLM
