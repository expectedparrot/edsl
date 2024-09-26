import os
from typing import Any, Dict, List
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from edsl.exceptions import MissingAPIKeyError
from edsl.language_models.LanguageModel import LanguageModel
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


# \'usage_metadata\': {\'prompt_token_count\': 5, \'candidates_token_count\':
class GoogleService(InferenceServiceABC):
    _inference_service_ = "google"
    key_sequence = ["candidates", 0, "content", "parts", 0, "text"]
    usage_sequence = ["usage_metadata"]
    input_token_name = "prompt_token_count"
    output_token_name = "candidates_token_count"

    model_exclude_list = []

    @classmethod
    def available(cls) -> List[str]:
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

            api_token = None
            model = None

            @classmethod
            def initialize(cls):
                if cls.api_token is None:
                    cls.api_token = os.getenv("GOOGLE_API_KEY")
                    if not cls.api_token:
                        raise MissingAPIKeyError(
                            "GOOGLE_API_KEY environment variable is not set"
                        )
                    genai.configure(api_key=cls.api_token)
                    cls.generative_model = genai.GenerativeModel(cls._model_)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.initialize()

            def get_generation_config(self) -> GenerationConfig:
                return GenerationConfig(
                    temperature=self.temperature,
                    top_p=self.topP,
                    top_k=self.topK,
                    max_output_tokens=self.maxOutputTokens,
                    stop_sequences=self.stopSequences,
                )

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str = ""
            ) -> Dict[str, Any]:
                generation_config = self.get_generation_config()

                # Combine system and user prompts
                combined_prompt = []
                if system_prompt:
                    combined_prompt.append(
                        {"role": "system", "parts": [{"text": system_prompt}]}
                    )
                combined_prompt.append(
                    {"role": "user", "parts": [{"text": user_prompt}]}
                )

                response = await self.generative_model.generate_content_async(
                    contents=combined_prompt, generation_config=generation_config
                )
                return response.to_dict()

        LLM.__name__ = model_name
        return LLM


if __name__ == "__main__":
    pass
