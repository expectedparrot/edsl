import aiohttp
import json
import requests
from typing import Any, List

# from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel

from edsl.inference_services.OpenAIService import OpenAIService


class OllamaService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "ollama"
    _env_key_name_ = "DEEP_INFRA_API_KEY"
    _base_url_ = "http://localhost:11434/v1"
    _models_list_cache: List[str] = []
