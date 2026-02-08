from __future__ import annotations
from typing import Any, List, Optional, Dict, NewType, TYPE_CHECKING
import os

import openai

from ..inference_service_abc import InferenceServiceABC
from ..decorators import report_errors_async
from .service_enums import OPENAI_REASONING_MODELS

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel

# from ..rate_limits_cache import rate_limits
rate_limits = {}

# Default to completions API but can use responses API with parameter

if TYPE_CHECKING:
    from ...scenarios.file_store import FileStore as Files
    from ...invigilators.invigilator_base import InvigilatorBase as InvigilatorAI


APIToken = NewType("APIToken", str)


class OpenAIServiceV2(InferenceServiceABC):
    """OpenAI service class using the Responses API."""

    _inference_service_ = "openai_v2"
    _env_key_name_ = "OPENAI_API_KEY"
    _base_url_ = None

    _sync_client_ = openai.OpenAI
    _async_client_ = openai.AsyncOpenAI

    _sync_client_instances: Dict[APIToken, openai.OpenAI] = {}
    _async_client_instances: Dict[APIToken, openai.AsyncOpenAI] = {}

    # sequence to extract text from response.output
    key_sequence = ["output", 1, "content", 0, "text"]
    usage_sequence = ["usage"]
    # sequence to extract reasoning summary from response.output
    reasoning_sequence = ["output", 0, "summary"]
    input_token_name = "input_tokens"
    output_token_name = "output_tokens"

    available_models_url = "https://platform.openai.com/docs/models/gp"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._sync_client_instances = {}
        cls._async_client_instances = {}

    @classmethod
    def sync_client(cls, api_key: str) -> openai.OpenAI:
        if api_key not in cls._sync_client_instances:
            client = cls._sync_client_(
                api_key=api_key,
                base_url=cls._base_url_,
            )
            cls._sync_client_instances[api_key] = client
        return cls._sync_client_instances[api_key]

    @classmethod
    def async_client(cls, api_key: str) -> openai.AsyncOpenAI:
        if api_key not in cls._async_client_instances:
            client = cls._async_client_(
                api_key=api_key,
                base_url=cls._base_url_,
            )
            cls._async_client_instances[api_key] = client
        return cls._async_client_instances[api_key]

    model_exclude_list = [
        "whisper-1",
        "davinci-002",
        "dall-e-2",
        "tts-1-hd-1106",
        "tts-1-hd",
        "dall-e-3",
        "tts-1",
        "babbage-002",
        "tts-1-1106",
        "text-embedding-3-large",
        "text-embedding-3-small",
        "text-embedding-ada-002",
        "ft:davinci-002:mit-horton-lab::8OfuHgoo",
        "gpt-3.5-turbo-instruct-0914",
        "gpt-3.5-turbo-instruct",
    ]
    _models_list_cache: List[str] = []

    @classmethod
    def get_model_info(cls, api_key: Optional[str] = None):
        """Get raw model info without wrapping in ModelInfo."""
        if api_key is None:
            api_key = os.getenv(cls._env_key_name_)
        raw = cls.sync_client(api_key).models.list()
        return raw.data if hasattr(raw, "data") else raw

    @classmethod
    def available(cls, api_token: Optional[str] = None) -> List[str]:
        if api_token is None:
            api_token = os.getenv(cls._env_key_name_)
        if not cls._models_list_cache:
            data = cls.get_model_list(api_key=api_token)
            cls._models_list_cache = [
                m.id for m in data if m.id not in cls.model_exclude_list
            ]
        return cls._models_list_cache

    @classmethod
    def create_model(
        cls,
        model_name: str,
        model_class_name: Optional[str] = None,
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            """Child class for OpenAI Responses API"""

            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            reasoning_sequence = cls.reasoning_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 2000,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "logprobs": False,
                "top_logprobs": 3,
                "reasoning": None,
            }

            def sync_client(self) -> openai.OpenAI:
                return cls.sync_client(api_key=self.api_token)

            def async_client(self) -> openai.AsyncOpenAI:
                return cls.async_client(api_key=self.api_token)

            @classmethod
            def available(cls) -> list[str]:
                return cls.sync_client().models.list().data

            def get_headers(self) -> dict[str, Any]:
                client = self.sync_client()
                response = client.responses.with_raw_response.create(
                    model=self.model,
                    input=[{"role": "user", "content": "Say this is a test"}],
                    store=False,
                )
                return dict(response.headers)

            def get_rate_limits(self) -> dict[str, Any]:
                try:
                    headers = rate_limits.get("openai", self.get_headers())
                except Exception:
                    return {"rpm": 10000, "tpm": 2000000}
                return {
                    "rpm": int(headers["x-ratelimit-limit-requests"]),
                    "tpm": int(headers["x-ratelimit-limit-tokens"]),
                }

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List[Files]] = None,
                invigilator: Optional[InvigilatorAI] = None,
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> dict[str, Any]:
                # Check if we should use remote proxy
                if self.remote_proxy:
                    # Use remote proxy mode
                    from .remote_proxy_handler import RemoteProxyHandler

                    handler = RemoteProxyHandler(
                        model=self.model,
                        inference_service=self._inference_service_,
                        job_uuid=getattr(self, "job_uuid", None),
                    )

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
                    )

                content = user_prompt
                if files_list:
                    # embed files as separate inputs for Responses API
                    content = [{"type": "input_text", "text": user_prompt}]
                    for f in files_list:
                        if f.mime_type.startswith("image/"):
                            content.append(
                                {
                                    "type": "input_image",
                                    "image_url": f"data:{f.mime_type};base64,{f.base64_string}",
                                }
                            )
                        elif f.mime_type == "application/pdf":
                            # For PDF files, upload to OpenAI first and then reference
                            filename = getattr(f, "filename", "document.pdf")
                            try:
                                import base64
                                import tempfile
                                import os

                                # Create temporary file from base64 data
                                file_content = base64.b64decode(f.base64_string)
                                with tempfile.NamedTemporaryFile(
                                    delete=False, suffix=f"_{filename}"
                                ) as temp_file:
                                    temp_file.write(file_content)
                                    temp_file_path = temp_file.name

                                try:
                                    # Upload file to OpenAI
                                    with open(temp_file_path, "rb") as file_obj:
                                        uploaded_file = self.sync_client().files.create(
                                            file=file_obj, purpose="user_data"
                                        )

                                    content.append(
                                        {
                                            "type": "input_file",
                                            "file_id": uploaded_file.id,
                                        }
                                    )
                                finally:
                                    # Clean up temporary file
                                    if os.path.exists(temp_file_path):
                                        os.unlink(temp_file_path)

                            except Exception as e:
                                # If upload fails, fall back to text description
                                content.append(
                                    {
                                        "type": "input_text",
                                        "text": f"[Error uploading PDF '{filename}': {str(e)}]",
                                    }
                                )
                        else:
                            # For other non-image files, try to include as text
                            filename = getattr(f, "filename", "file")
                            if hasattr(f, "base64_string"):
                                try:
                                    # Try to decode as text
                                    import base64

                                    text_content = base64.b64decode(
                                        f.base64_string
                                    ).decode("utf-8")
                                    content.append(
                                        {
                                            "type": "input_text",
                                            "text": f"--- Content from '{filename}' ---\n{text_content}\n--- End of {filename} ---",
                                        }
                                    )
                                except (UnicodeDecodeError, Exception):
                                    # If we can't decode, mention the file
                                    content.append(
                                        {
                                            "type": "input_text",
                                            "text": f"[File '{filename}' of type '{f.mime_type}' cannot be displayed as text]",
                                        }
                                    )
                # build input sequence
                messages: Any
                if system_prompt:
                    # For Responses API, system content should also be properly formatted
                    system_content = (
                        system_prompt
                        if isinstance(system_prompt, str)
                        else [{"type": "input_text", "input_text": system_prompt}]
                    )
                    messages = [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": content},
                    ]
                else:
                    if self.omit_system_prompt_if_empty:
                        messages = [{"role": "user", "content": content}]
                    else:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": content},
                        ]

                # All OpenAI models with the responses API use these base parameters
                params = {
                    "model": self.model,
                    "input": messages,
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "store": False,
                }

                # Check if this is a reasoning model (o-series models)
                is_reasoning_model = any(
                    tag in self.model for tag in OPENAI_REASONING_MODELS
                )

                # Only add reasoning parameter for reasoning models
                if is_reasoning_model:
                    reasoning_params = {"summary": "auto"}
                    if isinstance(self.reasoning, dict):
                        reasoning_params.update(self.reasoning)
                    params["reasoning"] = reasoning_params

                # For all models using the responses API, use max_output_tokens
                # instead of max_tokens (which is for the completions API)
                params["max_output_tokens"] = self.max_tokens

                # Specifically for o-series, we also set temperature to 1
                if is_reasoning_model:
                    params["temperature"] = 1

                client = self.async_client()
                response = await client.responses.create(**params)
                # convert to dict
                response_dict = response.model_dump()
                return response_dict

        LLM.__name__ = model_class_name
        return LLM

    @staticmethod
    def _create_reasoning_sequence():
        """Create the reasoning sequence for extracting reasoning summaries from model responses."""
        # For OpenAI responses, the reasoning summary is typically found at:
        # ["output", 0, "summary"]
        # This is the path to the 'summary' field in the first item of the 'output' array
        return ["output", 0, "summary"]
