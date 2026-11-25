"""xAI Responses API service for Grok's hosted tools."""

from .open_ai_service_v2 import OpenAIServiceV2


class XAIResponsesService(OpenAIServiceV2):
    """xAI's OpenAI-compatible Responses API, including hosted tools."""

    _inference_service_ = "xai_responses"
    _env_key_name_ = "XAI_API_KEY"
    _base_url_ = "https://api.x.ai/v1"
    _supports_files_api_ = False

