import os
from typing import Any, Optional, List, TYPE_CHECKING
from anthropic import AsyncAnthropic

from ..inference_service_abc import InferenceServiceABC
from ...language_models import LanguageModel

if TYPE_CHECKING:
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
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

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
                        encoded_image = file_entry.base64_string
                        messages[0]["content"].append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": file_entry.mime_type,
                                    "data": encoded_image,
                                },
                            }
                        )
                # breakpoint()
                client = AsyncAnthropic(api_key=self.api_token)

                try:
                    response = await client.messages.create(
                        model=model_name,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        system=system_prompt,  # note that the Anthropic API uses "system" parameter rather than put it in the message
                        messages=messages,
                    )
                except Exception as e:
                    return {"message": str(e)}
                return response.model_dump()

        LLM.__name__ = model_class_name

        return LLM
