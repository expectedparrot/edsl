from typing import Any, List
from edsl.inference_services.OpenAIService import OpenAIService


class GrokService(OpenAIService):
    """Openai service class."""

    _inference_service_ = "grok"
    _env_key_name_ = "GROQ_API_KEY"
    _base_url_ = "https://api.x.ai/v1"
    _models_list_cache: List[str] = []
