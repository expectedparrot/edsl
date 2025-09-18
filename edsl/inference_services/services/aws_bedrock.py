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
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> dict[str, Any]:
                """Calls the AWS Bedrock API and returns the API response."""

                # Check if we should use remote proxy
                if self.remote_proxy:
                    # Use remote proxy mode
                    from .remote_proxy_handler import RemoteProxyHandler

                    handler = RemoteProxyHandler(
                        model=self.model, inference_service=self._inference_service_
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
                        omit_system_prompt_if_empty=self.omit_system_prompt_if_empty,
                        fresh=fresh_value,  # Pass fresh parameter
                    )

                # Ensure credentials are available
                _ = self.api_token  # call to check if env variables are set.

                region = os.getenv("AWS_REGION", "us-east-1")
                client = boto3.client("bedrock-runtime", region_name=region)

                # Build content array for the user message
                content = []

                # Add text content if provided
                if user_prompt:
                    content.append({"text": user_prompt})

                # Add images/files if provided
                if files_list:
                    for file_store in files_list:
                        if hasattr(file_store, "path") and file_store.path:
                            # Read file bytes
                            with open(file_store.path, "rb") as f:
                                file_bytes = f.read()

                            # Determine file format from extension
                            file_format = self._get_file_format(file_store.path)
                            filename = file_store.path.split("/")[-1]

                            if file_format in ["png", "jpeg", "jpg", "gif", "webp"]:
                                # Handle image files
                                bedrock_format = (
                                    file_format if file_format != "jpg" else "jpeg"
                                )

                                image_block = {
                                    "image": {
                                        "format": bedrock_format,
                                        "source": {"bytes": file_bytes},
                                    }
                                }
                                content.append(image_block)

                            elif file_format in ["pdf", "txt", "doc", "docx"]:
                                # Handle document files - ensure name follows restrictions
                                # Clean filename to only contain allowed characters
                                clean_name = self._clean_document_name(filename)

                                document_block = {
                                    "document": {
                                        "format": file_format,
                                        "name": clean_name,
                                        "source": {"bytes": file_bytes},
                                    }
                                }
                                content.append(document_block)

                # AWS Bedrock requirement: If we have documents, we must have text content
                # If content is empty or only has documents, add a default text prompt
                has_text = any(block.get("text") for block in content)
                has_documents = any(block.get("document") for block in content)

                if has_documents and not has_text:
                    # Add required text content for document processing
                    content.insert(0, {"text": "Please analyze this document."})
                elif not content:
                    # If no content at all, add the user prompt as text
                    content.append({"text": user_prompt or "Hello"})

                conversation = [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]

                # Build converse parameters
                converse_params = {
                    "modelId": self._model_,
                    "messages": conversation,
                    "inferenceConfig": {
                        "maxTokens": self.max_tokens,
                        "temperature": self.temperature,
                        "topP": self.top_p,
                    },
                    "additionalModelRequestFields": {},
                }

                # Add system prompt if provided
                if system_prompt:
                    converse_params["system"] = [{"text": system_prompt}]

                response = client.converse(**converse_params)
                return response

            def _get_file_format(self, file_path: str) -> str:
                """Extract file format from file path."""
                import os

                _, ext = os.path.splitext(file_path.lower())
                return ext[1:] if ext else "unknown"

            def _clean_document_name(self, filename: str) -> str:
                """
                Clean document name to conform to AWS Bedrock restrictions.

                Allowed characters:
                - Alphanumeric characters
                - Whitespace characters (no more than one in a row)
                - Hyphens
                - Parentheses
                - Square brackets
                """
                import re

                # Remove file extension for cleaner name
                name = filename.rsplit(".", 1)[0] if "." in filename else filename

                # Replace invalid characters with spaces
                # Keep only: alphanumeric, spaces, hyphens, parentheses, square brackets
                cleaned = re.sub(r"[^a-zA-Z0-9\s\-\(\)\[\]]", " ", name)

                # Replace multiple consecutive spaces with single space
                cleaned = re.sub(r"\s+", " ", cleaned)

                # Trim and ensure it's not empty
                cleaned = cleaned.strip()

                if not cleaned:
                    cleaned = "Document"

                # Limit length to be reasonable (Bedrock doesn't specify but good practice)
                if len(cleaned) > 50:
                    cleaned = cleaned[:50].strip()

                return cleaned

        LLM.__name__ = model_class_name

        return LLM
