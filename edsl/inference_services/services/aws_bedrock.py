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
        """Get raw model info from AWS Bedrock — only the IDs the account can
        actually invoke on-demand.

        Two AWS Bedrock APIs together describe what's callable on-demand:

        * ``list_inference_profiles`` — returns cross-region routing profiles
          (``us.*``, ``global.*``, ``eu.*``, ``apac.*``). Most modern models
          (Claude 3.5+, Llama 3.1+, etc.) can ONLY be invoked via one of
          these; AWS rejects their bare foundation IDs with::

              ValidationException: Invocation of model ID <id> with on-demand
              throughput isn't supported. Retry your request with the ID or ARN
              of an inference profile that contains this model.

        * ``list_foundation_models`` — returns the regional catalog of every
          model AWS hosts. Some models (notably the OpenAI ``gpt-oss-*``
          family) support on-demand invocation with their BARE ID and have
          no inference profile; for those, the foundation ID is the only
          invocable form.

        We return the union: all profile IDs, plus any foundation ID whose
        ``inferenceTypesSupported`` includes ``ON_DEMAND`` AND that does not
        already appear as a profile target. This avoids hiding the OpenAI
        gpt-oss models (and any future on-demand-bare-ID models) while still
        steering users to the profile ID for everything that requires one.
        """
        region = os.getenv("AWS_REGION", "us-east-1")
        client = boto3.client("bedrock", region_name=region)

        # 1) Inference profiles (cross-region routing IDs).
        profiles: list = []
        try:
            profiles = client.list_inference_profiles().get(
                "inferenceProfileSummaries", []
            )
        except Exception:
            pass

        # Track the bare model IDs each profile contains so we can skip the
        # bare entries in step 2 — the profile ID is the canonical form.
        bare_ids_covered_by_profile: set = set()
        for p in profiles:
            for routed in p.get("models", []) or []:
                arn = routed.get("modelArn", "")
                # ARN tail looks like ".../foundation-model/<model-id>"
                if "/" in arn:
                    bare_ids_covered_by_profile.add(arn.rsplit("/", 1)[-1])
            # Also strip the routing prefix from the profile ID itself; that's
            # always the bare ID the profile fronts.
            pid = p.get("inferenceProfileId", "")
            for pref in cls._PROFILE_PREFERENCE:
                if pid.startswith(pref):
                    bare_ids_covered_by_profile.add(pid[len(pref) :])
                    break

        # 2) Foundation models with ON_DEMAND inference (bare-ID invokable
        #    and not already covered by a profile).
        foundation_on_demand: list = []
        try:
            catalog = client.list_foundation_models().get("modelSummaries", [])
            for m in catalog:
                if "ON_DEMAND" not in (m.get("inferenceTypesSupported") or []):
                    continue
                if m.get("modelId") in bare_ids_covered_by_profile:
                    continue
                foundation_on_demand.append(m)
        except Exception:
            pass

        # Reshape profiles to the {"modelId": ...} shape ModelInfo expects.
        profile_entries = [
            {
                "modelId": p["inferenceProfileId"],
                "providerName": p.get("inferenceProfileName", ""),
                "inferenceProfileArn": p.get("inferenceProfileArn", ""),
            }
            for p in profiles
        ]

        result = profile_entries + foundation_on_demand
        # If both APIs failed, fall back to whatever the catalog has so
        # discovery isn't completely broken in degraded environments.
        if not result:
            try:
                return client.list_foundation_models()["modelSummaries"]
            except Exception:
                return []
        return result

    # Cache: region -> {bare_model_id: profile_id}. Populated lazily on first
    # resolve call per region and reused for the rest of the process.
    _profile_cache_by_region: dict = {}

    # Prefixes that mark an ID as already an inference profile (or ARN); these
    # are passed through to the Converse API untouched.
    _PROFILE_PREFIXES = ("us.", "global.", "eu.", "apac.", "arn:")

    # Preference order when multiple cross-region profiles exist for the same
    # bare model ID. US accounts typically have us.* granted; global.* exists
    # for newer models; eu.*/apac.* for those regions.
    _PROFILE_PREFERENCE = ("us.", "global.", "eu.", "apac.")

    @classmethod
    def _load_profile_map(cls, region: str) -> dict:
        """Return {bare_model_id: profile_id} for `region`, caching per process.

        Builds the map by listing all inference profiles in the region and
        stripping the routing prefix from each profile ID. When several
        profiles map to the same bare ID (e.g. both ``us.X`` and ``global.X``),
        ``_PROFILE_PREFERENCE`` decides which one wins.
        """
        if region in cls._profile_cache_by_region:
            return cls._profile_cache_by_region[region]

        mapping: dict = {}
        try:
            client = boto3.client("bedrock", region_name=region)
            profiles = client.list_inference_profiles().get(
                "inferenceProfileSummaries", []
            )
            # Group bare-id -> [profile_id, ...] then pick by preference order.
            by_bare: dict = {}
            for p in profiles:
                pid = p.get("inferenceProfileId", "")
                for pref in cls._PROFILE_PREFERENCE:
                    if pid.startswith(pref):
                        bare = pid[len(pref) :]
                        by_bare.setdefault(bare, []).append(pid)
                        break
            for bare, candidates in by_bare.items():
                for pref in cls._PROFILE_PREFERENCE:
                    match = next((c for c in candidates if c.startswith(pref)), None)
                    if match:
                        mapping[bare] = match
                        break
        except Exception:
            # On failure leave the cache empty for this region; resolve() will
            # return the original ID and AWS will produce its native error.
            pass

        cls._profile_cache_by_region[region] = mapping
        return mapping

    @classmethod
    def _resolve_inference_profile(cls, model_id: str, region: str) -> str:
        """Translate a bare Bedrock foundation-model ID into the inference
        profile ID the account can invoke on-demand.

        Restores the silent translation the deleted ``remote_proxy`` used to
        perform server-side (removed in commit 04e6ffff, March 2026). Without
        this, pre-existing user code like ``Model("meta.llama3-1-70b-instruct-v1:0",
        service_name="bedrock")`` fails with::

            ValidationException: Invocation of model ID <bare_id> with on-demand
            throughput isn't supported. Retry your request with the ID or ARN
            of an inference profile that contains this model.

        Rules:
          * IDs already starting with ``us.``/``global.``/``eu.``/``apac.`` or
            ARNs are passed through unchanged.
          * Otherwise the cached profile map for the region is consulted. The
            preferred match (US first, then global, then EU, then APAC) is
            returned.
          * If no profile matches, the original ID is returned so AWS produces
            its native error message (which is more informative than anything
            EDSL could synthesize here).
        """
        if not model_id or model_id.startswith(cls._PROFILE_PREFIXES):
            return model_id
        return cls._load_profile_map(region).get(model_id, model_id)

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

                # Ensure credentials are available
                _ = self.api_token  # call to check if env variables are set.

                region = os.getenv("AWS_REGION", "us-east-1")
                # Translate a bare foundation-model ID (e.g.
                # "meta.llama3-1-70b-instruct-v1:0") into the inference profile
                # the account can actually invoke (e.g.
                # "us.meta.llama3-1-70b-instruct-v1:0"). Profile IDs and ARNs
                # pass through unchanged.
                effective_model_id = cls._resolve_inference_profile(
                    self._model_, region
                )
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
                    "modelId": effective_model_id,
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
