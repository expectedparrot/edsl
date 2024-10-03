import os
from typing import Any, Optional, List
import re
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
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["Files"]] = None,
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

        LLM.__name__ = model_class_name

        return LLM
