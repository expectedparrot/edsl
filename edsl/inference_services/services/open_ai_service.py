from __future__ import annotations
from typing import Any, List, Optional, Dict, NewType, TYPE_CHECKING
import os

import openai

from ..inference_service_abc import InferenceServiceABC

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
from ..rate_limits_cache import rate_limits

if TYPE_CHECKING:
    from ....scenarios.file_store import FileStore as Files
    from ....invigilators.invigilator_base import InvigilatorBase as InvigilatorAI


APIToken = NewType("APIToken", str)


class OpenAIService(InferenceServiceABC):
    """OpenAI service class."""

    _inference_service_ = "openai"
    _env_key_name_ = "OPENAI_API_KEY"
    _base_url_ = None

    _sync_client_ = openai.OpenAI
    _async_client_ = openai.AsyncOpenAI

    _sync_client_instances: Dict[APIToken, openai.OpenAI] = {}
    _async_client_instances: Dict[APIToken, openai.AsyncOpenAI] = {}

    key_sequence = ["choices", 0, "message", "content"]
    usage_sequence = ["usage"]
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"

    available_models_url = "https://platform.openai.com/docs/models/gp"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # so subclasses that use the OpenAI api key have to create their own instances of the clients
        cls._sync_client_instances = {}
        cls._async_client_instances = {}

    @classmethod
    def sync_client(cls, api_key):
        if api_key not in cls._sync_client_instances:
            client = cls._sync_client_(
                api_key=api_key,
                base_url=cls._base_url_,
            )
            cls._sync_client_instances[api_key] = client
        client = cls._sync_client_instances[api_key]
        return client

    @classmethod
    def async_client(cls, api_key):
        if api_key not in cls._async_client_instances:
            client = cls._async_client_(
                api_key=api_key,
                base_url=cls._base_url_,
            )
            cls._async_client_instances[api_key] = client
        client = cls._async_client_instances[api_key]
        return client

    model_exclude_list = [
        "whisper-1",
        "davinci-002",
        "dall-e-2",
        "tts-1-hd-1106",
        "tts-1-hd",
        "dall-e-3",
        "tts-1",
        "babbage-002",
        "tts-1-1106",
        "text-embedding-3-large",
        "text-embedding-3-small",
        "text-embedding-ada-002",
        "ft:davinci-002:mit-horton-lab::8OfuHgoo",
        "gpt-3.5-turbo-instruct-0914",
        "gpt-3.5-turbo-instruct",
    ]
    _models_list_cache: List[str] = []

    @classmethod
    def get_model_list(cls, api_key=None):
        # breakpoint()
        if api_key is None:
            api_key = os.getenv(cls._env_key_name_)
        raw_list = cls.sync_client(api_key).models.list()
        if hasattr(raw_list, "data"):
            return raw_list.data
        else:
            return raw_list

    @classmethod
    def available(cls, api_token=None) -> List[str]:
        if api_token is None:
            api_token = os.getenv(cls._env_key_name_)
        if not cls._models_list_cache:
            try:
                cls._models_list_cache = [
                    m.id
                    for m in cls.get_model_list(api_key=api_token)
                    if m.id not in cls.model_exclude_list
                ]
            except Exception:
                raise
        return cls._models_list_cache

    @classmethod
    def create_model(cls, model_name, model_class_name=None) -> "LanguageModel":
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
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 1000,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "logprobs": False,
                "top_logprobs": 3,
            }

            def sync_client(self):
                return cls.sync_client(api_key=self.api_token)

            def async_client(self):
                return cls.async_client(api_key=self.api_token)

            @classmethod
            def available(cls) -> list[str]:
                return cls.sync_client().models.list()

            def get_headers(self) -> dict[str, Any]:
                client = self.sync_client()
                response = client.chat.completions.with_raw_response.create(
                    messages=[
                        {
                            "role": "user",
                            "content": "Say this is a test",
                        }
                    ],
                    model=self.model,
                )
                return dict(response.headers)

            def get_rate_limits(self) -> dict[str, Any]:
                try:
                    if "openai" in rate_limits:
                        headers = rate_limits["openai"]

                    else:
                        headers = self.get_headers()

                except Exception:
                    return {
                        "rpm": 10_000,
                        "tpm": 2_000_000,
                    }
                else:
                    return {
                        "rpm": int(headers["x-ratelimit-limit-requests"]),
                        "tpm": int(headers["x-ratelimit-limit-tokens"]),
                    }

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                question_name: Optional[str] = None,
                files_list: Optional[List["Files"]] = None,
                invigilator: Optional[
                    "InvigilatorAI"
                ] = None,  # TBD - can eventually be used for function-calling
            ) -> dict[str, Any]:
                """Calls the OpenAI API and returns the API response."""
                import base64
                import io
                
                # Check if this is a reasoning model with file limitations
                is_reasoning_model = "o1" in self.model or "o3" in self.model
                is_o1_mini = "o1-mini" in self.model
                
                if files_list:
                    # Handle reasoning model limitations
                    if is_reasoning_model:
                        if is_o1_mini:
                            # o1-mini only supports text - no files at all
                            content = f"{user_prompt}\n\n[Note: Files were provided but o1-mini only supports text inputs. Please extract and include the relevant text content in your prompt instead.]"
                        else:
                            # o1 reasoning models - attempt file processing
                            content = [{"type": "text", "text": user_prompt}]
                            for file_entry in files_list:
                                # Check for PDF MIME types (could be various formats)
                                is_pdf = (
                                    file_entry.mime_type == "application/pdf" or
                                    file_entry.mime_type == "application/x-pdf" or
                                    file_entry.mime_type == "text/pdf" or
                                    'pdf' in file_entry.mime_type.lower() or
                                    (hasattr(file_entry, 'filename') and 
                                     getattr(file_entry, 'filename', '').lower().endswith('.pdf'))
                                )
                                
                                if is_pdf:
                                    # Try image_url format first for reasoning models
                                    try:
                                        content.append({
                                            "type": "image_url", 
                                            "image_url": {
                                                "url": f"data:application/pdf;base64,{file_entry.base64_string}"
                                            }
                                        })
                                    except Exception:
                                        # Fallback to extracted text for reasoning models
                                        if hasattr(file_entry, 'extracted_text') and file_entry.extracted_text:
                                            content.append({
                                                "type": "text",
                                                "text": f"\n--- PDF Content from '{getattr(file_entry, 'filename', 'document.pdf')}' ---\n{file_entry.extracted_text}\n--- End of PDF Content ---\n"
                                            })
                                        else:
                                            content.append({
                                                "type": "text",
                                                "text": f"\n[PDF file '{getattr(file_entry, 'filename', 'document.pdf')}' could not be processed - no extracted text available.]"
                                            })
                                elif file_entry.mime_type.startswith('image/'):
                                    # Images should work with o1 models
                                    content.append({
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{file_entry.mime_type};base64,{file_entry.base64_string}"
                                        },
                                    })
                                else:
                                    # Other file types - add informational message
                                    content.append({
                                        "type": "text",
                                        "text": f"\n[File '{getattr(file_entry, 'filename', 'unknown')}' of type '{file_entry.mime_type}' provided but not directly supported by reasoning models.]"
                                    })
                    else:
                        # Regular models - use the original logic
                        content = [{"type": "text", "text": user_prompt}]
                        for file_entry in files_list:
                            # Check for PDF MIME types (could be various formats)
                            is_pdf = (
                                file_entry.mime_type == "application/pdf" or
                                file_entry.mime_type == "application/x-pdf" or
                                file_entry.mime_type == "text/pdf" or
                                'pdf' in file_entry.mime_type.lower() or
                                (hasattr(file_entry, 'filename') and 
                                 getattr(file_entry, 'filename', '').lower().endswith('.pdf'))
                            )
                            
                            if is_pdf:
                                # For PDFs, we need to upload the file first and use file_id
                                try:
                                    # Convert base64 back to bytes for upload
                                    pdf_bytes = base64.b64decode(file_entry.base64_string)
                                    pdf_file = io.BytesIO(pdf_bytes)
                                    pdf_file.name = getattr(file_entry, 'filename', 'document.pdf')
                                    
                                    # Use sync client for file upload (files.create is not async in OpenAI client)
                                    sync_client = self.sync_client()
                                    uploaded_file = sync_client.files.create(
                                        file=pdf_file,
                                        purpose="user_data"
                                    )
                                    
                                    content.append({
                                        "type": "file",
                                        "file": {
                                            "file_id": uploaded_file.id,
                                        }
                                    })
                                except Exception as e:
                                    # Fallback approach: Try base64 PDF format (some users report this working)
                                    try:
                                        content.append({
                                            "type": "text",
                                            "text": f"Here is a PDF document (base64): data:application/pdf;base64,{file_entry.base64_string[:100]}... [truncated for brevity]"
                                        })
                                    except Exception as fallback_error:
                                        # Final fallback: add error message explaining the issue
                                        content.append({
                                            "type": "text", 
                                            "text": f"[PDF file could not be processed. Upload error: {str(e)}. Fallback error: {str(fallback_error)}. Please ensure the file is a valid PDF and OpenAI API supports PDF uploads.]"
                                        })
                            else:
                                # Handle images as before
                                content.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{file_entry.mime_type};base64,{file_entry.base64_string}"
                                        },
                                    }
                                )
                else:
                    content = user_prompt
                
                client = self.async_client()

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ]
                if (
                    (system_prompt == "" and self.omit_system_prompt_if_empty)
                    or "o1" in self.model
                    or "o3" in self.model
                ):
                    messages = messages[1:]

                params = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "top_p": self.top_p,
                    "frequency_penalty": self.frequency_penalty,
                    "presence_penalty": self.presence_penalty,
                    "logprobs": self.logprobs,
                    "top_logprobs": self.top_logprobs if self.logprobs else None,
                }
                if "o1" in self.model or "o3" in self.model:
                    params.pop("max_tokens")
                    # For reasoning models, use much higher completion tokens to allow for reasoning + response
                    reasoning_tokens = max(self.max_tokens, 5000)  # At least 5000 tokens for reasoning models
                    params["max_completion_tokens"] = reasoning_tokens
                    params["temperature"] = 1
                try:
                    response = await client.chat.completions.create(**params)
                except Exception as e:
                    error_message = str(e)
                    
                    # Check if this is a PDF-related error for reasoning models and we can fallback
                    if (is_reasoning_model and files_list and 
                        "unsupported MIME type 'application/pdf'" in error_message):
                        
                        # Rebuild content with extracted text instead of PDF
                        content = [{"type": "text", "text": user_prompt}]
                        for file_entry in files_list:
                            if 'pdf' in file_entry.mime_type.lower():
                                if hasattr(file_entry, 'extracted_text') and file_entry.extracted_text:
                                    # Truncate very long PDFs to avoid overwhelming reasoning models
                                    extracted_text = file_entry.extracted_text
                                    max_chars = 50000  # Limit to ~50k chars (roughly 12-15k tokens)
                                    if len(extracted_text) > max_chars:
                                        extracted_text = extracted_text[:max_chars] + f"\n\n[PDF truncated after {max_chars} characters due to length limits]"
                                    
                                    content.append({
                                        "type": "text",
                                        "text": f"\n--- PDF Content from '{getattr(file_entry, 'filename', 'document.pdf')}' ---\n{extracted_text}\n--- End of PDF Content ---\n"
                                    })
                                else:
                                    content.append({
                                        "type": "text",
                                        "text": f"\n[PDF file '{getattr(file_entry, 'filename', 'document.pdf')}' could not be processed - no extracted text available.]"
                                    })
                            elif file_entry.mime_type.startswith('image/'):
                                # Keep images as-is
                                content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{file_entry.mime_type};base64,{file_entry.base64_string}"
                                    },
                                })
                        
                        # Update the messages with the new content
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": content},
                        ]
                        if (
                            (system_prompt == "" and self.omit_system_prompt_if_empty)
                            or "o1" in self.model
                            or "o3" in self.model
                        ):
                            messages = messages[1:]
                        
                        # Update params with new messages
                        params["messages"] = messages
                        
                        # Ensure reasoning models get enough completion tokens in retry too
                        if "o1" in self.model or "o3" in self.model:
                            reasoning_tokens = max(self.max_tokens, 5000)
                            params["max_completion_tokens"] = reasoning_tokens
                        
                        try:
                            response = await client.chat.completions.create(**params)
                        except Exception as e2:
                            return {"message": f"Original error: {error_message}. Retry error: {str(e2)}"}
                    else:
                        return {"message": str(e)}
                return response.model_dump()

        LLM.__name__ = "LanguageModel"

        return LLM
