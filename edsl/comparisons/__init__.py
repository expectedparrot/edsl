from __future__ import annotations

__version__ = "0.1.0"

"""EDSL Comparisons – helper library for analysing EDSL `Results` objects.

The sub-modules expose:

• ``comparisons.metrics`` – individual comparison metrics
• ``comparisons.factory`` – `ComparisonFactory`
• ``comparisons.answer_comparison`` – `AnswerComparison` container
• ``comparisons.comparison_results`` – `ComparisonResults` container
• ``comparisons.utils`` – utility functions like `local_results_cache`
• ``comparisons.visualization`` – rich/Matplotlib rendering helpers
• ``comparisons.results_comparison`` – high-level `ResultPairComparison` wrapper
"""

from .metrics import (
    ComparisonFunction,
    Overlap,
    JaccardSimilarity,
    SquaredDistance,
    ExactMatch,
    CosineSimilarity,
    LLMSimilarity,
)
from .factory import ComparisonFactory, ComparisonOutput
from .answer_comparison import AnswerComparison
from .comparison_results import ComparisonResults
from .utils import local_results_cache
from .visualization import render_comparison_table, render_metric_heatmap
from .result_pair_comparison import (
    ResultPairComparison,
    ResultDifferences,
    example_metric_weighting_dict,
    example_question_weighting_dict,
    single_metric_weighting_dict,
    single_question_weighting_dict,
)
from .weighted_score_visualization import WeightedScoreVisualization
from .comparison_formatter import ComparisonFormatter
from .compare_candidates import CompareCandidates
from .compare_results_to_gold import CompareResultsToGold
from .batch_compare import BatchCompare
from .persona_pipeline import PersonaPipeline
from .agent_optimizer import AgentOptimizer, SelectionStrategy
from .optimization_results import OptimizationResults
from .performance_delta import PerformanceDelta
from .create_agent_delta import (
    create_agent_delta_from_comparison,
    analyze_and_update_agent,
    batch_create_agent_deltas,
    create_agent_list_deltas_from_comparisons,
)

__all__ = [
    "ComparisonFunction",
    "Overlap",
    "JaccardSimilarity",
    "SquaredDistance",
    "ExactMatch",
    "CosineSimilarity",
    "LLMSimilarity",
    "ComparisonFactory",
    "ComparisonOutput",
    "AnswerComparison",
    "ComparisonResults",
    "local_results_cache",
    "render_comparison_table",
    "render_metric_heatmap",
    "ResultPairComparison",
    "ResultDifferences",
    "WeightedScoreVisualization",
    "example_metric_weighting_dict",
    "example_question_weighting_dict",
    "single_metric_weighting_dict",
    "single_question_weighting_dict",
    "CompareCandidates",
    "ComparisonFormatter",
    "CompareResultsToGold",
    "BatchCompare",
    "PersonaPipeline",
    "AgentOptimizer",
    "OptimizationResults",
    "SelectionStrategy",
    "PerformanceDelta",
    "create_agent_delta_from_comparison",
    "analyze_and_update_agent",
    "batch_create_agent_deltas",
    "create_agent_list_deltas_from_comparisons",
] 