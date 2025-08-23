# import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import google
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from google.api_core.exceptions import InvalidArgument

# from ...exceptions.general import MissingAPIKeyError
from ..inference_service_abc import InferenceServiceABC

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ....scenarios.file_store import FileStore as Files
# from ...coop import Coop

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
                "candidateCount": 1,
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
                    candidate_count=getattr(self, 'candidateCount', 1),
                )

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional["Files"] = None,
            ) -> Dict[str, Any]:
                if files_list is None:
                    files_list = []
                genai.configure(api_key=self.api_token)
                
                # Setup generative model
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

                # Handle candidateCount parameter with batching support for candidateCount > 8
                candidate_count = getattr(self, 'candidateCount', 1)
                if candidate_count <= 8:
                    # Single API call with candidateCount parameter
                    generation_config = self.get_generation_config()
                    try:
                        response = await self.generative_model.generate_content_async(
                            combined_prompt, generation_config=generation_config
                        )
                        return response.to_dict()
                    except Exception as e:
                        return {"message": str(e)}
                else:
                    # Need to batch requests since Google supports max candidateCount=8
                    import asyncio
                    
                    # Calculate batch sizes
                    batch_size = 8
                    num_batches = (candidate_count + batch_size - 1) // batch_size  # Ceiling division
                    
                    all_candidates = []
                    total_usage = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}
                    
                    try:
                        # Create tasks for all batches
                        tasks = []
                        for i in range(num_batches):
                            remaining = candidate_count - i * batch_size
                            current_batch_size = min(batch_size, remaining)
                            
                            # Create generation config for this batch
                            batch_generation_config = GenerationConfig(
                                temperature=self.temperature,
                                top_p=self.topP,
                                top_k=self.topK,
                                max_output_tokens=self.maxOutputTokens,
                                stop_sequences=self.stopSequences,
                                candidate_count=current_batch_size,
                            )
                            
                            tasks.append(
                                self.generative_model.generate_content_async(
                                    combined_prompt, generation_config=batch_generation_config
                                )
                            )
                        
                        # Execute all batches concurrently
                        batch_responses = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Combine results
                        for batch_response in batch_responses:
                            if isinstance(batch_response, Exception):
                                return {"message": str(batch_response)}
                            
                            batch_data = batch_response.to_dict()
                            all_candidates.extend(batch_data.get("candidates", []))
                            
                            # Aggregate usage statistics
                            if "usage_metadata" in batch_data:
                                usage = batch_data["usage_metadata"]
                                # Only count prompt tokens once for the first batch
                                if len(all_candidates) == len(batch_data.get("candidates", [])):  # First batch
                                    total_usage["prompt_token_count"] = usage.get("prompt_token_count", 0)
                                total_usage["candidates_token_count"] += usage.get("candidates_token_count", 0)
                        
                        # Calculate total tokens
                        total_usage["total_token_count"] = (
                            total_usage["prompt_token_count"] + total_usage["candidates_token_count"]
                        )
                        
                        # Return combined response in Google format
                        first_response = batch_responses[0].to_dict()
                        combined_response = first_response.copy()
                        combined_response["candidates"] = all_candidates
                        combined_response["usage_metadata"] = total_usage
                        
                        return combined_response
                        
                    except Exception as e:
                        return {"message": str(e)}

        LLM.__name__ = model_name
        return LLM


if __name__ == "__main__":
    pass
