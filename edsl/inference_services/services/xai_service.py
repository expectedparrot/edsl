from typing import Any, List
from edsl.inference_services.OpenAIService import OpenAIService


class XAIService(OpenAIService):
    """Openai service class."""

    _inference_service_ = "xai"
    _env_key_name_ = "XAI_API_KEY"
    _base_url_ = "https://api.x.ai/v1"
    _models_list_cache: List[str] = []
