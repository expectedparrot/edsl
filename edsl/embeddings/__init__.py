"""Embeddings module for EDSL.

This module provides functionality for document embedding, storage, and similarity search.
"""

from edsl.embeddings.embeddings_engine import EmbeddingsEngine
from edsl.embeddings.embedding_function import EmbeddingFunction

__all__ = ["EmbeddingsEngine", "EmbeddingFunction"]
