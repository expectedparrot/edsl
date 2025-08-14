from typing import List

from .open_ai_service import OpenAIService


class OpenRouterService(OpenAIService):
    """OpenRouter service class."""

    _inference_service_ = "open_router"
    _env_key_name_ = "OPEN_ROUTER_API_KEY"
    _base_url_ = "https://openrouter.ai/api/v1"
