from typing import Any, List
import re
import os

# from openai import AsyncOpenAI
import openai

from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel
from edsl.inference_services.rate_limits_cache import rate_limits
from edsl.utilities.utilities import fix_partial_correct_response


class OpenAIService(InferenceServiceABC):
    """OpenAI service class."""

    _inference_service_ = "openai"
    _env_key_name_ = "OPENAI_API_KEY"
    _base_url_ = None

    _sync_client_ = openai.OpenAI
    _async_client_ = openai.AsyncOpenAI

    _sync_client_instance = None
    _async_client_instance = None

    key_sequence = ["choices", 0, "message", "content"]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # so subclasses have to create their own instances of the clients
        cls._sync_client_instance = None
        cls._async_client_instance = None

    @classmethod
    def sync_client(cls):
        if cls._sync_client_instance is None:
            cls._sync_client_instance = cls._sync_client_(
                api_key=os.getenv(cls._env_key_name_), base_url=cls._base_url_
            )
        return cls._sync_client_instance

    @classmethod
    def async_client(cls):
        if cls._async_client_instance is None:
            cls._async_client_instance = cls._async_client_(
                api_key=os.getenv(cls._env_key_name_), base_url=cls._base_url_
            )
        return cls._async_client_instance

    # @classmethod
    # def sync_client(cls):
    #     cls._sync_client_instance = cls._sync_client_(
    #         api_key=os.getenv(cls._env_key_name_), base_url=cls._base_url_
    #     )
    #     return cls._sync_client_instance

    # @classmethod
    # def async_client(cls):
    #     cls._async_client_instance = cls._async_client_(
    #         api_key=os.getenv(cls._env_key_name_), base_url=cls._base_url_
    #     )
    #     return cls._async_client_instance

    # @classmethod
    # def sync_client(cls):
    #     return cls._sync_client_(
    #         api_key=os.getenv(cls._env_key_name_), base_url=cls._base_url_
    #     )

    # @classmethod
    # def async_client(cls):
    #     return cls._async_client_(
    #         api_key=os.getenv(cls._env_key_name_), base_url=cls._base_url_
    #     )

    # TODO: Make this a coop call
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
    def get_model_list(cls):
        raw_list = cls.sync_client().models.list()
        if hasattr(raw_list, "data"):
            return raw_list.data
        else:
            return raw_list

    @classmethod
    def available(cls) -> List[str]:
        # from openai import OpenAI

        if not cls._models_list_cache:
            try:
                # client = OpenAI(api_key = os.getenv(cls._env_key_name_), base_url = cls._base_url_)
                cls._models_list_cache = [
                    m.id
                    for m in cls.get_model_list()
                    if m.id not in cls.model_exclude_list
                ]
            except Exception as e:
                raise
                # print(
                #     f"""Error retrieving models: {e}.
                #     See instructions about storing your API keys: https://docs.expectedparrot.com/en/latest/api_keys.html"""
                # )
                # cls._models_list_cache = [
                #     "gpt-3.5-turbo",
                #     "gpt-4-1106-preview",
                #     "gpt-4",
                # ]  # Fallback list
        return cls._models_list_cache

    @classmethod
    def create_model(cls, model_name, model_class_name=None) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with OpenAI models
            """

            key_sequence = cls.key_sequence
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

            def sync_client(self):
                return cls.sync_client()

            def async_client(self):
                return cls.async_client()

            @classmethod
            def available(cls) -> list[str]:
                # import openai
                # client = openai.OpenAI(api_key = os.getenv(cls._env_key_name_), base_url = cls._base_url_)
                # return client.models.list()
                return cls.sync_client().models.list()

            def get_headers(self) -> dict[str, Any]:
                # from openai import OpenAI

                # client = OpenAI(api_key = os.getenv(cls._env_key_name_), base_url = cls._base_url_)
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

                except Exception as e:
                    return {
                        "rpm": 10_000,
                        "tpm": 2_000_000,
                    }
                else:
                    return {
                        "rpm": int(headers["x-ratelimit-limit-requests"]),
                        "tpm": int(headers["x-ratelimit-limit-tokens"]),
                    }

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                encoded_image=None,
            ) -> dict[str, Any]:
                """Calls the OpenAI API and returns the API response."""
                if encoded_image:
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
                # self.client = AsyncOpenAI(
                #     api_key = os.getenv(cls._env_key_name_),
                #     base_url = cls._base_url_
                #     )
                client = self.async_client()
                params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content},
                    ],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "top_p": self.top_p,
                    "frequency_penalty": self.frequency_penalty,
                    "presence_penalty": self.presence_penalty,
                    "logprobs": self.logprobs,
                    "top_logprobs": self.top_logprobs if self.logprobs else None,
                }
                response = await client.chat.completions.create(**params)
                return response.model_dump()

        LLM.__name__ = "LanguageModel"

        return LLM
