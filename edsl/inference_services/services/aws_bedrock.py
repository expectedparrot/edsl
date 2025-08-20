import os
from typing import Any, List, Optional, TYPE_CHECKING
import boto3
from ..inference_service_abc import InferenceServiceABC
from ..decorators import report_errors_async

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ...scenarios.file_store import FileStore


class AwsBedrockService(InferenceServiceABC):
    """AWS Bedrock service class."""

    _inference_service_ = "bedrock"
    _env_key_name_ = (
        "AWS_ACCESS_KEY_ID"  # or any other environment key for AWS credentials
    )
    key_sequence = ["output", "message", "content", 0, "text"]
    input_token_name = "inputTokens"
    output_token_name = "outputTokens"
    usage_sequence = ["usage"]

    @classmethod
    def get_model_info(cls):
        """Get raw model info from AWS Bedrock."""
        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock", region_name=region)
        return client.list_foundation_models()["modelSummaries"]

    # @classmethod
    # def available(cls):
    #     """Fetch available models from AWS Bedrock."""

    #     region = os.getenv("AWS_REGION", "us-east-1")

    #     if not cls._models_list_cache:
    #         client = boto3.client("bedrock", region_name=region)
    #         all_models_ids = [
    #             x["modelId"] for x in client.list_foundation_models()["modelSummaries"]
    #         ]
    #     else:
    #         all_models_ids = cls._models_list_cache

    #     return [m for m in all_models_ids if m not in cls.model_exclude_list]

    @classmethod
    def create_model(
        cls, model_name: str = "amazon.titan-tg1-large", model_class_name=None
    ) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Import LanguageModel only when actually creating a model
        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            """
            Child class of LanguageModel for interacting with AWS Bedrock models.
            """

            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            _inference_service_ = cls._inference_service_
            _model_ = model_name
            _parameters_ = {
                "temperature": 0.5,
                "max_tokens": 512,
                "top_p": 0.9,
            }
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional[List["FileStore"]] = None,
            ) -> dict[str, Any]:
                """Calls the AWS Bedrock API and returns the API response."""

                # Ensure credentials are available
                _ = self.api_token  # call to check if env variables are set.

                region = os.getenv("AWS_REGION", "us-east-1")
                client = boto3.client("bedrock-runtime", region_name=region)

                conversation = [
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ]
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

        LLM.__name__ = model_class_name

        return LLM
