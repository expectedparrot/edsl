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
    _env_key_name_ = "AZURE_API_KEY"  # Environment variable for Azure API key

    @classmethod
    def available(cls):
        # TODO: Implement logic to return available models based on Azure environment variables
        return ["azure"]

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

                api_key = os.getenv(cls._env_key_name_)
                if not api_key:
                    raise EnvironmentError(f"{cls._env_key_name_} is not set")

                base_url = os.getenv(
                    "AZURE_ENDPOINT_URL"
                )  # Expecting endpoint URL in environment variables
                if not base_url:
                    raise EnvironmentError("AZURE_ENDPOINT_URL is not set")
                print(base_url, api_key)
                # client = OpenAI(base_url=base_url, api_key=api_key)
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
