import os
from typing import Any, Dict, Optional, TYPE_CHECKING
from google import genai
from google.genai import types
import google

# from ...exceptions.general import MissingAPIKeyError
from ..inference_service_abc import InferenceServiceABC
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import InvalidArgument

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ...scenarios.file_store import FileStore as Files

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

    available_models_url = (
        "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models"
    )

    @classmethod
    def get_model_info(cls):
        """Get raw model info without wrapping in ModelInfo."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")

        client = genai.Client(api_key=api_key)
        response = client.models.list()
        model_list = list(response)
        return model_list

    @classmethod
    def create_model(
        cls, model_name: str = "gemini-pro", model_class_name=None
    ) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Import LanguageModel only when actually creating a model
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
                import time

                start = time.time()
                # print("Entering google file loads")

                # Use the file upload cache to handle uploads efficiently
                from ...scenarios.file_upload_cache import file_upload_cache

                for file in files_list:
                    # Use cache to get or upload the file
                    # This ensures each unique file is only uploaded once
                    google_file_info = await file_upload_cache.get_or_upload(
                        file, service="google"
                    )

                    # Create the Google AI file reference
                    gen_ai_file = google.generativeai.types.file_types.File(
                        google_file_info
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
