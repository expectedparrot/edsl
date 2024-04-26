import os
from typing import Any

from anthropic import AsyncAnthropic
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models.LanguageModel import LanguageModel


class AnthropicService(InferenceServiceABC):
    """Anthropic service class."""

    _inference_service_ = "anthropic"
    _env_key_name_ = "ANTHROPIC_API_KEY"

    @classmethod
    def available(cls):
        # TODO - replace with an API call
        return [
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

            @staticmethod
            def parse_response(raw_response: dict[str, Any]) -> str:
                """Parses the API response and returns the response text."""
                response = raw_response["content"][0]["text"]
                pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
                match = re.match(pattern, response, re.DOTALL)
                if match:
                    return match.group(1)
                else:
                    return response

        LLM.__name__ = model_class_name

        return LLM
