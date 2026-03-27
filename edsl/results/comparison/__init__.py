"""Comparison sub-module for EDSL results."""

from .comparison import ResultPairComparison
from .compare_to_gold import CompareResultsToGold
from .metrics import (
    MetricsCollection,
    exact_match,
    overlap,
    jaccard_similarity,
    cosine_metric_from_embed_fn,
    make_cosine_metric,
    make_openai_cosine_metric,
)
from .scoring import weighted_score
from .answers_compare import AnswersCompare

__all__ = [
    "ResultPairComparison",
    "CompareResultsToGold",
    "MetricsCollection",
    "exact_match",
    "overlap",
    "jaccard_similarity",
    "make_cosine_metric",
    "weighted_score",
    "AnswersCompare",
]
