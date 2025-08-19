import os
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
            _cached_client = None
            _cached_api_token = None
            _client_lock = None

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if self._client_lock is None:
                    import asyncio

                    self._client_lock = asyncio.Lock()

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional["Files"] = None,
            ) -> Dict[str, Any]:
                import time

                method_start = time.time()

                if files_list is None:
                    files_list = []

                # Get or create cached client (thread-safe)
                client_start = time.time()
                async with self._client_lock:
                    if (
                        self._cached_client is None
                        or self._cached_api_token != self.api_token
                    ):
                        # print("Creating new Google client...", flush=True)
                        creation_start = time.time()
                        self._cached_client = genai.Client(api_key=self.api_token)
                        self._cached_api_token = self.api_token
                        creation_time = time.time() - creation_start
                        client_time = time.time() - client_start
                        # print(
                        #     f"Google client creation took {creation_time:.3f}s (total with lock: {client_time:.3f}s)",
                        #     flush=True,
                        # )
                    else:
                        client_time = time.time() - client_start
                        # print(
                        #     f"Using cached Google client (took {client_time:.3f}s)",
                        #     flush=True,
                        # )

                client = self._cached_client

                # Time prompt processing
                prompt_start = time.time()
                if system_prompt is not None and system_prompt != "":
                    if self._model_ != "gemini-pro":
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
                prompt_time = time.time() - prompt_start
                # print(f"Prompt processing took {prompt_time:.3f}s", flush=True)

                # Time file processing
                file_start = time.time()
                # print(f"Processing {len(files_list)} files", flush=True)

                # Use the file upload cache to handle uploads efficiently
                from ...scenarios.file_upload_cache import file_upload_cache

                for i, file in enumerate(files_list):
                    file_upload_start = time.time()
                    # Use cache to get or upload the file
                    # This ensures each unique file is only uploaded once
                    google_file_info = await file_upload_cache.get_or_upload(
                        file, service="google"
                    )
                    file_upload_time = time.time() - file_upload_start
                    # print(
                    #     f"File {i+1} upload/cache took {file_upload_time:.3f}s",
                    #     flush=True,
                    # )

                    # print("gogole file info is",google_file_info)
                    # Create the Google AI file reference using native async API
                    file_ref_start = time.time()
                    try:
                        gen_ai_file = await client.aio.files.get(
                            name=google_file_info["name"]
                        )
                        combined_prompt.append(gen_ai_file)
                        file_ref_time = time.time() - file_ref_start
                        # print(
                        #     f"File {i+1} reference creation took {file_ref_time:.3f}s",
                        #     flush=True,
                        # )
                    except Exception as e:
                        file_ref_time = time.time() - file_ref_start
                        # print(
                        #     f"File {i+1} reference creation failed after {file_ref_time:.3f}s: {str(e)}",
                        #     flush=True,
                        # )
                        raise Exception(
                            f"Failed to create file reference for {google_file_info['name']}: {str(e)}"
                        )

                file_total_time = time.time() - file_start
                # print(f"Total file processing took {file_total_time:.3f}s", flush=True)

                # Time config creation
                config_start = time.time()
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
                config_time = time.time() - config_start
                # print(f"Configuration creation took {config_time:.3f}s", flush=True)

                # Time API call
                api_start = time.time()
                try:
                    # print(
                    #     f"Making async API call to {self._model_} with {len(combined_prompt)} prompt parts",
                    #     flush=True,
                    # )
                    response = await client.aio.models.generate_content(
                        model=self._model_,
                        contents=combined_prompt,
                        config=generation_config,
                    )
                    api_time = time.time() - api_start
                    # print(f"Async API call completed in {api_time:.3f}s", flush=True)

                except Exception as e:
                    api_time = time.time() - api_start
                    # print(
                    #     f"Async API call failed after {api_time:.3f}s: {str(e)}",
                    #     flush=True,
                    # )
                    return {"message": str(e)}

                # Time response processing
                response_start = time.time()
                result = response.model_dump(mode="json")
                response_time = time.time() - response_start
                # print(f"Response processing took {response_time:.3f}s", flush=True)

                # Print total method time
                total_time = time.time() - method_start
                # print(
                #     f"Total async_execute_model_call took {total_time:.3f}s", flush=True
                # )

                return result

        LLM.__name__ = model_name
        return LLM


if __name__ == "__main__":
    pass
