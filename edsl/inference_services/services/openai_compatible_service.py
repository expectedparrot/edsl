"""Generic service for local or self-hosted OpenAI-compatible endpoints."""

import os
from typing import Optional

from .open_ai_service import OpenAIService


class OpenAICompatibleService(OpenAIService):
    """Connect EDSL to llama.cpp, Ollama, LM Studio, vLLM, or similar servers."""

    _inference_service_ = "openai_compatible"
    _env_key_name_ = "OPENAI_COMPATIBLE_API_KEY"
    _base_url_ = "http://127.0.0.1:11434/v1"
    _supports_files_api_ = False
    _models_list_cache: Optional[list[str]] = None

    @classmethod
    def sync_client(cls, api_key, base_url=None):
        resolved = base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL") or cls._base_url_
        return super().sync_client(api_key or "local", base_url=resolved)

    @classmethod
    def async_client(cls, api_key, base_url=None):
        resolved = base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL") or cls._base_url_
        return super().async_client(api_key or "local", base_url=resolved)

    @classmethod
    def get_model_info(cls, api_key=None, base_url=None):
        api_key = api_key or os.getenv(cls._env_key_name_) or "local"
        base_url = base_url or os.getenv("OPENAI_COMPATIBLE_BASE_URL") or cls._base_url_
        raw_list = cls.sync_client(api_key, base_url=base_url).models.list()
        return raw_list.data if hasattr(raw_list, "data") else raw_list
