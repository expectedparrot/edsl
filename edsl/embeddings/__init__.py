"""Embeddings module for EDSL.

This module provides functionality for document embedding, storage, and similarity search.

.. deprecated::
    This module is deprecated. Use the embeddings service instead:
    ``ScenarioList([...]).embeddings.generate(field="text_field")``
    This module will be removed in a future version.
"""

import warnings

warnings.warn(
    "The edsl.embeddings module is deprecated. "
    "Use ScenarioList([...]).embeddings.generate(field='text_field') instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)

from edsl.embeddings.embeddings_engine import EmbeddingsEngine
from edsl.embeddings.embedding_function import EmbeddingFunction

__all__ = ["EmbeddingsEngine", "EmbeddingFunction"]
