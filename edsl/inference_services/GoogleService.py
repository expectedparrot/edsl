import os
import aiohttp
import json
from typing import Any
from edsl.exceptions import MissingAPIKeyError
from edsl.language_models.LanguageModel import LanguageModel

from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


class GoogleService(InferenceServiceABC):
    _inference_service_ = "google"

    @classmethod
    def available(cls):
        return ["gemini-pro"]

    @classmethod
    def create_model(
        cls, model_name: str = "gemini-pro", model_class_name=None
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            _model_ = model_name
            _inference_service_ = cls._inference_service_
            _parameters_ = {
                "temperature": 0.5,
                "topP": 1,
                "topK": 1,
                "maxOutputTokens": 2048,
                "stopSequences": [],
            }

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str = ""
            ) -> dict[str, Any]:
                # self.api_token = os.getenv("GOOGLE_API_KEY")
                combined_prompt = user_prompt + system_prompt
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_token}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": combined_prompt}]}],
                    "generationConfig": {
                        "temperature": self.temperature,
                        "topK": self.topK,
                        "topP": self.topP,
                        "maxOutputTokens": self.maxOutputTokens,
                        "stopSequences": self.stopSequences,
                    },
                }

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, headers=headers, data=json.dumps(data)
                    ) as response:
                        raw_response_text = await response.text()
                        return json.loads(raw_response_text)

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                data = raw_response
                return data["candidates"][0]["content"]["parts"][0]["text"]

        LLM.__name__ = model_name

        return LLM


if __name__ == "__main__":
    pass
