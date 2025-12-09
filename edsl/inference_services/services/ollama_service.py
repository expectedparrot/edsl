from typing import List, Optional
import os

from .open_ai_service import OpenAIService


class OllamaService(OpenAIService):
    """Ollama service class for local Ollama installations."""

    _inference_service_ = "ollama"
    _env_key_name_ = "OLLAMA_API_KEY"
    _base_url_ = "http://localhost:11434/v1"
    _models_list_cache: Optional[List[str]] = None

    @classmethod
    def get_model_info(cls, api_key=None):
        """Get raw model info without wrapping in ModelInfo."""
        if api_key is None:
            api_key = os.getenv(cls._env_key_name_)
        # For Ollama, provide a default API key since it's required but ignored
        if api_key is None:
            api_key = "ollama"
        raw_list = cls.sync_client(api_key).models.list()
        if hasattr(raw_list, "data"):
            return raw_list.data
        else:
            return raw_list
