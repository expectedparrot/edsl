import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .embedding_cache import EmbeddingCache, EmbeddingCacheEntry
    from .embedding_model import EmbeddingModel
    from .embedding_result import EmbeddingResult

__all__ = ["EmbeddingCache", "EmbeddingCacheEntry", "EmbeddingModel", "EmbeddingResult"]

_LAZY_IMPORTS = {
    "EmbeddingCache": ".embedding_cache",
    "EmbeddingCacheEntry": ".embedding_cache",
    "EmbeddingModel": ".embedding_model",
    "EmbeddingResult": ".embedding_result",
}


def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name], package="edsl.embeddings")
        return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
