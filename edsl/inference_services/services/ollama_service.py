from typing import List

from .open_ai_service import OpenAIService


class OllamaService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "ollama"
    _env_key_name_ = "DEEP_INFRA_API_KEY"
    _base_url_ = "http://localhost:11434/v1"
    _models_list_cache: List[str] = []
