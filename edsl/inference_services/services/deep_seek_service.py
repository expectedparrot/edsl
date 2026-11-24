from .open_ai_service import OpenAIService


class DeepSeekService(OpenAIService):
    """DeepInfra service class."""

    _inference_service_ = "deepseek"
    _env_key_name_ = "DEEPSEEK_API_KEY"
    _base_url_ = "https://api.deepseek.com"

    @classmethod
    def _is_reasoning_model(cls, model_name: str) -> bool:
        # DeepSeek's current V4 API defaults to thinking mode; the effort field
        # controls its depth and the output cap includes reasoning tokens.
        return "deepseek-v4" in model_name.lower() or "deepseek-reasoner" in model_name.lower()

    @classmethod
    def _default_reasoning_effort(cls, model_name: str):
        # EDSL currently calls DeepSeek through Chat Completions, while its
        # documented effort control belongs to the Responses API.
        return None
