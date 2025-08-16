# import os
from typing import Any, Dict, Optional, TYPE_CHECKING
from google import genai
from google.genai import types

# from ...exceptions.general import MissingAPIKeyError
from ..inference_service_abc import InferenceServiceABC

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
        return list(genai.list_models())

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

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional["Files"] = None,
            ) -> Dict[str, Any]:

                if files_list is None:
                    files_list = []

                client = genai.Client(api_key=self.api_token)

                if system_prompt is not None and system_prompt != "":
                    if self._model_ == "gemini-pro":
                        system_instruction = system_prompt
                    else:
                        print(
                            f"This model, {self._model_}, does not support system_instruction"
                        )
                        print("Will add system_prompt to user_prompt")
                        user_prompt = f"{system_prompt}\n{user_prompt}"
                        system_instruction = None
                else:
                    # No system prompt
                    system_instruction = None

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
                    gen_ai_file = client.files.get(name=google_file_info["name"])
                    combined_prompt.append(gen_ai_file)

                generation_config = types.GenerateContentConfig(
                    temperature=self.temperature,
                    top_p=self.topP,
                    top_k=self.topK,
                    max_output_tokens=self.maxOutputTokens,
                    stop_sequences=self.stopSequences,
                    safety_settings=[
                        types.SafetySetting(
                            category=setting["category"],
                            threshold=setting["threshold"],
                        )
                        for setting in safety_settings
                    ],
                    system_instruction=system_instruction,
                )

                try:
                    # print("Making LLM api call")
                    response = await client.aio.models.generate_content(
                        model=self._model_,
                        contents=combined_prompt,
                        config=generation_config,
                    )

                except Exception as e:
                    return {"message": str(e)}
                return response.model_dump(mode="json")

        LLM.__name__ = model_name
        return LLM


if __name__ == "__main__":
    pass
