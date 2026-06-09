import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .language_model import LanguageModel
    from .model import Model
    from .model_list import ModelList
    from .exceptions import LanguageModelBadResponseError
    from .model_list_git import ModelListGitError, ModelListGitNestedRepoWarning

__all__ = [
    "Model",
    "ModelList",
    "LanguageModelBadResponseError",
    "LanguageModel",
    "ModelListGitError",
    "ModelListGitNestedRepoWarning",
]

# Lazy loading to avoid circular imports during Survey import
_LAZY_IMPORTS = {
    "LanguageModel": ".language_model",
    "Model": ".model",
    "ModelList": ".model_list",
    "LanguageModelBadResponseError": ".exceptions",
    "ModelListGitError": ".model_list_git",
    "ModelListGitNestedRepoWarning": ".model_list_git",
}


def __getattr__(name: str):
    """Lazy import for language_models module to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        module_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_name, package="edsl.language_models")
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
