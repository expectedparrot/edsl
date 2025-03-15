from typing import List

from .open_ai_service import OpenAIService

class XAIService(OpenAIService):
    """Openai service class."""

    _inference_service_ = "xai"
    _env_key_name_ = "XAI_API_KEY"
    _base_url_ = "https://api.x.ai/v1"
    _models_list_cache: List[str] = []
