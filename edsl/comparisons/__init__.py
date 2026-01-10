from __future__ import annotations

# Lazy imports to avoid loading heavy dependencies at import time
__all__ = [
    "ResultPairComparison",
    "CompareResultsToGold",
    "ResultDifferences",
    "AgentPersonaImprover",
    "EvaluateAgentsAgainstGold",
    "ScoreComparison",
]


def __getattr__(name):
    if name == "ResultPairComparison":
        from .result_pair_comparison.result_pair_comparison import ResultPairComparison

        return ResultPairComparison
    if name == "CompareResultsToGold":
        from .compare_results_to_gold import CompareResultsToGold

        return CompareResultsToGold
    if name == "ResultDifferences":
        from .result_differences import ResultDifferences

        return ResultDifferences
    if name == "AgentPersonaImprover":
        from .persona_improvement import AgentPersonaImprover

        return AgentPersonaImprover
    if name == "EvaluateAgentsAgainstGold":
        from .evaluate_agents_against_gold import EvaluateAgentsAgainstGold

        return EvaluateAgentsAgainstGold
    if name == "ScoreComparison":
        from .result_pair_comparison import ScoreComparison

        return ScoreComparison
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
