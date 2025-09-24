import os
from typing import Any, Optional, List, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

from azure.ai.inference.aio import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage

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
    def get_model_info(cls):
        """Retrieve Azure model information from environment variable."""

        # Initialize model map if empty
        if not cls._model_id_to_endpoint_and_key:
            cls._model_id_to_endpoint_and_key = {}

        models_info = []
        azure_endpoints = os.getenv(cls._env_key_name_)
        if not azure_endpoints:
            raise ValueError(f"{cls._env_key_name_} is not defined")

        azure_endpoints = azure_endpoints.split(",")

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
    def create_model(
        cls, model_name: str = "azureai", model_class_name=None
    ) -> "LanguageModel":
        """Dynamically create a LanguageModel subclass for Azure AI."""
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Ensure the model map is initialized
        if not cls._model_id_to_endpoint_and_key:
            cls.get_model_info()

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

            @property
            def remote_proxy(self) -> bool:
                """Check if remote proxy is enabled."""
                return getattr(self, "_remote_proxy", False)

            @remote_proxy.setter
            def remote_proxy(self, value: bool):
                """Set the remote proxy flag."""
                self._remote_proxy = value

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["FileStore"]] = None,
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> dict[str, Any]:
                """Call Azure OpenAI API and return the response."""
                # Check if remote proxy is enabled
                if self.remote_proxy:
                    from .remote_proxy_handler import RemoteProxyHandler

                    handler = RemoteProxyHandler(
                        model=self._model_,
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
                        parameters=self._parameters_,
                        fresh=fresh_value,  # Pass fresh parameter
                    )

                # Note: files_list is not yet implemented for Azure AI service
                try:
                    api_key = cls._model_id_to_endpoint_and_key[model_name][
                        "azure_endpoint_key"
                    ]
                    endpoint = cls._model_id_to_endpoint_and_key[model_name]["endpoint"]
                except (KeyError, TypeError):
                    from ..exceptions import InferenceServiceEnvironmentError

                    raise InferenceServiceEnvironmentError(
                        f"AZURE_ENDPOINT_URL_AND_KEY missing endpoint:key pair for model {model_name}"
                    )

                # Extract base endpoint URL and deployment name for Azure OpenAI models
                # The stored endpoint might include the full path like /openai/deployments/{deployment}/chat/completions
                deployment_name = None
                if "/openai/deployments/" in endpoint:
                    # Parse the URL to extract base endpoint and deployment name
                    from urllib.parse import urlparse, urlunparse

                    parsed = urlparse(endpoint)

                    # Extract deployment name from path
                    path_parts = parsed.path.split("/")
                    if "deployments" in path_parts:
                        deploy_idx = path_parts.index("deployments")
                        if deploy_idx + 1 < len(path_parts):
                            deployment_name = path_parts[deploy_idx + 1]

                    # Construct base endpoint (scheme + netloc + /openai/deployments/{deployment})
                    if deployment_name:
                        base_path = f"/openai/deployments/{deployment_name}"
                        endpoint = urlunparse(
                            (parsed.scheme, parsed.netloc, base_path, "", "", "")
                        )
                    else:
                        # Fallback to base URL without path
                        endpoint = urlunparse(
                            (parsed.scheme, parsed.netloc, "", "", "", "")
                        )

                # Use Azure AI Inference SDK for all models (unified approach)
                api_version = cls._model_id_to_endpoint_and_key[model_name].get(
                    "api_version"
                )

                # Create client with optional api_version
                client_kwargs = {
                    "endpoint": endpoint,
                    "credential": AzureKeyCredential(api_key),
                }

                # Add api_version if available (required for some models)
                if api_version:
                    client_kwargs["api_version"] = api_version

                client = ChatCompletionsClient(**client_kwargs)

                try:
                    # Build messages
                    messages = []
                    if system_prompt:
                        messages.append(SystemMessage(content=system_prompt))
                    messages.append(UserMessage(content=user_prompt))

                    # Make the API call with parameters
                    # Use deployment name if available (for Azure OpenAI), otherwise use model_name
                    model_to_use = deployment_name if deployment_name else model_name

                    # Use AzureParameterBuilder to construct parameters
                    params = AzureParameterBuilder.build_params(
                        model=model_name,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        top_p=self.top_p,
                    )

                    # Add the model to the parameters
                    params["model"] = model_to_use

                    response = await client.complete(**params)
                    return response.as_dict()
                finally:
                    await client.close()

        LLM.__name__ = model_class_name
        return LLM
