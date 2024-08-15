import aiohttp
import json
import requests
from typing import Any, List

# from edsl.inference_services.InferenceServiceABC import InferenceServiceABC
from edsl.language_models import LanguageModel

from edsl.inference_services.OpenAIService import OpenAIService


class DeepInfraService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "deep_infra"
    _env_key_name_ = "DEEP_INFRA_API_KEY"
    _base_url_ = "https://api.deepinfra.com/v1/openai"
    _models_list_cache: List[str] = []
