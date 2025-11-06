from __future__ import annotations

"""Helper class for evaluating and comparing persona iterations."""

from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .result_pair_comparison import ResultPairComparison

from .compare_candidates import CompareCandidates
from .result_pair_helpers import (
    example_metric_weighting_dict,
    example_question_weighting_dict,
)


@dataclass
class EvaluationResult:
    """Results from comparing a candidate against the current best.

    Attributes:
        is_improvement: Whether the candidate is better than the current best
        wins_best: Number of metrics where current best won
        wins_candidate: Number of metrics where candidate won
        ties: Number of tied metrics
        weighted_score_best: Weighted score for current best (0-1 scale)
        weighted_score_candidate: Weighted score for candidate (0-1 scale)
        weighted_score_delta: Difference (candidate - best)
        win_rate_candidate: Proportion of wins for candidate
        improvement_margin: Raw difference in win counts (candidate - best)
        best_metrics: Detailed per-question, per-metric performance for best
        comparison_table: Full comparison table as ScenarioList
    """

    is_improvement: bool
    wins_best: int
    wins_candidate: int
    ties: int
    weighted_score_best: float
    weighted_score_candidate: float
    weighted_score_delta: float
    win_rate_candidate: float
    improvement_margin: int
    best_metrics: Dict[str, Any]
    comparison_table: Any  # ScenarioList type


class IterationEvaluator:
    """Evaluates a candidate persona against the current best.

    Compares two ResultPairComparison objects (each comparing an agent to gold
    standard) and determines which performs better using win counts, weighted
    scores, and detailed metric analysis.
    """

    def __init__(
        self,
        best_comparison: "ResultPairComparison",
        candidate_comparison: "ResultPairComparison",
        metric_weights: Optional[Dict[str, float]] = None,
        question_weights: Optional[Dict[str, float]] = None,
    ):
        """Initialize the evaluator.

        Args:
            best_comparison: Comparison of current best agent vs gold standard
            candidate_comparison: Comparison of candidate agent vs gold standard
            metric_weights: Optional weights for each metric (defaults to equal weights)
            question_weights: Optional weights for each question (defaults to equal weights)
        """
        self.best_comparison = best_comparison
        self.candidate_comparison = candidate_comparison

        # Use provided weights or generate defaults
        self.metric_weights = metric_weights or example_metric_weighting_dict(
            best_comparison.comparison_factory
        )
        self.question_weights = question_weights or example_question_weighting_dict(
            best_comparison
        )

        self._comparison_table = None
        self._evaluation_result = None

    def evaluate(self) -> EvaluationResult:
        """Run full evaluation and return structured results.

        Returns:
            EvaluationResult containing all metrics and decision
        """
        # Run comparison
        cc = CompareCandidates(
            results_comparison_a=self.best_comparison,
            results_comparison_b=self.candidate_comparison,
        )

        comparison_table = cc.compare()
        self._comparison_table = comparison_table

        # Extract win counts
        tally_results = comparison_table.tally("winner")
        tally_data = tally_results.to_dicts()

        wins_best = next(
            (r["count"] for r in tally_data if r["winner"] == "candidate_1"), 0
        )
        wins_candidate = next(
            (r["count"] for r in tally_data if r["winner"] == "candidate_2"), 0
        )
        ties = next((r["count"] for r in tally_data if r["winner"] == "tie"), 0)

        # Calculate weighted scores
        weighted_score_best = self.best_comparison.weighted_score(
            self.metric_weights, self.question_weights
        )
        weighted_score_candidate = self.candidate_comparison.weighted_score(
            self.metric_weights, self.question_weights
        )
        weighted_score_delta = weighted_score_candidate - weighted_score_best

        # Extract detailed metrics for the best agent
        best_metrics = self._extract_detailed_metrics(self.best_comparison)

        # Calculate derived metrics
        total_decisions = wins_best + wins_candidate + ties
        win_rate_candidate = (
            wins_candidate / total_decisions if total_decisions > 0 else 0
        )
        improvement_margin = wins_candidate - wins_best

        # Make decision based on weighted score
        is_improvement = weighted_score_candidate > weighted_score_best

        self._evaluation_result = EvaluationResult(
            is_improvement=is_improvement,
            wins_best=wins_best,
            wins_candidate=wins_candidate,
            ties=ties,
            weighted_score_best=weighted_score_best,
            weighted_score_candidate=weighted_score_candidate,
            weighted_score_delta=weighted_score_delta,
            win_rate_candidate=win_rate_candidate,
            improvement_margin=improvement_margin,
            best_metrics=best_metrics,
            comparison_table=comparison_table,
        )

        return self._evaluation_result

    def _extract_detailed_metrics(
        self, comparison: "ResultPairComparison"
    ) -> Dict[str, Any]:
        """Extract per-question, per-metric performance data.

        Args:
            comparison: The ResultPairComparison to extract metrics from

        Returns:
            Dictionary with hierarchical metric names and values
        """
        metrics = {}

        # Extract per-question, per-metric performance
        for question_name, answer_comparison in comparison.comparison.items():
            metrics_dict = answer_comparison.to_dict()
            for metric_name, metric_value in metrics_dict.items():
                if isinstance(metric_value, (int, float)):
                    # Create hierarchical metric names
                    metrics[f"best_performance/{question_name}/{metric_name}"] = (
                        metric_value
                    )

        # Calculate average metrics across all questions
        metric_types = set()
        for key in metrics.keys():
            metric_type = key.split("/")[-1]
            metric_types.add(metric_type)

        for metric_type in metric_types:
            metric_values = [
                v for k, v in metrics.items() if k.endswith(f"/{metric_type}")
            ]
            if metric_values:
                metrics[f"best_avg/{metric_type}"] = sum(metric_values) / len(
                    metric_values
                )

        return metrics

    def print_summary(self, iteration: int):
        """Print a formatted summary of the evaluation.

        Args:
            iteration: The iteration number for labeling output
        """
        if self._evaluation_result is None:
            raise ValueError("Must call evaluate() before print_summary()")

        result = self._evaluation_result

        print(
            f"\n--- Iteration {iteration}: Detailed Comparison Table "
            f"(candidate_1=current_best, candidate_2=iteration_{iteration}) ---"
        )
        print(result.comparison_table.table())

        print(f"\n--- Iteration {iteration}: Win/Tie Summary ---")
        tally_results = result.comparison_table.tally("winner")
        print(tally_results.table())

        print(f"\n--- Iteration {iteration}: Weighted Scores (normalized [0,1]) ---")
        print(f"Current Best:     {result.weighted_score_best:.4f}")
        print(f"Candidate:        {result.weighted_score_candidate:.4f}")

        status = (
            "(improvement)"
            if result.weighted_score_delta > 0
            else "(decline)" if result.weighted_score_delta < 0 else "(no change)"
        )
        print(f"Delta:            {result.weighted_score_delta:+.4f} {status}")

        decision_symbol = "✓" if result.is_improvement else "✗"
        decision_text = "IMPROVES" if result.is_improvement else "does not improve"
        print(
            f"\n{decision_symbol} Iteration {iteration} {decision_text} "
            f"(weighted score: {result.weighted_score_candidate:.4f} vs "
            f"{result.weighted_score_best:.4f}, delta: {result.weighted_score_delta:+.4f})"
        )
        print(
            f"  Win counts: New: {result.wins_candidate}, "
            f"Old: {result.wins_best}, Ties: {result.ties}"
        )

    def get_wandb_metrics(self, iteration: int) -> Dict[str, Any]:
        """Get metrics formatted for wandb logging.

        Args:
            iteration: The iteration number

        Returns:
            Dictionary of metrics ready for wandb.log()
        """
        if self._evaluation_result is None:
            raise ValueError("Must call evaluate() before get_wandb_metrics()")

        result = self._evaluation_result

        metrics = {
            "iteration": iteration,
            "wins_current_best": result.wins_best,
            "wins_candidate": result.wins_candidate,
            "ties": result.ties,
            "win_rate_candidate": result.win_rate_candidate,
            "improvement_margin": result.improvement_margin,
            "weighted_score_best": result.weighted_score_best,
            "weighted_score_candidate": result.weighted_score_candidate,
            "weighted_score_delta": result.weighted_score_delta,
            "accepted_improvement": 1 if result.is_improvement else 0,
        }

        # Add detailed performance metrics
        metrics.update(result.best_metrics)

        return metrics
