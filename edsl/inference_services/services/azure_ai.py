import os
from typing import Any, Optional, List, TYPE_CHECKING
from openai import AsyncAzureOpenAI
from ..inference_service_abc import InferenceServiceABC
from ...language_models import LanguageModel

if TYPE_CHECKING:
    from ....scenarios.file_store import FileStore

from azure.ai.inference.aio import ChatCompletionsClient
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

    # key_sequence = ["content", 0, "text"]  # ["content"][0]["text"]
    key_sequence = ["choices", 0, "message", "content"]
    usage_sequence = ["usage"]
    input_token_name = "prompt_tokens"
    output_token_name = "completion_tokens"

    _inference_service_ = "azure"
    _env_key_name_ = (
        "AZURE_ENDPOINT_URL_AND_KEY"  # Environment variable for Azure API key
    )
    _model_id_to_endpoint_and_key = {}
    model_exclude_list = [
        "Cohere-command-r-plus-xncmg",
        "Mistral-Nemo-klfsi",
        "Mistral-large-2407-ojfld",
    ]

    @classmethod
    def available(cls):
        out = []
        azure_endpoints = os.getenv("AZURE_ENDPOINT_URL_AND_KEY", None)
        if not azure_endpoints:
            from ..exceptions import InferenceServiceEnvironmentError
            raise InferenceServiceEnvironmentError("AZURE_ENDPOINT_URL_AND_KEY is not defined")
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
                        api_version_value = None
                        if "api-version=" in endpoint:
                            start_idx = endpoint.index("api-version=") + len(
                                "api-version="
                            )
                            end_idx = (
                                endpoint.index("&", start_idx)
                                if "&" in endpoint[start_idx:]
                                else len(endpoint)
                            )
                            api_version_value = endpoint[start_idx:end_idx]

                        cls._model_id_to_endpoint_and_key[f"azure:{model_id}"] = {
                            "endpoint": f"https:{endpoint}",
                            "azure_endpoint_key": azure_endpoint_key,
                            "api_version": api_version_value,
                        }
                        out.append(f"azure:{model_id}")

            except Exception as e:
                raise e
        return [m for m in out if m not in cls.model_exclude_list]

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

            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["FileStore"]] = None,
            ) -> dict[str, Any]:
                """Calls the Azure OpenAI API and returns the API response."""

                try:
                    api_key = cls._model_id_to_endpoint_and_key[model_name][
                        "azure_endpoint_key"
                    ]
                except (KeyError, TypeError):
                    api_key = None

                if not api_key:
                    from ..exceptions import InferenceServiceEnvironmentError
                    raise InferenceServiceEnvironmentError(
                        f"AZURE_ENDPOINT_URL_AND_KEY doesn't have the endpoint:key pair for your model: {model_name}"
                    )

                try:
                    endpoint = cls._model_id_to_endpoint_and_key[model_name]["endpoint"]
                except (KeyError, TypeError):
                    endpoint = None

                if not endpoint:
                    from ..exceptions import InferenceServiceEnvironmentError
                    raise InferenceServiceEnvironmentError(
                        f"AZURE_ENDPOINT_URL_AND_KEY doesn't have the endpoint:key pair for your model: {model_name}"
                    )

                if "openai" not in endpoint:
                    client = ChatCompletionsClient(
                        endpoint=endpoint,
                        credential=AzureKeyCredential(api_key),
                        temperature=self.temperature,
                        top_p=self.top_p,
                        max_tokens=self.max_tokens,
                    )
                    try:
                        response = await client.complete(
                            messages=[
                                SystemMessage(content=system_prompt),
                                UserMessage(content=user_prompt),
                            ],
                            # model_extras={"safe_mode": True},
                        )
                        await client.close()
                        return response.as_dict()
                    except Exception as e:
                        await client.close()
                        return {"error": str(e)}
                else:
                    api_version = cls._model_id_to_endpoint_and_key[model_name][
                        "api_version"
                    ]
                    client = AsyncAzureOpenAI(
                        azure_endpoint=endpoint,
                        api_version=api_version,
                        api_key=api_key,
                    )
                    try:
                        response = await client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {
                                    "role": "user",
                                    "content": user_prompt,  # Your question can go here
                                },
                            ],
                        )
                    except Exception as e:
                        return {"message": str(e)}
                    return response.model_dump()

            # @staticmethod
            # def parse_response(raw_response: dict[str, Any]) -> str:
            #     """Parses the API response and returns the response text."""
            #     if (
            #         raw_response
            #         and "choices" in raw_response
            #         and raw_response["choices"]
            #     ):
            #         response = raw_response["choices"][0]["message"]["content"]
            #         pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
            #         match = re.match(pattern, response, re.DOTALL)
            #         if match:
            #             return match.group(1)
            #         else:
            #             out = fix_partial_correct_response(response)
            #             if "error" not in out:
            #                 response = out["extracted_json"]
            #             return response
            #     return "Error parsing response"

        LLM.__name__ = model_class_name

        return LLM
