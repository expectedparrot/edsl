import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .language_model import LanguageModel
    from .model import Model
    from .model_list import ModelList
    from .hosted_model import HostedModel
    from .exceptions import LanguageModelBadResponseError

__all__ = [
    "Model",
    "ModelList",
    "HostedModel",
    "LanguageModelBadResponseError",
    "LanguageModel",
]

# Lazy loading to avoid circular imports during Survey import
_LAZY_IMPORTS = {
    "LanguageModel": ".language_model",
    "Model": ".model",
    "ModelList": ".model_list",
    "HostedModel": ".hosted_model",
    "LanguageModelBadResponseError": ".exceptions",
}


def __getattr__(name: str):
    """Lazy import for language_models module to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        module_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name, package="edsl.language_models")
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
