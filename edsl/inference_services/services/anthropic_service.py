import os
from typing import Any, Optional, List, TYPE_CHECKING
from anthropic import AsyncAnthropic

from ..inference_service_abc import InferenceServiceABC

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ....scenarios.file_store import FileStore as Files


class AnthropicService(InferenceServiceABC):
    """Anthropic service class."""

    _inference_service_ = "anthropic"
    _env_key_name_ = "ANTHROPIC_API_KEY"
    key_sequence = ["content", 0, "text"]
    usage_sequence = ["usage"]
    input_token_name = "input_tokens"
    output_token_name = "output_tokens"
    model_exclude_list = []

    available_models_url = "https://docs.anthropic.com/en/docs/about-claude/models"

    @classmethod
    def get_model_list(cls, api_key: str = None):
        import requests

        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        response = requests.get("https://api.anthropic.com/v1/models", headers=headers)
        model_names = [m["id"] for m in response.json()["data"]]
        return model_names

    @classmethod
    def available(cls):
        return cls.get_model_list()

    @classmethod
    def create_model(
        cls, model_name: str = "claude-3-opus-20240229", model_class_name=None
    ) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Import LanguageModel only when actually creating a model
        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with OpenAI models
            """

            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name

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
                "n": 1,
            }

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["Files"]] = None,
            ) -> dict[str, Any]:
                """Calls the Anthropic API and returns the API response."""

                messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    }
                ]
                if files_list:
                    for file_entry in files_list:
                        encoded_data = file_entry.base64_string

                        # Use "document" type for PDFs, "image" type for other files
                        content_type = (
                            "document"
                            if file_entry.mime_type == "application/pdf"
                            else "image"
                        )

                        messages[0]["content"].append(
                            {
                                "type": content_type,
                                "source": {
                                    "type": "base64",
                                    "media_type": file_entry.mime_type,
                                    "data": encoded_data,
                                },
                            }
                        )

                client = AsyncAnthropic(api_key=self.api_token)

                # Handle n parameter using multiple API calls (Anthropic doesn't support n natively)
                n_completions = getattr(self, 'n', 1)
                if n_completions == 1:
                    # Single API call
                    try:
                        response = await client.messages.create(
                            model=model_name,
                            max_tokens=self.max_tokens,
                            temperature=self.temperature,
                            system=system_prompt,
                            messages=messages,
                        )
                        return response.model_dump()
                    except Exception as e:
                        return {"message": str(e)}
                else:
                    # Multiple API calls since Anthropic doesn't support n parameter
                    import asyncio
                    
                    try:
                        # Create tasks for all completions
                        tasks = []
                        for _ in range(n_completions):
                            tasks.append(
                                client.messages.create(
                                    model=model_name,
                                    max_tokens=self.max_tokens,
                                    temperature=self.temperature,
                                    system=system_prompt,
                                    messages=messages,
                                )
                            )
                        
                        # Execute all calls concurrently
                        responses = await asyncio.gather(*tasks, return_exceptions=True)
                        
                        # Convert to OpenAI-like format for consistency
                        all_choices = []
                        total_usage = {"input_tokens": 0, "output_tokens": 0}
                        
                        for i, response in enumerate(responses):
                            if isinstance(response, Exception):
                                return {"message": str(response)}
                            
                            response_data = response.model_dump()
                            
                            # Convert Anthropic format to OpenAI-like format
                            choice = {
                                "index": i,
                                "message": {
                                    "role": "assistant",
                                    "content": response_data["content"][0]["text"]
                                },
                                "finish_reason": "stop" if response_data.get("stop_reason") == "end_turn" else response_data.get("stop_reason", "stop")
                            }
                            all_choices.append(choice)
                            
                            # Aggregate usage statistics
                            if "usage" in response_data:
                                usage = response_data["usage"]
                                # Only count input tokens once for the first response
                                if i == 0:
                                    total_usage["input_tokens"] = usage.get("input_tokens", 0)
                                total_usage["output_tokens"] += usage.get("output_tokens", 0)
                        
                        # Return combined response in OpenAI-like format for consistency
                        return {
                            "choices": all_choices,
                            "usage": {
                                "prompt_tokens": total_usage["input_tokens"],
                                "completion_tokens": total_usage["output_tokens"],
                                "total_tokens": total_usage["input_tokens"] + total_usage["output_tokens"]
                            },
                            "model": model_name,
                            "object": "chat.completion",
                        }
                        
                    except Exception as e:
                        return {"message": str(e)}

        LLM.__name__ = model_class_name

        return LLM
