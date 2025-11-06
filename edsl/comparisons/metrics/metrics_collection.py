from __future__ import annotations

"""Factory that bundles together multiple comparison metrics."""

from typing import Sequence, Dict, Any
from .metrics_abc import ComparisonFunction
from .metric_definitions import (
    ExactMatch,
    CosineSimilarity,
    SquaredDistance,
    Overlap,
    JaccardSimilarity,
    # LLMSimilarity,
)


class MetricsCollection:
    """Collection of metrics that can be used to compare answers."""

    def __init__(self, comparison_fns: Sequence[ComparisonFunction] | None = None):
        """Initialize factory with optional comparison functions.

        Args:
            comparison_fns: Optional sequence of ComparisonFunction instances.
                          If None, creates an empty factory that requires
                          manual addition of functions before use.
        """
        if comparison_fns is None:
            comparison_fns = []
        for metric in comparison_fns:
            if not isinstance(metric, ComparisonFunction):
                raise TypeError(
                    f"Expected ComparisonFunction instance, got {type(metric).__name__}"
                )
        self.metrics = list[ComparisonFunction](comparison_fns)

    def add_metric(self, comparison_fn: ComparisonFunction) -> "MetricsCollection":
        """Add a single comparison function via dependency injection."""
        if not isinstance(comparison_fn, ComparisonFunction):
            raise TypeError(
                f"Expected ComparisonFunction instance, got {type(comparison_fn).__name__}"
            )
        self.metrics.append(comparison_fn)
        return self

    @classmethod
    def with_defaults(cls) -> "MetricsCollection":
        """Create a factory with a sensible set of default comparison functions.

        The default set includes:
        - ExactMatch: For categorical/exact comparisons
        - CosineSimilarity (two models): For semantic similarity (if available)
        - Overlap: For collection-based comparisons (recall-focused)
        - JaccardSimilarity: For collection-based comparisons (balanced)
        - SquaredDistance: For numerical comparisons

        Returns:
            ComparisonFactory configured with default comparison functions

        Examples:
            >>> factory = ComparisonFactory.with_defaults()
            >>> len(factory.comparison_fns) >= 2  # At least ExactMatch and Overlap
            True
            >>> any(isinstance(fn, ExactMatch) for fn in factory.comparison_fns)
            True
        """
        import os

        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            # for speed in doctests, only include ExactMatch
            return MetricsCollection([ExactMatch()])

        comparisons = [ExactMatch()]

        # Add CosineSimilarity functions only if sentence-transformers is available
        from .metric_definitions import SENTENCE_TRANSFORMERS_AVAILABLE

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            comparisons.extend(
                [
                    CosineSimilarity("all-MiniLM-L6-v2"),
                    CosineSimilarity("all-mpnet-base-v2"),
                ]
            )

        comparisons.extend(
            [
                SquaredDistance(),
                Overlap(),
                JaccardSimilarity(),
            ]
        )
        return MetricsCollection(comparisons)

    def compute_metrics(self, answer_a: Any, answer_b: Any) -> Dict[str, Any]:
        """Compute all metrics for a pair of answers.

        Returns:
            Dictionary mapping metric names to their computed values
        """
        d = {}
        for fnc in self.metrics:
            d[str(fnc)] = fnc.execute([answer_a], [answer_b])[0]
        return d

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize the MetricsCollection to a dictionary.

        Args:
            add_edsl_version: Whether to include the EDSL version in the output

        Returns:
            Dictionary representation of the collection

        Examples:
            >>> factory = MetricsCollection().add_metric(ExactMatch())
            >>> data = factory.to_dict(add_edsl_version=False)
            >>> data['comparison_fns'][0]['class_name']
            'ExactMatch'
            >>>
            >>> # Collection with CosineSimilarity includes model_name
            >>> factory = MetricsCollection().add_metric(CosineSimilarity("all-MiniLM-L6-v2"))
            >>> data = factory.to_dict(add_edsl_version=False)
            >>> data['comparison_fns'][0]['class_name']
            'CosineSimilarity'
            >>> data['comparison_fns'][0]['params']['model_name']
            'all-MiniLM-L6-v2'
        """
        result = {"comparison_fns": [fn.to_dict() for fn in self.metrics]}

        if add_edsl_version:
            from edsl import __version__

            result["edsl_version"] = __version__
            result["edsl_class_name"] = "MetricsCollection"

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsCollection":
        """Deserialize a MetricsCollection from a dictionary.

        Args:
            data: Dictionary representation of a collection

        Returns:
            New MetricsCollection instance

        Examples:
            >>> factory = MetricsCollection().add_metric(ExactMatch())
            >>> data = factory.to_dict(add_edsl_version=False)
            >>> restored = MetricsCollection.from_dict(data)
            >>> len(restored.metrics)
            1
            >>> isinstance(restored.metrics[0], ExactMatch)
            True
        """
        comparison_fns = [
            ComparisonFunction.from_dict(fn_data)
            for fn_data in data.get("comparison_fns", [])
        ]
        return cls(comparison_fns=comparison_fns)
