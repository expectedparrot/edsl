import os
from typing import Any, List
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models.LanguageModel import LanguageModel
import asyncio
from mistralai import Mistral


class MistralAIService(InferenceServiceABC):
    """Mistral AI service class."""

    # key_sequence = ["content", 0, "text"]  # ["content"][0]["text"]
    key_sequence = ["choices", 0, "message", "content"]
    _inference_service_ = "mistral"
    _env_key_name_ = "MISTRAL_API_KEY"  # Environment variable for Mistral API key

    _sync_client_instance = None
    _async_client_instance = None

    _sync_client = Mistral
    _async_client = Mistral

    _models_list_cache: List[str] = []
    model_exclude_list = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # so subclasses have to create their own instances of the clients
        cls._sync_client_instance = None
        cls._async_client_instance = None

    @classmethod
    def sync_client(cls):
        if cls._sync_client_instance is None:
            cls._sync_client_instance = cls._sync_client(
                api_key=os.getenv(cls._env_key_name_)
            )
        return cls._sync_client_instance

    @classmethod
    def async_client(cls):
        if cls._async_client_instance is None:
            cls._async_client_instance = cls._async_client(
                api_key=os.getenv(cls._env_key_name_)
            )
        return cls._async_client_instance

    @classmethod
    def available(cls) -> list[str]:
        if not cls._models_list_cache:
            cls._models_list_cache = [
                m.id for m in cls.sync_client().models.list().data
            ]

        return cls._models_list_cache

    @classmethod
    def create_model(
        cls, model_name: str = "mistral", model_class_name=None
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with Mistral models.
            """

            key_sequence = cls.key_sequence
            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 512,
                "top_p": 0.9,
            }

            def sync_client(self):
                return cls.sync_client()

            def async_client(self):
                return cls.async_client()

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str = ""
            ) -> dict[str, Any]:
                """Calls the Mistral API and returns the API response."""
                s = self.async_client()

                res = await s.chat.complete_async(
                    model=model_name,
                    messages=[
                        {
                            "content": user_prompt,
                            "role": "user",
                        },
                    ],
                )

                return res.model_dump()

        LLM.__name__ = model_class_name

        return LLM
