import os
import aiohttp
import json
from typing import Any
from edsl.exceptions import MissingAPIKeyError
from edsl.language_models.LanguageModel import LanguageModel

from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


class GoogleService(InferenceServiceABC):
    _inference_service_ = "google"
    key_sequence = ["candidates", 0, "content", "parts", 0, "text"]
    usage_sequence = ["usageMetadata"]
    input_token_name = "promptTokenCount"
    output_token_name = "candidatesTokenCount"

    model_exclude_list = []

    @classmethod
    def available(cls):
        return ["gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"]

    @classmethod
    def create_model(
        cls, model_name: str = "gemini-pro", model_class_name=None
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            _model_ = model_name
            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            _inference_service_ = cls._inference_service_

            _tpm = cls.get_tpm(cls)
            _rpm = cls.get_rpm(cls)

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
                print(combined_prompt)
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, headers=headers, data=json.dumps(data)
                    ) as response:
                        raw_response_text = await response.text()
                        return json.loads(raw_response_text)

        LLM.__name__ = model_name

        return LLM


if __name__ == "__main__":
    pass
