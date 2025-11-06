from __future__ import annotations

"""Scoring logic for ResultPairComparison - weighted scoring and visualization."""

from typing import Dict, Optional, List, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from ..result_pair_comparison import ResultPairComparison


class ResultPairScorer:
    """Handles weighted scoring logic for ResultPairComparison objects."""

    def __init__(self, result_comparison: "ResultPairComparison"):
        """Initialize scorer with a ResultPairComparison instance.

        Args:
            result_comparison: The ResultPairComparison to score
        """
        self.result_comparison = result_comparison
        self.comparison = result_comparison.comparison
        self.comparison_factory = result_comparison.comparison_factory
        self._cached_scores = result_comparison._cached_scores

    def validate_metric_weights(self, metric_weights: Dict[str, float]) -> None:
        """Ensure provided *metric_weights* match the metrics produced by the factory.

        Raises
        ------
        ValueError
            If a metric defined by the factory has no corresponding weight or
            an unknown metric is specified in *metric_weights*.
        """

        if metric_weights is None:
            return

        # Expected metric names (string representation of comparison functions)
        expected_metrics = {str(fn) for fn in self.comparison_factory.comparison_fns}

        provided_metrics = set(metric_weights.keys())

        missing = expected_metrics - provided_metrics
        extra = provided_metrics - expected_metrics

        if missing or extra:
            messages: List[str] = []
            if missing:
                messages.append(
                    "Missing weights for metrics: " + ", ".join(sorted(missing))
                )
            if extra:
                messages.append(
                    "Unexpected metrics provided: " + ", ".join(sorted(extra))
                )
            raise ValueError("; ".join(messages))

    def validate_question_weights(
        self, question_weights: Dict[str, float], questions: Sequence[str]
    ) -> None:
        """Validate *question_weights* covers each question exactly once."""

        expected = set(questions)
        provided = set(question_weights.keys())

        missing = expected - provided
        extra = provided - expected

        if missing or extra:
            msgs: List[str] = []
            if missing:
                msgs.append(
                    "Missing weights for questions: " + ", ".join(sorted(missing))
                )
            if extra:
                msgs.append(
                    "Unexpected questions provided: " + ", ".join(sorted(extra))
                )
            raise ValueError("; ".join(msgs))

    def weighted_score(
        self,
        metric_weights: Optional[Dict[str, float]] = None,
        question_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute a weighted score using metric and question weights.

        The score is normalized to be a float between [0, 1] by normalizing the
        metric weights to sum to 1. Question weights are used to compute weighted
        averages within each metric.

        Parameters
        ----------
        metric_weights
            Mapping *metric_name* -> *weight* used for aggregation.
            The argument is required; omitting it raises a ``ValueError``.
            Weights are automatically normalized to sum to 1.
        question_weights
            Mapping *question_name* -> *weight* used for aggregation.
            The argument is optional; if omitted, all questions are weighted equally (weight of 1).

        Returns
        -------
        float
            Normalized score between 0 and 1.
        """

        if metric_weights is None:
            raise ValueError("metric_weights must be provided for weighted_score().")

        # Default question weights equal for all questions if not provided
        if question_weights is None:
            question_weights = {q: 1.0 for q in self.comparison.keys()}
        else:
            self.validate_question_weights(question_weights, self.comparison.keys())

        # Validate provided weights
        self.validate_metric_weights(metric_weights)

        # Normalize metric weights to sum to 1 for [0, 1] score range
        total_metric_weight = sum(metric_weights.values())
        if total_metric_weight == 0:
            return 0.0

        normalized_metric_weights = {
            name: weight / total_metric_weight
            for name, weight in metric_weights.items()
        }

        cache_key = (
            frozenset(normalized_metric_weights.items()),
            frozenset(question_weights.items()),
        )
        if cache_key in self._cached_scores:
            return self._cached_scores[cache_key]

        total = 0.0
        for metric_name, weight in normalized_metric_weights.items():
            # Gather values for this metric across all questions
            weighted_vals: List[float] = []
            weights_q: List[float] = []
            for qname, ac in self.comparison.items():
                v = ac[metric_name]
                if v is None:
                    continue
                # Booleans -> numeric
                if isinstance(v, bool):
                    v = 1.0 if v else 0.0
                else:
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue

                wq = question_weights.get(qname, 1.0)
                weighted_vals.append(v * wq)
                weights_q.append(wq)

            metric_avg = (
                sum(weighted_vals) / sum(weights_q)
                if weights_q and sum(weights_q) != 0
                else 0.0
            )
            total += weight * metric_avg

        # Cache and return
        self._cached_scores[cache_key] = total
        return total

    def visualize_weighted_score(
        self,
        metric_weights: Optional[Dict[str, float]] = None,
        question_weights: Optional[Dict[str, float]] = None,
    ) -> "WeightedScoreVisualization":
        """Create a detailed visualization of the weighted score calculation.

        Returns a WeightedScoreVisualization object that shows a breakdown table
        with each metric, question, their weights, and contribution to the final score.

        If no weights are provided, uses default equal weighting for all metrics
        and questions, making this method work out-of-the-box.

        Parameters
        ----------
        metric_weights
            Mapping *metric_name* -> *weight* used for aggregation.
            If None, uses equal weights for all metrics (default).
            Weights are automatically normalized to sum to 1.
        question_weights
            Mapping *question_name* -> *weight* used for aggregation.
            If None, all questions are weighted equally (weight of 1.0).

        Returns
        -------
        WeightedScoreVisualization
            Visualization object with _repr_html_ for displaying the breakdown table
        """
        from ..weighted_score_visualization import WeightedScoreVisualization
        from .weighting import example_metric_weighting_dict

        # Use default equal weights if none provided
        if metric_weights is None:
            metric_weights = example_metric_weighting_dict(
                self.comparison_factory, weight=1.0
            )

        # Default question weights equal for all questions if not provided
        if question_weights is None:
            question_weights = {q: 1.0 for q in self.comparison.keys()}
        else:
            self.validate_question_weights(question_weights, self.comparison.keys())

        # Validate provided weights
        self.validate_metric_weights(metric_weights)

        # Normalize metric weights to sum to 1 for [0, 1] score range
        total_metric_weight = sum(metric_weights.values())
        if total_metric_weight == 0:
            # Return empty visualization
            return WeightedScoreVisualization(
                result_comparison=self.result_comparison,
                metric_weights={},
                question_weights=question_weights,
                final_score=0.0,
                breakdown=[],
            )

        normalized_metric_weights = {
            name: weight / total_metric_weight
            for name, weight in metric_weights.items()
        }

        # Build detailed breakdown
        breakdown = []
        total = 0.0

        for metric_name, weight in normalized_metric_weights.items():
            # Gather values for this metric across all questions
            questions_data = []
            weighted_vals: List[float] = []
            weights_q: List[float] = []

            for qname, ac in self.comparison.items():
                v = ac[metric_name]
                wq = question_weights.get(qname, 1.0)

                # Convert value to float if possible
                numeric_v = None
                if v is not None:
                    if isinstance(v, bool):
                        numeric_v = 1.0 if v else 0.0
                    else:
                        try:
                            numeric_v = float(v)
                        except (TypeError, ValueError):
                            pass

                # Store question data
                weighted_score = (numeric_v * wq) if numeric_v is not None else None
                questions_data.append(
                    {
                        "question": qname,
                        "score": numeric_v,
                        "question_weight": wq,
                        "weighted_score": weighted_score,
                    }
                )

                # Accumulate for average
                if numeric_v is not None:
                    weighted_vals.append(numeric_v * wq)
                    weights_q.append(wq)

            metric_avg = (
                sum(weighted_vals) / sum(weights_q)
                if weights_q and sum(weights_q) != 0
                else 0.0
            )

            breakdown.append(
                {
                    "metric_name": metric_name,
                    "metric_weight": weight,
                    "metric_avg": metric_avg,
                    "questions": questions_data,
                }
            )

            total += weight * metric_avg

        return WeightedScoreVisualization(
            result_comparison=self.result_comparison,
            metric_weights=normalized_metric_weights,
            question_weights=question_weights,
            final_score=total,
            breakdown=breakdown,
        )
