import aiohttp
import json
import requests
from typing import Any, List

# from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel

from edsl.inference_services.OpenAIService import OpenAIService


class DeepSeekService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "deepseek"
    _env_key_name_ = "DEEPSEEK_API_KEY"
    _base_url_ = "https://api.deepseek.com"
    _models_list_cache: List[str] = []
