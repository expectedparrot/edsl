import os
from typing import Any, Optional, List, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

from azure.ai.inference.aio import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage, TextContentItem, ImageContentItem, ImageUrl

from ..inference_service_abc import InferenceServiceABC
from ..decorators import report_errors_async
from .service_enums import OPENAI_REASONING_MODELS

if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ...scenarios.file_store import FileStore


def json_handle_none(value: Any) -> Any:
    """
    Handle None values during JSON serialization.
    Returns "null" if value is None.
    """
    if value is None:
        return "null"


class AzureParameterBuilder:
    """Helper class to construct API parameters based on model type for Azure AI."""

    @staticmethod
    def build_params(model: str, messages: list, **model_params) -> dict:
        """Build API parameters, adjusting for specific model types."""

        default_max_tokens = model_params.get("max_tokens", 512)
        default_temperature = model_params.get("temperature", 0.5)

        # Check if this is a reasoning model (o1, o1-mini, etc.)
        # Extract the base model name from Azure model names
        base_model = model.replace("azure:", "")
        is_reasoning_model = any(
            reasoning_model in base_model for reasoning_model in OPENAI_REASONING_MODELS
        )

        if is_reasoning_model:
            # For reasoning models, only pass minimal parameters (no max tokens, no top_p)
            temperature = 1

            # For o1 models, only pass messages and temperature
            params = {
                "messages": messages,
                "temperature": temperature,
            }
        else:
            # For regular (non-o1) models, always use max_tokens regardless of type
            params = {
                "messages": messages,
                "temperature": default_temperature,
                "max_tokens": default_max_tokens,
                "top_p": model_params.get("top_p", 0.9),
            }

        return params


class AzureAIService(InferenceServiceABC):
    """Service class to interact with Azure AI models."""

    key_sequence = ["choices", 0, "message", "content"]
    usage_sequence = ["usage"]
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"

    _inference_service_ = "azure"
    _env_key_name_ = "AZURE_ENDPOINT_URL_AND_KEY"
    _models_list_cache: Optional[List[str]] = None
    _model_id_to_endpoint_and_key = {}

    model_exclude_list = [
        "Cohere-command-r-plus-xncmg",
        "Mistral-Nemo-klfsi",
        "Mistral-large-2407-ojfld",
    ]

    @classmethod
    def parse_data_from_key(cls, api_key: str):
        """Parse data from an Azure key."""
        models_info = []
        azure_endpoints = api_key.split(",")

        for data in azure_endpoints:
            try:
                # Handle different formats of AZURE_ENDPOINT_URL_AND_KEY
                # Format 1: "endpoint:key" (2 parts)
                # Format 2: "model:endpoint:key" (3 parts, legacy)

                # Find the last colon to separate key from endpoint
                last_colon_idx = data.rfind(":")
                if last_colon_idx == -1:
                    continue

                azure_endpoint_key = data[last_colon_idx + 1 :]
                endpoint_part = data[:last_colon_idx]

                # Check if there's a model prefix (legacy format)
                if endpoint_part.startswith("http://") or endpoint_part.startswith(
                    "https://"
                ):
                    # No model prefix, just endpoint
                    endpoint = endpoint_part
                else:
                    # Might have model prefix, check for another colon
                    first_colon_idx = endpoint_part.find(":")
                    if first_colon_idx != -1:
                        # Has model prefix (legacy format: model:endpoint)
                        endpoint = endpoint_part[first_colon_idx + 1 :]
                    else:
                        # No protocol, assume it needs https://
                        endpoint = f"https://{endpoint_part}"

                # Non-OpenAI Azure endpoint
                if "openai" not in endpoint:
                    # Extract model ID from the hostname
                    # For https://DeepSeek-R1-nqcfe.eastus2.models.ai.azure.com, we want DeepSeek-R1-nqcfe
                    parsed = urlparse(endpoint)
                    hostname = (
                        parsed.netloc or parsed.path
                    )  # Handle cases with/without protocol
                    model_id = hostname.split(".")[0]

                    # Remove protocol prefix if present
                    if "://" in model_id:
                        model_id = model_id.split("://")[-1]

                    model_data = {
                        "id": f"azure:{model_id}",
                        "endpoint": endpoint,
                        "type": "azure_non_openai",
                        "azure_endpoint_key": azure_endpoint_key,
                        "api_version": None,
                    }
                    models_info.append(model_data)
                    cls._model_id_to_endpoint_and_key[f"azure:{model_id}"] = model_data
                    continue

                # Azure OpenAI endpoint
                if "/deployments/" in endpoint:
                    start_idx = endpoint.index("/deployments/") + len("/deployments/")
                    end_idx = endpoint.find("/", start_idx)
                    end_idx = end_idx if end_idx != -1 else len(endpoint)
                    model_id = endpoint[start_idx:end_idx]

                    parsed_url = urlparse(endpoint)
                    api_version = parse_qs(parsed_url.query)["api-version"][0]

                    model_data = {
                        "id": f"azure:{model_id}",
                        "endpoint": endpoint,
                        "type": "azure_openai",
                        "azure_endpoint_key": azure_endpoint_key,
                        "api_version": api_version,
                    }
                    models_info.append(model_data)
                    cls._model_id_to_endpoint_and_key[f"azure:{model_id}"] = model_data

            except Exception:
                continue

        return models_info

    @classmethod
    def get_model_info(cls, api_key: Optional[str] = None):
        """Retrieve Azure model information from environment variable."""
        # Initialize model map if empty
        if not cls._model_id_to_endpoint_and_key:
            cls._model_id_to_endpoint_and_key = {}

        if api_key is None:
            api_key = os.getenv(cls._env_key_name_)
        if api_key is None:
            # Return empty list instead of raising error when no API key is available
            # This allows Model.available() to work without requiring all service keys
            return []

        models_info = cls.parse_data_from_key(api_key)
        return models_info

    @classmethod
    def create_model(
        cls, model_name: str = "azureai", model_class_name=None
    ) -> "LanguageModel":
        """Dynamically create a LanguageModel subclass for Azure AI."""
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            """Language model class for Azure AI."""

            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 512,
                "top_p": 0.9,
            }

            def get_model_info_dict(self):
                """Initialize the model info dict from the key lookup."""
                # Get model info from the user's Azure key in the key lookup
                if self.api_token is None:
                    raise ValueError("API key is not set for Azure AI service")
                model_info = cls.parse_data_from_key(self.api_token)
                model_info_dict = {f"{model['id']}": model for model in model_info}
                return model_info_dict

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["FileStore"]] = None,
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> dict[str, Any]:
                """Call Azure OpenAI API and return the response."""
                try:
                    model_info_dict = self.get_model_info_dict()
                    api_key = model_info_dict[model_name]["azure_endpoint_key"]
                    endpoint = model_info_dict[model_name]["endpoint"]
                    model_type = model_info_dict[model_name].get("type", "azure_openai")
                except (KeyError, TypeError):
                    from ..exceptions import InferenceServiceEnvironmentError

                    raise InferenceServiceEnvironmentError(
                        f"AZURE_ENDPOINT_URL_AND_KEY missing endpoint:key pair for model {model_name}"
                    )

                # Extract base endpoint URL and deployment name for Azure OpenAI models
                deployment_name = None
                azure_base_endpoint = None
                api_version = model_info_dict[model_name].get("api_version")

                if "/openai/deployments/" in endpoint:
                    from urllib.parse import urlparse, urlunparse

                    parsed = urlparse(endpoint)
                    path_parts = parsed.path.split("/")
                    if "deployments" in path_parts:
                        deploy_idx = path_parts.index("deployments")
                        if deploy_idx + 1 < len(path_parts):
                            deployment_name = path_parts[deploy_idx + 1]

                    # Base endpoint is just scheme + netloc (e.g., https://xxx.openai.azure.com)
                    azure_base_endpoint = urlunparse(
                        (parsed.scheme, parsed.netloc, "", "", "", "")
                    )

                # For Azure OpenAI models, use the OpenAI SDK with Responses API
                # This gives us full file upload + PDF support
                if model_type == "azure_openai" and azure_base_endpoint:
                    import openai

                    # Responses API requires at least 2025-03-01-preview
                    responses_api_version = "2025-03-01-preview"
                    client = openai.AsyncAzureOpenAI(
                        azure_endpoint=azure_base_endpoint,
                        api_key=api_key,
                        api_version=responses_api_version,
                    )

                    # Build content for Responses API
                    content = [{"type": "input_text", "text": user_prompt}]

                    if files_list:
                        for f in files_list:
                            if f.mime_type.startswith("image/"):
                                content.append({
                                    "type": "input_image",
                                    "image_url": f"data:{f.mime_type};base64,{f.base64_string}",
                                })
                            elif f.mime_type == "application/pdf":
                                # Upload PDF via Files API, then reference by ID
                                import base64 as b64mod
                                import io
                                pdf_bytes = b64mod.b64decode(f.base64_string)
                                pdf_file = io.BytesIO(pdf_bytes)
                                pdf_file.name = getattr(f, "filename", "document.pdf")
                                sync_client = openai.AzureOpenAI(
                                    azure_endpoint=azure_base_endpoint,
                                    api_key=api_key,
                                    api_version=responses_api_version,
                                )
                                uploaded = sync_client.files.create(file=pdf_file, purpose="assistants")
                                content.append({
                                    "type": "input_file",
                                    "file_id": uploaded.id,
                                })
                            else:
                                # Text-based files: inline content
                                import base64 as b64mod
                                filename = getattr(f, "filename", "file")
                                try:
                                    text = b64mod.b64decode(f.base64_string).decode("utf-8")
                                    content.append({
                                        "type": "input_text",
                                        "text": f"--- Content from '{filename}' ---\n{text}\n--- End of {filename} ---",
                                    })
                                except (UnicodeDecodeError, Exception):
                                    content.append({
                                        "type": "input_text",
                                        "text": f"[File '{filename}' of type '{f.mime_type}' cannot be displayed]",
                                    })

                    input_messages = []
                    if system_prompt:
                        input_messages.append({"role": "system", "content": system_prompt})
                    input_messages.append({"role": "user", "content": content})

                    model_to_use = deployment_name or model_name
                    response = await client.responses.create(
                        model=model_to_use,
                        input=input_messages,
                        max_output_tokens=self.max_tokens,
                        temperature=self.temperature,
                        top_p=self.top_p,
                    )
                    return response.model_dump()

                # For non-OpenAI Azure models, use the Azure AI Inference SDK
                else:
                    if deployment_name:
                        from urllib.parse import urlunparse
                        parsed = urlparse(endpoint)
                        base_path = f"/openai/deployments/{deployment_name}"
                        endpoint = urlunparse(
                            (parsed.scheme, parsed.netloc, base_path, "", "", "")
                        )

                    client_kwargs = {
                        "endpoint": endpoint,
                        "credential": AzureKeyCredential(api_key),
                    }
                    if api_version:
                        client_kwargs["api_version"] = api_version

                    client = ChatCompletionsClient(**client_kwargs)

                    try:
                        messages = []
                        if system_prompt:
                            messages.append(SystemMessage(content=system_prompt))

                        if files_list:
                            content_items = [TextContentItem(text=user_prompt)]
                            for f in files_list:
                                if f.mime_type.startswith("image/"):
                                    content_items.append(
                                        ImageContentItem(
                                            image_url=ImageUrl(
                                                url=f"data:{f.mime_type};base64,{f.base64_string}"
                                            )
                                        )
                                    )
                                else:
                                    import base64 as b64mod
                                    filename = getattr(f, "filename", "file")
                                    try:
                                        text = b64mod.b64decode(f.base64_string).decode("utf-8")
                                        content_items.append(
                                            TextContentItem(
                                                text=f"--- Content from '{filename}' ---\n{text}\n--- End of {filename} ---"
                                            )
                                        )
                                    except (UnicodeDecodeError, Exception):
                                        content_items.append(
                                            TextContentItem(text=f"[File '{filename}' of type '{f.mime_type}' cannot be displayed]")
                                        )
                            messages.append(UserMessage(content=content_items))
                        else:
                            messages.append(UserMessage(content=user_prompt))

                        model_to_use = deployment_name if deployment_name else model_name
                        params = AzureParameterBuilder.build_params(
                            model=model_name,
                            messages=messages,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            top_p=self.top_p,
                        )
                        params["model"] = model_to_use

                        response = await client.complete(**params)
                        return response.as_dict()
                    finally:
                        await client.close()

        LLM.__name__ = model_class_name
        return LLM
