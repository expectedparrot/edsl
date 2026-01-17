"""EDSL Comparison Metrics Package.

This package provides comparison metrics for evaluating EDSL answer similarity.
"""

from .metrics_abc import ComparisonFunction, optional_import
from .metric_definitions import (
    Overlap,
    JaccardSimilarity,
    SquaredDistance,
    ExactMatch,
    CosineSimilarity,
    OpenAICosineSimilarity,
    LLMSimilarity,
    SENTENCE_TRANSFORMERS_AVAILABLE,
)
from .metrics_collection import MetricsCollection

__all__ = [
    # ABC and utilities
    "ComparisonFunction",
    "optional_import",
    # Individual metrics
    "Overlap",
    "JaccardSimilarity",
    "SquaredDistance",
    "ExactMatch",
    "CosineSimilarity",
    "OpenAICosineSimilarity",
    "LLMSimilarity",
    # Collection class
    "MetricsCollection",
    # Constants
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]
