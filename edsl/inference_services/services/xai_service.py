from .open_ai_service import OpenAIService


class XAIService(OpenAIService):
    """XAI service class."""

    _inference_service_ = "xai"
    _env_key_name_ = "XAI_API_KEY"
    _base_url_ = "https://api.x.ai/v1"
    _supports_files_api_ = False

    @classmethod
    def _is_reasoning_model(cls, model_name: str) -> bool:
        import re

        match = re.search(r"grok-(\d+)\.(\d+)", model_name.lower())
        return bool(match and (int(match.group(1)), int(match.group(2))) >= (4, 5))
