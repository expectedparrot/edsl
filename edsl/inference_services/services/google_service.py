# import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import google
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import InvalidArgument

# from ...exceptions.general import MissingAPIKeyError
from ..inference_service_abc import InferenceServiceABC
from ...language_models import LanguageModel

if TYPE_CHECKING:
    from ....scenarios.file_store import FileStore as Files
#from ...coop import Coop

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
]


class GoogleService(InferenceServiceABC):
    _inference_service_ = "google"
    key_sequence = ["candidates", 0, "content", "parts", 0, "text"]
    usage_sequence = ["usage_metadata"]
    input_token_name = "prompt_token_count"
    output_token_name = "candidates_token_count"

    model_exclude_list = []

    available_models_url = (
        "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models"
    )

    @classmethod
    def get_model_list(cls):
        model_list = []
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                model_list.append(m.name.split("/")[-1])
        return model_list

    @classmethod
    def available(cls) -> List[str]:
        return cls.get_model_list()

    @classmethod
    def create_model(
        cls, model_name: str = "gemini-pro", model_class_name=None
    ) -> 'LanguageModel':
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            _model_ = model_name
            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            _inference_service_ = cls._inference_service_

            _parameters_ = {
                "temperature": 0.5,
                "topP": 1,
                "topK": 1,
                "maxOutputTokens": 2048,
                "stopSequences": [],
            }

            model = None

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            def get_generation_config(self) -> GenerationConfig:
                return GenerationConfig(
                    temperature=self.temperature,
                    top_p=self.topP,
                    top_k=self.topK,
                    max_output_tokens=self.maxOutputTokens,
                    stop_sequences=self.stopSequences,
                )

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional["Files"] = None,
            ) -> Dict[str, Any]:
                generation_config = self.get_generation_config()

                if files_list is None:
                    files_list = []
                genai.configure(api_key=self.api_token)
                if (
                    system_prompt is not None
                    and system_prompt != ""
                    and self._model_ != "gemini-pro"
                ):
                    try:
                        self.generative_model = genai.GenerativeModel(
                            self._model_,
                            safety_settings=safety_settings,
                            system_instruction=system_prompt,
                        )
                    except InvalidArgument:
                        print(
                            f"This model, {self._model_}, does not support system_instruction"
                        )
                        print("Will add system_prompt to user_prompt")
                        user_prompt = f"{system_prompt}\n{user_prompt}"
                else:
                    self.generative_model = genai.GenerativeModel(
                        self._model_,
                        safety_settings=safety_settings,
                    )
                combined_prompt = [user_prompt]
                for file in files_list:
                    if "google" not in file.external_locations:
                        _ = file.upload_google()
                    gen_ai_file = google.generativeai.types.file_types.File(
                        file.external_locations["google"]
                    )
                    combined_prompt.append(gen_ai_file)

                try:
                    response = await self.generative_model.generate_content_async(
                        combined_prompt, generation_config=generation_config
                    )
                except Exception as e:
                    return {"message": str(e)}
                return response.to_dict()

        LLM.__name__ = model_name
        return LLM


if __name__ == "__main__":
    pass
