from __future__ import annotations

"""Compare two candidate results against a shared gold standard."""

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList
    from .result_pair_comparison import ResultPairComparison


class CompareCandidates:
    """Compare two candidate results against a shared gold standard.

    Takes two ResultPairComparison objects where result_B (the gold standard)
    should be identical in both. Produces a ScenarioList showing which
    candidate performs better on each metric for each question.
    """

    def __init__(
        self,
        results_comparison_a: "ResultPairComparison",
        results_comparison_b: "ResultPairComparison",
    ):
        """Initialize with two ResultPairComparison objects.

        Args:
            results_comparison_a: First comparison (candidate_1 vs gold standard)
            results_comparison_b: Second comparison (candidate_2 vs gold standard)

        Note:
            The result_B in both comparisons should be the same (gold standard).
        """
        self.results_comparison_a = results_comparison_a
        self.results_comparison_b = results_comparison_b

    def compare(self) -> "ScenarioList":
        """Compare the two candidates and return a ScenarioList with performance data.

        Returns:
            ScenarioList with columns:
            - question_name: Name of the question
            - metric_name: Name of the metric being compared
            - candidate_answer_1: Answer from first candidate
            - candidate_answer_2: Answer from second candidate
            - candidate_metric_value_1: Metric value for first candidate
            - candidate_metric_value_2: Metric value for second candidate
            - actual_answer: The gold standard answer
            - winner: Which candidate performed better ('candidate_1', 'candidate_2', or 'tie')

        Examples:
            >>> from edsl.comparisons import ResultPairComparison, CompareCandidates
            >>> rc1 = ResultPairComparison.example()
            >>> rc2 = ResultPairComparison.example()
            >>> cc = CompareCandidates(rc1, rc2)
            >>> sl = cc.compare()
            >>> len(sl) > 0
            True
        """
        from edsl.scenarios import Scenario, ScenarioList

        # Get comparisons from both
        comp_a = self.results_comparison_a.comparison
        comp_b = self.results_comparison_b.comparison

        # Get metric names
        metric_names = [
            str(fn)
            for fn in self.results_comparison_a.comparison_factory.comparison_fns
        ]

        # Build scenarios
        scenarios = []

        # Get the gold standard answer (result_B, which should be the same in both)
        for question_name in comp_a.keys():
            if question_name not in comp_b:
                continue

            metrics_a = comp_a[question_name]
            metrics_b = comp_b[question_name]

            # Get the actual answer (from result_B, the gold standard)
            actual_answer = metrics_a.answer_b  # result_B is the gold standard

            # Get candidate answers
            candidate_answer_1 = metrics_a.answer_a  # result_A from first comparison
            candidate_answer_2 = metrics_b.answer_a  # result_A from second comparison

            # For each metric, create a row
            for metric_name in metric_names:
                value_1 = metrics_a[metric_name]
                value_2 = metrics_b[metric_name]

                # Determine winner (higher is better for similarity metrics)
                winner = self._determine_winner(value_1, value_2)

                row = {
                    "question_name": str(question_name),
                    "metric_name": metric_name,
                    "candidate_answer_1": candidate_answer_1,
                    "candidate_answer_2": candidate_answer_2,
                    "candidate_metric_value_1": value_1,
                    "candidate_metric_value_2": value_2,
                    "actual_answer": actual_answer,
                    "winner": winner,
                }

                scenarios.append(Scenario(row))

        return ScenarioList(scenarios)

    def _determine_winner(
        self, value_1: Any, value_2: Any, tie_threshold: float = 0.001
    ) -> str:
        """Determine which candidate has the better metric value.

        Args:
            value_1: Metric value for candidate 1
            value_2: Metric value for candidate 2
            tie_threshold: Values within this threshold are considered tied

        Returns:
            'candidate_1', 'candidate_2', or 'tie'
        """
        # Handle None values
        if value_1 is None and value_2 is None:
            return "tie"
        if value_1 is None:
            return "candidate_2"
        if value_2 is None:
            return "candidate_1"

        # Convert booleans to numeric
        if isinstance(value_1, bool):
            value_1 = 1.0 if value_1 else 0.0
        if isinstance(value_2, bool):
            value_2 = 1.0 if value_2 else 0.0

        # Try to convert to float for comparison
        try:
            v1 = float(value_1)
            v2 = float(value_2)

            # Check if within tie threshold
            if abs(v1 - v2) <= tie_threshold:
                return "tie"

            # Higher is better for similarity metrics
            return "candidate_1" if v1 > v2 else "candidate_2"
        except (TypeError, ValueError):
            # If we can't convert to numeric, check for equality
            return "tie" if value_1 == value_2 else "candidate_1"


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
