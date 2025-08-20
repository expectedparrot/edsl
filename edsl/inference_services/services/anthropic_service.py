import os
from typing import Any, Optional, List, TYPE_CHECKING
from anthropic import AsyncAnthropic

from ..inference_service_abc import InferenceServiceABC

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ...scenarios.file_store import FileStore as Files


class AnthropicService(InferenceServiceABC):
    """Anthropic service class."""

    _inference_service_ = "anthropic"
    _env_key_name_ = "ANTHROPIC_API_KEY"
    key_sequence = ["content", 0, "text"]
    usage_sequence = ["usage"]
    input_token_name = "input_tokens"
    output_token_name = "output_tokens"
    available_models_url = "https://docs.anthropic.com/en/docs/about-claude/models"

    @classmethod
    def get_model_info(cls, api_key: Optional[str] = None):
        """Get raw model info without wrapping in ModelInfo."""
        import requests

        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        response = requests.get("https://api.anthropic.com/v1/models", headers=headers)
        response.raise_for_status()
        return response.json()["data"]

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

                try:
                    response = await client.messages.create(
                        model=model_name,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        system=system_prompt,  # note that the Anthropic API uses "system" parameter rather than put it in the message
                        messages=messages,
                    )
                    return response.model_dump()
                except Exception as e:
                    from ...coop import Coop 
                    c = Coop()
                    c.report_error(e)
                    #breakpoint()
                    raise e

        LLM.__name__ = model_class_name

        return LLM
