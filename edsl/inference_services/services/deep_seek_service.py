from typing import List

from .open_ai_service import OpenAIService


class DeepSeekService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "deepseek"
    _env_key_name_ = "DEEPSEEK_API_KEY"
    _base_url_ = "https://api.deepseek.com"
    _models_list_cache: List[str] = []
