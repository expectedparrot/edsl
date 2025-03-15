from typing import List

import groq

from .open_ai_service import OpenAIService

class GroqService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "groq"
    _env_key_name_ = "GROQ_API_KEY"

    _sync_client_ = groq.Groq
    _async_client_ = groq.AsyncGroq

    model_exclude_list = ["whisper-large-v3", "distil-whisper-large-v3-en"]

    # _base_url_ = "https://api.deepinfra.com/v1/openai"
    _base_url_ = None
    _models_list_cache: List[str] = []
