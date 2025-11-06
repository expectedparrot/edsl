from __future__ import annotations

"""Helper functions for creating weighting dictionaries for ResultPairComparison scoring."""

from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..factory import ComparisonFactory
    from ..result_pair_comparison import ResultPairComparison


def example_metric_weighting_dict(
    comparison_factory: "ComparisonFactory | None" = None,
    weight: float = 1.0,
) -> Dict[str, float]:
    """Return a mapping *metric_name* -> *weight* for the given factory.

    Parameters
    ----------
    comparison_factory
        Factory whose metric functions should be considered.  If *None*, a
        :class:`ComparisonFactory` with the default metrics is instantiated.
    weight
        Value assigned to **every** metric (default: 1.0).

    Examples
    --------
    >>> from edsl.comparisons import ResultPairComparison, example_metric_weighting_dict
    >>> rc = ResultPairComparison.example()
    >>> weights = example_metric_weighting_dict(rc.comparison_factory)
    >>> all(isinstance(w, float) for w in weights.values())
    True
    """
    from ..factory import ComparisonFactory

    if comparison_factory is None:
        comparison_factory = ComparisonFactory.with_defaults()

    return {str(fn): float(weight) for fn in comparison_factory.comparison_fns}


def example_question_weighting_dict(
    results_comparison: "ResultPairComparison",
    weight: float = 1.0,
) -> Dict[str, float]:
    """Return a mapping *question_name* -> *weight* for the given comparison.

    Examples
    --------
    >>> from edsl.comparisons import ResultPairComparison, example_question_weighting_dict
    >>> rc = ResultPairComparison.example()
    >>> qw = example_question_weighting_dict(rc)
    >>> set(qw) == set(rc.comparison.keys())
    True
    """

    return {qname: float(weight) for qname in results_comparison.comparison.keys()}


def single_metric_weighting_dict(
    comparison_factory: "ComparisonFactory",
    target_metric_name: str,
    weight: float = 1.0,
    default: float = 0.0,
) -> Dict[str, float]:
    """Return weights with *target_metric_name* set to *weight*, others to *default*.

    Raises
    ------
    ValueError
        If *target_metric_name* is not produced by *comparison_factory*.
    """

    names = [str(fn) for fn in comparison_factory.comparison_fns]
    if target_metric_name not in names:
        raise ValueError(f"Metric '{target_metric_name}' not found in factory metrics.")
    return {name: (weight if name == target_metric_name else default) for name in names}


def single_question_weighting_dict(
    results_comparison: "ResultPairComparison",
    target_question_name: str,
    weight: float = 1.0,
    default: float = 0.0,
) -> Dict[str, float]:
    """Return weights with *target_question_name* set to *weight*, others to *default*.

    Raises
    ------
    ValueError
        If *target_question_name* is not among the compared questions.
    """

    qnames = list(results_comparison.comparison.keys())
    if target_question_name not in qnames:
        raise ValueError(f"Question '{target_question_name}' not found in comparison.")
    return {q: (weight if q == target_question_name else default) for q in qnames}
