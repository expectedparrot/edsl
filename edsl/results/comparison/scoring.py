"""Weighted scoring for ResultPairComparison comparisons dicts."""

from __future__ import annotations

from typing import Dict, Optional


def weighted_score(
    comparisons: dict,
    metric_weights: Optional[Dict[str, float]] = None,
    question_weights: Optional[Dict[str, float]] = None,
) -> float:
    """Compute a weighted score from a comparisons dict. Returns float in [0, 1].

    ``comparisons`` is the ``.comparisons`` attribute of a
    :class:`ResultPairComparison`.  Each value must have a ``"metrics"`` key.

    If *metric_weights* is ``None``, all metrics are weighted equally.
    If *question_weights* is ``None``, all questions are weighted equally.
    Weights are normalised internally so they don't need to sum to 1.

    >>> from edsl.results.comparison.comparison import ResultPairComparison
    >>> rpc = ResultPairComparison.example()
    >>> 0 <= weighted_score(rpc.comparisons) <= 1
    True
    """
    questions = list(comparisons.keys())

    # Collect metric names from the first question
    first_metrics = comparisons[questions[0]]["metrics"]
    metric_names = list(first_metrics.keys())

    # Default weights
    if metric_weights is None:
        metric_weights = {m: 1.0 for m in metric_names}
    if question_weights is None:
        question_weights = {q: 1.0 for q in questions}

    # Normalise metric weights
    total_mw = sum(metric_weights.values())
    if total_mw == 0:
        raise ValueError("Sum of metric_weights cannot be zero")
    norm_mw = {m: w / total_mw for m, w in metric_weights.items()}

    score = 0.0
    for metric_name, mweight in norm_mw.items():
        metric_sum = 0.0
        weight_sum = 0.0
        for qname in questions:
            value = comparisons[qname]["metrics"].get(metric_name)
            if value is None:
                continue
            qw = question_weights.get(qname, 1.0)
            if isinstance(value, bool):
                value = 1.0 if value else 0.0
            metric_sum += value * qw
            weight_sum += qw
        if weight_sum > 0:
            score += (metric_sum / weight_sum) * mweight

    return score


if __name__ == "__main__":
    import doctest

    doctest.testmod()
