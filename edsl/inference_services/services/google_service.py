import os
from typing import Any, Dict, Optional, TYPE_CHECKING

# from ...exceptions.general import MissingAPIKeyError
from ..inference_service_abc import InferenceServiceABC
from ..decorators import report_errors_async

# Use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from ...language_models import LanguageModel
    from ...scenarios.file_store import FileStore as Files

# Lazy imports for Google genai packages (they load slowly)
_genai = None
_types = None


def _get_genai():
    """Lazy import of google.genai module."""
    global _genai
    if _genai is None:
        from google import genai

        _genai = genai
    return _genai


def _get_types():
    """Lazy import of google.genai.types module."""
    global _types
    if _types is None:
        from google.genai import types

        _types = types
    return _types


def _vertex_enabled() -> bool:
    """Whether Google calls go through Vertex AI instead of the Gemini Developer
    API. Toggled by the ``GOOGLE_GENAI_USE_VERTEXAI`` environment variable."""
    return os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


# Env vars that may hold a service-account key for Vertex. The first two carry
# the key's JSON *contents* inline (how containers usually inject a secret); the
# standard GOOGLE_APPLICATION_CREDENTIALS holds a filesystem *path* (and is also
# what Application Default Credentials reads on its own).
_VERTEX_SA_JSON_ENV_VARS = (
    "GOOGLE_VERTEX_CREDENTIALS",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
)
_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _vertex_credentials_and_project(explicit_json: Optional[str] = None):
    """Resolve Vertex credentials and project from a service-account key.

    The key may be supplied explicitly as a JSON string (``explicit_json`` — this
    is how a per-user *custodial* Vertex key is passed, carried on the model so it
    reaches coopr's worker), otherwise it is read from the environment. The
    project is read from the key's ``project_id`` field, so a project need not be
    configured separately. Returns ``(credentials, project_id)``, or
    ``(None, None)`` when no key is found (the Gen AI SDK then falls back to
    Application Default Credentials, e.g. workload identity).
    """
    import json

    blob = None
    if explicit_json and explicit_json.strip().startswith("{"):
        blob = explicit_json
    else:
        for name in _VERTEX_SA_JSON_ENV_VARS:
            value = os.environ.get(name)
            if value and value.strip().startswith("{"):
                blob = value
                break
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    try:
        from google.oauth2 import service_account

        if blob:
            info = json.loads(blob)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=_VERTEX_SCOPES
            )
            return creds, info.get("project_id")
        if path and os.path.exists(path):
            with open(path) as handle:
                info = json.load(handle)
            creds = service_account.Credentials.from_service_account_file(
                path, scopes=_VERTEX_SCOPES
            )
            return creds, info.get("project_id")
    except Exception:
        # Malformed key or google-auth unavailable: let the SDK try ADC and let
        # any real failure surface on the actual call.
        return None, None

    return None, None


def _build_genai_client(
    api_token: Optional[str] = None,
    *,
    use_vertex: Optional[bool] = None,
    vertex_project: Optional[str] = None,
    vertex_location: Optional[str] = None,
    vertex_credentials: Optional[str] = None,
):
    """Construct a ``google.genai`` client for the configured backend.

    Backend selection is per call. An explicit ``use_vertex`` wins; it is
    normally carried as a *model parameter* (see ``create_model``), so the choice
    serializes with the model and reaches coopr's remote-inference worker when it
    rebuilds the model from its dict. When ``use_vertex`` is ``None`` the
    ``GOOGLE_GENAI_USE_VERTEXAI`` environment variable is the default.

    * **Gemini Developer API** (default) — authenticated by an API key
      (``api_token`` if given, else ``GOOGLE_API_KEY``). Historical behaviour.
    * **Vertex AI** — ``genai.Client(vertexai=True, project=..., location=...,
      credentials=...)``. Credentials come from a **service-account key** in the
      environment: its JSON contents inline in ``GOOGLE_VERTEX_CREDENTIALS`` /
      ``GOOGLE_SERVICE_ACCOUNT_JSON``, or a file path in
      ``GOOGLE_APPLICATION_CREDENTIALS`` (also plain ADC / workload identity).
      The **project is read from the key** (its ``project_id``), so it need not be
      configured; ``vertex_project`` / ``GOOGLE_CLOUD_PROJECT`` only override it.
      ``location`` is not part of a key, so it comes from ``vertex_location`` /
      ``GOOGLE_CLOUD_LOCATION`` / ``us-central1``. The API key is ignored
      (standard Vertex rejects keys). Vertex is where Google Cloud credits apply.
    """
    genai = _get_genai()
    vertex = use_vertex if use_vertex is not None else _vertex_enabled()
    if vertex:
        credentials, sa_project = _vertex_credentials_and_project(vertex_credentials)
        project = vertex_project or os.environ.get("GOOGLE_CLOUD_PROJECT") or sa_project
        if not project:
            raise ValueError(
                "Vertex AI is enabled but no project could be determined. Provide "
                "a service-account key (the project is read from it) via "
                "GOOGLE_VERTEX_CREDENTIALS / GOOGLE_APPLICATION_CREDENTIALS, or set "
                "GOOGLE_CLOUD_PROJECT."
            )
        location = (
            vertex_location or os.environ.get("GOOGLE_CLOUD_LOCATION") or "us-central1"
        )
        client_kwargs = {"vertexai": True, "project": project, "location": location}
        # When no explicit key is found, credentials is None and the SDK uses ADC.
        if credentials is not None:
            client_kwargs["credentials"] = credentials
        return genai.Client(**client_kwargs)

    api_key = api_token or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable not set.")
    return genai.Client(api_key=api_key)


safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
]


class GoogleService(InferenceServiceABC):
    _inference_service_ = "google"
    key_sequence = ["candidates", 0, "content", "parts", 0, "text"]
    usage_sequence = ["usage_metadata"]
    input_token_name = "prompt_token_count"
    output_token_name = "candidates_token_count"
    thinking_token_sequence = ["thoughts_token_count"]

    available_models_url = (
        "https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models"
    )

    @classmethod
    def get_model_info(cls):
        """Get raw model info without wrapping in ModelInfo."""
        client = _build_genai_client()
        response = client.models.list()
        model_list = list(response)
        return model_list

    @classmethod
    def create_model(
        cls, model_name: str = "gemini-pro", model_class_name=None
    ) -> "LanguageModel":
        if model_class_name is None:
            model_class_name = cls.to_class_name(model_name)

        # Import LanguageModel only when actually creating a model
        from ...language_models import LanguageModel

        class LLM(LanguageModel):
            _model_ = model_name
            key_sequence = cls.key_sequence
            usage_sequence = cls.usage_sequence
            input_token_name = cls.input_token_name
            output_token_name = cls.output_token_name
            thinking_token_sequence = cls.thinking_token_sequence
            _inference_service_ = cls._inference_service_

            _parameters_ = {
                "temperature": 0.5,
                "topP": 1,
                "topK": 1,
                "maxOutputTokens": 2048,
                "stopSequences": [],
                "thinking_budget": None,
                # Backend selection (Vertex AI vs Gemini Developer API). These
                # are model parameters so they travel with the serialized model:
                # a job built with use_vertex=True runs on Vertex through coopr's
                # remote-inference worker as well. They are NOT sent to the API.
                # None => fall back to GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_*.
                "use_vertex": None,
                "vertex_project": None,
                "vertex_location": None,
                # A service-account key (JSON string) for a per-user "custodial"
                # Vertex project. When set it supplies the credentials and the
                # project; None falls back to the worker env credentials.
                "vertex_credentials": None,
            }

            model = None
            _cached_client = None
            _cached_api_token = None
            _client_lock = None

            # Map common/generic parameter names to Google-specific names
            _parameter_aliases_ = {
                "max_output_tokens": "maxOutputTokens",
                "max_tokens": "maxOutputTokens",
                "top_p": "topP",
                "top_k": "topK",
                "stop_sequences": "stopSequences",
            }

            def __init__(self, *args, **kwargs):
                # Translate generic parameter names to Google-specific names
                for generic, google_name in self._parameter_aliases_.items():
                    if generic in kwargs and google_name not in kwargs:
                        kwargs[google_name] = kwargs.pop(generic)
                super().__init__(*args, **kwargs)
                if self._client_lock is None:
                    import asyncio

                    self._client_lock = asyncio.Lock()

            @report_errors_async
            async def async_execute_model_call(
                self,
                user_prompt: str,
                system_prompt: str = "",
                files_list: Optional["Files"] = None,
                cache_key: Optional[str] = None,  # Cache key for tracking
            ) -> Dict[str, Any]:
                """Calls the Google API and returns the API response.

                Args:
                    user_prompt: The user message or input prompt
                    system_prompt: The system message or context
                    files_list: Optional list of files to include
                """
                # import time

                # method_start = time.time()

                if files_list is None:
                    files_list = []

                # Get or create cached client (thread-safe)
                # client_start = time.time()
                async with self._client_lock:
                    if (
                        self._cached_client is None
                        or self._cached_api_token != self.api_token
                    ):
                        # print("Creating new Google client...", flush=True)
                        # creation_start = time.time()

                        # Developer API (api key) or Vertex AI (ADC/service
                        # account). The per-model use_vertex / vertex_project /
                        # vertex_location parameters win; otherwise the
                        # GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_* env vars are
                        # the default. In Vertex mode api_token is ignored.
                        self._cached_client = _build_genai_client(
                            self.api_token,
                            use_vertex=getattr(self, "use_vertex", None),
                            vertex_project=getattr(self, "vertex_project", None),
                            vertex_location=getattr(self, "vertex_location", None),
                            vertex_credentials=getattr(
                                self, "vertex_credentials", None
                            ),
                        )
                        self._cached_api_token = self.api_token

                client = self._cached_client

                # Time prompt processing
                # prompt_start = time.time()
                if system_prompt is not None and system_prompt != "":
                    if self._model_ != "gemini-pro":
                        system_instruction = system_prompt
                    else:
                        print(
                            f"This model, {self._model_}, does not support system_instruction"
                        )
                        print("Will add system_prompt to user_prompt")
                        user_prompt = f"{system_prompt}\n{user_prompt}"
                        system_instruction = None
                else:
                    # No system prompt
                    system_instruction = None

                combined_prompt = [user_prompt]
                # prompt_time = time.time() - prompt_start
                # print(f"Prompt processing took {prompt_time:.3f}s", flush=True)

                # Time file processing
                # file_start = time.time()
                # print(f"Processing {len(files_list)} files", flush=True)

                # Use the file upload cache to handle uploads efficiently
                from ...scenarios.file_upload_cache import file_upload_cache

                for i, file in enumerate(files_list):
                    # file_upload_start = time.time()
                    # Use cache to get or upload the file
                    # This ensures each unique file is only uploaded once
                    google_file_info = await file_upload_cache.get_or_upload(
                        file, service="google"
                    )
                    # file_upload_time = time.time() - file_upload_start
                    # print(
                    #     f"File {i+1} upload/cache took {file_upload_time:.3f}s",
                    #     flush=True,
                    # )

                    # print("gogole file info is",google_file_info)
                    # Create the Google AI file reference using native async API
                    # file_ref_start = time.time()
                    try:
                        gen_ai_file = await client.aio.files.get(
                            name=google_file_info["name"]
                        )
                        combined_prompt.append(gen_ai_file)
                        # file_ref_time = time.time() - file_ref_start
                        # print(
                        #     f"File {i+1} reference creation took {file_ref_time:.3f}s",
                        #     flush=True,
                        # )
                    except Exception as e:
                        # file_ref_time = time.time() - file_ref_start
                        # print(
                        #     f"File {i+1} reference creation failed after {file_ref_time:.3f}s: {str(e)}",
                        #     flush=True,
                        # )
                        raise Exception(
                            f"Failed to create file reference for {google_file_info['name']}: {str(e)}"
                        )

                # file_total_time = time.time() - file_start
                # print(f"Total file processing took {file_total_time:.3f}s", flush=True)

                # Time config creation
                # config_start = time.time()
                types = _get_types()

                config_kwargs = dict(
                    temperature=self.temperature,
                    top_p=self.topP,
                    top_k=self.topK,
                    max_output_tokens=self.maxOutputTokens,
                    stop_sequences=self.stopSequences,
                    safety_settings=[
                        types.SafetySetting(
                            category=setting["category"],
                            threshold=setting["threshold"],
                        )
                        for setting in safety_settings
                    ],
                    system_instruction=system_instruction,
                )

                if self.thinking_budget is not None:
                    config_kwargs["thinking_config"] = types.ThinkingConfig(
                        thinking_budget=self.thinking_budget,
                    )

                generation_config = types.GenerateContentConfig(**config_kwargs)
                # config_time = time.time() - config_start
                # print(f"Configuration creation took {config_time:.3f}s", flush=True)

                # Time API call
                # api_start = time.time()
                # print(
                #     f"Making async API call to {self._model_} with {len(combined_prompt)} prompt parts",
                #     flush=True,
                # )
                response = await client.aio.models.generate_content(
                    model=self._model_,
                    contents=combined_prompt,
                    config=generation_config,
                )
                # api_time = time.time() - api_start
                # print(f"Async API call completed in {api_time:.3f}s", flush=True)

                # Time response processing
                # response_start = time.time()
                result = response.model_dump(mode="json")
                # response_time = time.time() - response_start
                # print(f"Response processing took {response_time:.3f}s", flush=True)

                # Print total method time
                # total_time = time.time() - method_start
                # print(
                #     f"Total async_execute_model_call took {total_time:.3f}s", flush=True
                # )

                return result

        LLM.__name__ = model_name
        return LLM


if __name__ == "__main__":
    pass
