import os
from typing import Any
import re
import boto3
from botocore.exceptions import ClientError
from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models.LanguageModel import LanguageModel


class AwsBedrockService(InferenceServiceABC):
    """AWS Bedrock service class."""

    _inference_service_ = "bedrock"
    _env_key_name_ = (
        "AWS_ACCESS_KEY_ID"  # or any other environment key for AWS credentials
    )

    @classmethod
    def available(cls):
        """Fetch available models from AWS Bedrock."""
        # client = boto3.client('bedrock', region_name="us-west-2")
        # all_models_ids = [
        #    x['modelId'] for x in client.list_foundation_models()['modelSummaries']
        # ]
        # good models
        all_models_ids = [
            "amazon.titan-tg1-large",
            "amazon.titan-text-lite-v1",
            "amazon.titan-text-express-v1",
            "ai21.j2-grande-instruct",
            "ai21.j2-jumbo-instruct",
            "ai21.j2-mid",
            "ai21.j2-mid-v1",
            "ai21.j2-ultra",
            "ai21.j2-ultra-v1",
            "anthropic.claude-instant-v1",
            "anthropic.claude-v2:1",
            "anthropic.claude-v2",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-opus-20240229-v1:0",
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "cohere.command-text-v14",
            "cohere.command-r-v1:0",
            "cohere.command-r-plus-v1:0",
            "cohere.command-light-text-v14",
            "meta.llama3-8b-instruct-v1:0",
            "meta.llama3-70b-instruct-v1:0",
            "meta.llama3-1-8b-instruct-v1:0",
            "meta.llama3-1-70b-instruct-v1:0",
            "meta.llama3-1-405b-instruct-v1:0",
            "mistral.mistral-7b-instruct-v0:2",
            "mistral.mixtral-8x7b-instruct-v0:1",
            "mistral.mistral-large-2402-v1:0",
            "mistral.mistral-large-2407-v1:0",
        ]

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

                try:
                    response = client.converse(
                        modelId=self._model_,
                        messages=conversation,
                        inferenceConfig={
                            "maxTokens": self.max_tokens,
                            "temperature": self.temperature,
                            "topP": self.top_p,
                        },
                        additionalModelRequestFields={},
                    )
                    return response
                except (ClientError, Exception) as e:
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
                        return response
                return "Error parsing response"

        LLM.__name__ = model_class_name

        return LLM
