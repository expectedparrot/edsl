from typing import Optional, Dict, Sequence, Any, List
from dataclasses import dataclass

from ..result_pair_comparison.result_pair_comparison import ResultPairComparison


@dataclass
class MetricBreakdown:
    """Breakdown of a single metric's contribution to the overall score."""

    metric_name: str
    metric_weight: float
    normalized_weight: float
    questions: List[Dict[str, Any]]
    metric_avg: float
    contribution: float


class ScoreComparison:
    """Scoring and weighting functionality for ResultPairComparison.

    Handles validation, calculation, and visualization of weighted scores
    based on metric and question weights.
    """

    def __init__(self, result_pair_comparison: "ResultPairComparison"):
        """Initialize with a ResultPairComparison instance.

        Args:
            result_pair_comparison: The ResultPairComparison to score
        """
        self.rpc = result_pair_comparison
        self._cached_score: Optional[float] = None
        self._cached_weights: Optional[tuple] = None

    def validate_metric_weights(self, metric_weights: Dict[str, float]) -> None:
        """Validate that metric_weights match the metrics produced by the metrics collection.

        Args:
            metric_weights: Mapping of metric_name -> weight

        Raises:
            ValueError: If a metric defined by the metrics collection has no corresponding weight
                       or an unknown metric is specified in metric_weights.
        """
        if metric_weights is None:
            raise ValueError("metric_weights cannot be None")

        # Get all metrics from the metrics collection
        collection_metrics = set(str(fn) for fn in self.rpc.metrics_collection.metrics)
        provided_metrics = set(metric_weights.keys())

        # Check for missing metrics
        missing = collection_metrics - provided_metrics
        if missing:
            raise ValueError(
                f"metric_weights is missing weights for: {sorted(missing)}. "
                f"Expected metrics: {sorted(collection_metrics)}"
            )

        # Check for unknown metrics
        unknown = provided_metrics - collection_metrics
        if unknown:
            raise ValueError(
                f"metric_weights contains unknown metrics: {sorted(unknown)}. "
                f"Valid metrics: {sorted(collection_metrics)}"
            )

        # Check that all weights are numeric
        for metric, weight in metric_weights.items():
            if not isinstance(weight, (int, float)):
                raise ValueError(
                    f"Weight for metric '{metric}' must be numeric, got {type(weight)}"
                )

    def validate_question_weights(
        self, question_weights: Dict[str, float], questions: Sequence[str]
    ) -> None:
        """Validate that question_weights covers each question exactly once.

        Args:
            question_weights: Mapping of question_name -> weight
            questions: Sequence of question names to validate against

        Raises:
            ValueError: If question_weights doesn't match the questions exactly
        """
        if question_weights is None:
            raise ValueError("question_weights cannot be None")

        provided_questions = set(question_weights.keys())
        expected_questions = set(questions)

        # Check for missing questions
        missing = expected_questions - provided_questions
        if missing:
            raise ValueError(
                f"question_weights is missing weights for: {sorted(missing)}"
            )

        # Check for unknown questions
        unknown = provided_questions - expected_questions
        if unknown:
            raise ValueError(
                f"question_weights contains unknown questions: {sorted(unknown)}. "
                f"Valid questions: {sorted(expected_questions)}"
            )

        # Check that all weights are numeric
        for question, weight in question_weights.items():
            if not isinstance(weight, (int, float)):
                raise ValueError(
                    f"Weight for question '{question}' must be numeric, got {type(weight)}"
                )

    def weighted_score(
        self,
        metric_weights: Optional[Dict[str, float]] = None,
        question_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute a weighted score using metric and question weights.

        The score is normalized to be a float between [0, 1] by normalizing the
        metric weights to sum to 1. Question weights are used to compute weighted
        averages within each metric.

        Args:
            metric_weights: Mapping metric_name -> weight used for aggregation.
                          Optional; if omitted, all metrics weighted equally (1.0).
                          Weights are automatically normalized to sum to 1.
            question_weights: Mapping question_name -> weight used for aggregation.
                            Optional; if omitted, all questions weighted equally (1.0).

        Returns:
            Normalized score between 0 and 1.

        Raises:
            ValueError: If validation fails

        Examples:
            >>> sc = ScoreComparison.example()
            >>> score = sc.weighted_score()
            >>> 0 <= score <= 1
            True
        """
        # Set default metric weights if not provided
        if metric_weights is None:
            metric_weights = {str(m): 1.0 for m in self.rpc.metrics_collection.metrics}

        # Check cache
        cache_key = (
            frozenset(metric_weights.items()) if metric_weights else None,
            frozenset(question_weights.items()) if question_weights else None,
        )
        if cache_key == self._cached_weights and self._cached_score is not None:
            return self._cached_score

        # Validate the provided weights
        self.validate_metric_weights(metric_weights)

        # Get all questions from the comparison
        all_questions = list(self.rpc.keys())

        # Set default question weights if not provided
        if question_weights is None:
            question_weights = {q: 1.0 for q in all_questions}
        else:
            self.validate_question_weights(question_weights, all_questions)

        # Normalize metric weights to sum to 1
        total_metric_weight = sum(metric_weights.values())
        if total_metric_weight == 0:
            raise ValueError("Sum of metric_weights cannot be zero")

        normalized_metric_weights = {
            m: w / total_metric_weight for m, w in metric_weights.items()
        }

        # Calculate weighted score
        final_score = 0.0

        for metric_name, metric_weight in normalized_metric_weights.items():
            # Calculate weighted average for this metric across all questions
            metric_sum = 0.0
            weight_sum = 0.0

            for question_name in all_questions:
                comparison = self.rpc[question_name]
                metric_value = comparison[metric_name]

                # Skip None values
                if metric_value is not None:
                    q_weight = question_weights[question_name]

                    # Convert boolean to float
                    if isinstance(metric_value, bool):
                        metric_value = 1.0 if metric_value else 0.0

                    metric_sum += metric_value * q_weight
                    weight_sum += q_weight

            # Calculate weighted average for this metric
            if weight_sum > 0:
                metric_avg = metric_sum / weight_sum
                final_score += metric_avg * metric_weight

        # Cache the result
        self._cached_score = final_score
        self._cached_weights = cache_key

        return final_score

    @classmethod
    def example(cls) -> "ScoreComparison":
        """Return a ScoreComparison instance based on ResultPairComparison.example().

        Examples:
            >>> sc = ScoreComparison.example()
            >>> isinstance(sc, ScoreComparison)
            True
            >>> len(sc.rpc) > 0
            True
        """
        rpc = ResultPairComparison.example()
        return cls(rpc)


if __name__ == "__main__":  # pragma: no cover
    import doctest

    doctest.testmod()
    sc = ScoreComparison.example()
    print(sc.weighted_score())
