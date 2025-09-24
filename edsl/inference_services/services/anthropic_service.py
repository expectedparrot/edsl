import os
import base64
from typing import Any, Optional, List, TYPE_CHECKING
from anthropic import AsyncAnthropic

from ..inference_service_abc import InferenceServiceABC
from ..decorators import report_errors_async
from .message_builder import MessageBuilder

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
            Child class of LanguageModel for interacting with Anthropic models
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

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["Files"]] = None,
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> dict[str, Any]:
                """Calls the Anthropic API and returns the API response.

                Args:
                    user_prompt: The user message or input prompt
                    system_prompt: The system message or context
                    files_list: Optional list of files to include
                    cache_key: Optional cache key for tracking
                """

                # Check if we should use remote proxy
                if self.remote_proxy:
                    # Use remote proxy mode
                    from .remote_proxy_handler import RemoteProxyHandler

                    handler = RemoteProxyHandler(
                        model=self.model,
                        inference_service=self._inference_service_,
                        job_uuid=getattr(self, "job_uuid", None),
                    )

                    # Get fresh parameter
                    fresh_value = getattr(self, "fresh", False)

                    return await handler.execute_model_call(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt,
                        files_list=files_list,
                        cache_key=cache_key,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        top_p=self.top_p,
                        frequency_penalty=self.frequency_penalty,
                        presence_penalty=self.presence_penalty,
                        logprobs=self.logprobs,
                        top_logprobs=self.top_logprobs,
                        fresh=fresh_value,  # Pass fresh parameter
                    )

                messages = [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    }
                ]
                if files_list:
                    # Create a MessageBuilder instance to use its helper methods
                    msg_builder = MessageBuilder(model=model_name)

                    for file_entry in files_list:
                        # Handle text files by including their decoded content
                        if msg_builder._is_text_file(file_entry):
                            text_content = msg_builder.decode_text_file(file_entry)
                            filename = getattr(file_entry, "filename", "text_file")
                            messages[0]["content"].append(
                                {
                                    "type": "text",
                                    "text": f"\n--- Content from '{filename}' ---\n{text_content}\n--- End of {filename} ---\n",
                                }
                            )
                        # Handle PDFs as documents
                        elif msg_builder._is_pdf_file(file_entry):
                            encoded_data = file_entry.base64_string
                            messages[0]["content"].append(
                                {
                                    "type": "document",
                                    "source": {
                                        "type": "base64",
                                        "media_type": file_entry.mime_type,
                                        "data": encoded_data,
                                    },
                                }
                            )
                        # Handle images
                        elif msg_builder._is_image_file(file_entry):
                            encoded_data = file_entry.base64_string
                            messages[0]["content"].append(
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": file_entry.mime_type,
                                        "data": encoded_data,
                                    },
                                }
                            )
                        # Handle unsupported file types
                        else:
                            filename = getattr(file_entry, "filename", "unknown")
                            messages[0]["content"].append(
                                {
                                    "type": "text",
                                    "text": f"[Unsupported file '{filename}' of type '{file_entry.mime_type}'. File content cannot be processed.]",
                                }
                            )
                client = AsyncAnthropic(api_key=self.api_token)

                response = await client.messages.create(
                    model=model_name,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=system_prompt,  # note that the Anthropic API uses "system" parameter rather than put it in the message
                    messages=messages,
                )
                return response.model_dump()

        LLM.__name__ = model_class_name

        return LLM
