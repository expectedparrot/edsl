import os
from typing import Any
import re
import boto3
from botocore.exceptions import ClientError
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models.LanguageModel import LanguageModel
import json
from edsl.utilities.utilities import fix_partial_correct_response


class AwsBedrockService(InferenceServiceABC):
    """AWS Bedrock service class."""

    _inference_service_ = "bedrock"
    _env_key_name_ = (
        "AWS_ACCESS_KEY_ID"  # or any other environment key for AWS credentials
    )

    @classmethod
    def available(cls):
        """Fetch available models from AWS Bedrock."""
        if not cls._models_list_cache:
            client = boto3.client("bedrock", region_name="us-west-2")
            all_models_ids = [
                x["modelId"] for x in client.list_foundation_models()["modelSummaries"]
            ]
        else:
            all_models_ids = cls._models_list_cache

        return all_models_ids

    @classmethod
    def create_model(
        cls, model_name: str = "amazon.titan-tg1-large", model_class_name=None
    ) -> LanguageModel:
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with AWS Bedrock models.
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
                """Calls the AWS Bedrock API and returns the API response."""

                api_token = (
                    self.api_token
                )  # call to check the if env variables are set.

                client = boto3.client("bedrock-runtime", region_name="us-west-2")

                conversation = [
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ]
                system = [
                    {
                        "text": system_prompt,
                    }
                ]
                try:
                    response = client.converse(
                        modelId=self._model_,
                        messages=conversation,
                        inferenceConfig={
                            "maxTokens": self.max_tokens,
                            "temperature": self.temperature,
                            "topP": self.top_p,
                        },
                        # system=system,
                        additionalModelRequestFields={},
                    )
                    return response
                except (ClientError, Exception) as e:
                    print(e)
                    return {"error": str(e)}

            @staticmethod
            def parse_response(raw_response: dict[str, Any]) -> str:
                """Parses the API response and returns the response text."""
                if "output" in raw_response and "message" in raw_response["output"]:
                    response = raw_response["output"]["message"]["content"][0]["text"]
                    pattern = r"^```json(?:\\n|\n)(.+?)(?:\\n|\n)```$"
                    match = re.match(pattern, response, re.DOTALL)
                    if match:
                        return match.group(1)
                    else:
                        out = fix_partial_correct_response(response)
                        if "error" not in out:
                            response = out["extracted_json"]
                        return response
                return "Error parsing response"

        LLM.__name__ = model_class_name

        return LLM
