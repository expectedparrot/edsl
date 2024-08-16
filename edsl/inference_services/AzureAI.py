import os
from typing import Any
import re
from openai import OpenAI
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models.LanguageModel import LanguageModel

from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage


def json_handle_none(value: Any) -> Any:
    """
    Handle None values during JSON serialization.
    - Return "null" if the value is None. Otherwise, don't return anything.
    """
    if value is None:
        return "null"


class AzureAIService(InferenceServiceABC):
    """Azure AI service class."""

    _inference_service_ = "azure"
    _env_key_name_ = (
        "AZURE_ENDPOINT_URL_AND_KEY"  # Environment variable for Azure API key
    )
    _model_id_to_endpoint_and_key = {}

    @classmethod
    def available(cls):
        out = []
        azure_endpoints = os.getenv("AZURE_ENDPOINT_URL_AND_KEY", None)
        if not azure_endpoints:
            # TODO print an error message
            pass
        azure_endpoints = azure_endpoints.split(",")
        for data in azure_endpoints:
            try:
                # data has this format for non openai models https://model_id.azure_endpoint:azure_key
                _, endpoint, azure_endpoint_key = data.split(":")
                if "openai" not in endpoint:
                    model_id = endpoint.split(".")[0].replace("/", "")
                    out.append(model_id)
                    cls._model_id_to_endpoint_and_key[model_id] = {
                        "endpoint": f"https:{endpoint}",
                        "azure_endpoint_key": azure_endpoint_key,
                    }
                else:
                    # data has this format for openai models ,https://azure_project_id.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2023-03-15-preview:azure_key
                    if "/deployments/" in endpoint:
                        start_idx = endpoint.index("/deployments/") + len(
                            "/deployments/"
                        )
                        end_idx = (
                            endpoint.index("/", start_idx)
                            if "/" in endpoint[start_idx:]
                            else len(endpoint)
                        )
                        model_id = endpoint[start_idx:end_idx]
                        out.append(f"azure:{model_id}")

            except Exception as e:
                print(e)
        return out

    @classmethod
    def create_model(
        cls, model_name: str = "azureai", model_class_name=None
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with Azure OpenAI models.
            """

            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 512,
                "top_p": 0.9,
            }

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str = ""
            ) -> dict[str, Any]:
                """Calls the Azure OpenAI API and returns the API response."""

                try:
                    api_key = cls._model_id_to_endpoint_and_key[model_name][
                        "azure_endpoint_key"
                    ]
                except:
                    api_key = None

                if not api_key:
                    raise EnvironmentError(
                        f"AZURE_ENDPOINT_URL_AND_KEY doesn't have the endpoint:key pair for your model: {model_name}"
                    )

                try:
                    base_url = cls._model_id_to_endpoint_and_key[model_name]["endpoint"]
                except:
                    base_url = None

                if not base_url:
                    raise EnvironmentError(
                        f"AZURE_ENDPOINT_URL_AND_KEY doesn't have the endpoint:key pair for your model: {model_name}"
                    )

                print(base_url, api_key)
                client = ChatCompletionsClient(
                    endpoint=base_url,
                    credential=AzureKeyCredential(api_key),
                )
                try:
                    response = client.complete(
                        messages=[
                            SystemMessage(content=system_prompt),
                            UserMessage(content=user_prompt),
                        ],
                        model_extras={"safe_mode": True},
                    )
                    return response.as_dict()
                except Exception as e:
                    return {"error": str(e)}

            @staticmethod
            def parse_response(raw_response: dict[str, Any]) -> str:
                """Parses the API response and returns the response text."""
                print(raw_response)
                if (
                    raw_response
                    and "choices" in raw_response
                    and raw_response["choices"]
                ):
                    response = raw_response["choices"][0]["message"]["content"]
                    # Old parsing logic with regex
                    pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
                    match = re.match(pattern, response, re.DOTALL)
                    if match:
                        return match.group(1)
                    else:
                        return response
                return "Error parsing response"

        LLM.__name__ = model_class_name

        return LLM
