from typing import Any
import re
from openai import AsyncOpenAI

from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel


class OpenAIService(InferenceServiceABC):
    """OpenAI service class."""

    _inference_service_ = "openai"
    _env_key_name_ = "OPENAI_API_KEY"

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
    ]

    @classmethod
    def available(cls):
        try:
            from openai import OpenAI

            client = OpenAI()
            return [
                m.id for m in client.models.list() if m.id not in cls.model_exclude_list
            ]
        except Exception as e:
            return ["gpt-3.5-turbo", "gpt-4-1106-preview", "gpt-4"]

    @classmethod
    def create_model(cls, model_name, model_class_name=None) -> LanguageModel:
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

            @classmethod
            def available(cls) -> list[str]:
                client = openai.OpenAI()
                return client.models.list()

            def get_headers(self) -> dict[str, Any]:
                from openai import OpenAI

                client = OpenAI()
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
                self, user_prompt: str, system_prompt: str = ""
            ) -> dict[str, Any]:
                """Calls the OpenAI API and returns the API response."""
                self.client = AsyncOpenAI()
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    frequency_penalty=self.frequency_penalty,
                    presence_penalty=self.presence_penalty,
                    logprobs=self.logprobs,
                    top_logprobs=self.top_logprobs if self.logprobs else None,
                )
                return response.model_dump()

            @staticmethod
            def parse_response(raw_response: dict[str, Any]) -> str:
                """Parses the API response and returns the response text."""
                response = raw_response["choices"][0]["message"]["content"]
                pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
                match = re.match(pattern, response, re.DOTALL)
                if match:
                    return match.group(1)
                else:
                    return response

        LLM.__name__ = "LanguageModel"

        return LLM
