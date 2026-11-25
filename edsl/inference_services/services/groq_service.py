from typing import List

from .open_ai_service import OpenAIService


class GroqService(OpenAIService):
    """Groq service class."""

    _inference_service_ = "groq"
    _env_key_name_ = "GROQ_API_KEY"

    _sync_client_ = None
    _async_client_ = None

    @classmethod
    def _resolve_clients(cls):
        if cls._sync_client_ is None:
            import groq
            cls._sync_client_ = groq.Groq
            cls._async_client_ = groq.AsyncGroq

    @classmethod
    def async_client(cls, api_key, base_url=None):
        """Create a cached Groq async client without OpenAI-specific options."""
        cls._resolve_clients()
        resolved_base_url = base_url if base_url is not None else cls._base_url_
        cache_key = (api_key, resolved_base_url)
        if cache_key not in cls._async_client_instances:
            client = cls._async_client_(
                api_key=api_key,
                base_url=resolved_base_url,
            )
            cls._async_client_instances[cache_key] = client
        return cls._async_client_instances[cache_key]

    # _base_url_ = "https://api.deepinfra.com/v1/openai"
    _base_url_ = None
    _models_list_cache: List[str] = []

    @classmethod
    def _is_reasoning_model(cls, model_name: str) -> bool:
        name = model_name.lower()
        return any(
            tag in name
            for tag in ("gpt-oss", "qwen3", "qwen/qwq", "muse-spark", "minimax-m")
        )
