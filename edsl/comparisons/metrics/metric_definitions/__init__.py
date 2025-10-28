"""Metric definitions for EDSL comparison functions.

This package contains individual metric implementations that inherit from
ComparisonFunction ABC.
"""

from .overlap import Overlap
from .jaccard_similarity import JaccardSimilarity
from .squared_distance import SquaredDistance
from .exact_match import ExactMatch
from .cosine_similarity import CosineSimilarity, SENTENCE_TRANSFORMERS_AVAILABLE
from .llm_similarity import LLMSimilarity

__all__ = [
    "Overlap",
    "JaccardSimilarity",
    "SquaredDistance",
    "ExactMatch",
    "CosineSimilarity",
    "LLMSimilarity",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]
