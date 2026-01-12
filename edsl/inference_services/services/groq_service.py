from typing import List, Dict

from .open_ai_service import OpenAIService

# Lazy import for groq - only loaded when actually used
_groq = None


def _get_groq():
    """Lazy import of groq module."""
    global _groq
    if _groq is None:
        try:
            import groq

            _groq = groq
        except ImportError:
            raise ImportError(
                "The 'groq' package is required to use Groq models. "
                "Please install it with: pip install edsl[groq] "
                "or: pip install groq"
            )
    return _groq


class GroqService(OpenAIService):
    """Groq service class."""

    _inference_service_ = "groq"
    _env_key_name_ = "GROQ_API_KEY"

    # These are lazily loaded
    _sync_client_ = None
    _async_client_ = None

    _base_url_ = None
    _models_list_cache: List[str] = []
    _sync_client_instances: Dict[str, object] = {}
    _async_client_instances: Dict[str, object] = {}

    @classmethod
    def sync_client(cls, api_key):
        """Get or create a sync client instance with lazy import."""
        if api_key not in cls._sync_client_instances:
            groq = _get_groq()
            client = groq.Groq(api_key=api_key)
            cls._sync_client_instances[api_key] = client
        return cls._sync_client_instances[api_key]

    @classmethod
    def async_client(cls, api_key):
        """Get or create an async client instance with lazy import."""
        if api_key not in cls._async_client_instances:
            groq = _get_groq()
            client = groq.AsyncGroq(api_key=api_key)
            cls._async_client_instances[api_key] = client
        return cls._async_client_instances[api_key]
