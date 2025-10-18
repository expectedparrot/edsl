from __future__ import annotations

"""Container that bundles answers and metric values for a single question."""

from typing import Any, Dict
from collections.abc import Iterable

__all__ = ["AnswerComparison"]


class AnswerComparison:
    """Container for a single question's answer pair and all comparison metrics.

    This class stores two answers and all computed comparison metrics for a single
    question, providing flexible access to both the raw answers and computed scores.
    It's designed to be metric-agnostic, accepting arbitrary comparison results
    as keyword arguments.

    The class also provides utility methods for display formatting and data export.

    Attributes:
        answer_a: The first answer being compared
        answer_b: The second answer being compared
        _truncate_len: Class-level setting for display truncation (60 characters)

    Examples:
        Basic usage with metrics:

        >>> comparison = AnswerComparison(
        ...     answer_a="yes",
        ...     answer_b="no",
        ...     exact_match=False,
        ...     similarity=0.2,
        ...     question_type="yes_no"
        ... )
        >>> comparison.answer_a
        'yes'
        >>> comparison.exact_match
        False
        >>> comparison.similarity
        0.2

        Attribute access for question metadata:

        >>> comparison.question_type
        'yes_no'

        Dictionary conversion:

        >>> data = comparison.to_dict()
        >>> data['answer_a']
        'yes'
        >>> data['exact_match']
        False

        Display truncation:

        >>> long_answer = "This is a very long answer that will be truncated for display purposes"
        >>> AnswerComparison._truncate(long_answer, 20)
        'This is...purposes'
    """

    _truncate_len: int = 60  # characters for display

    def __init__(self, answer_a: Any, answer_b: Any, **metrics: Any):
        """Initialize with answer pair and arbitrary metrics.

        Args:
            answer_a: First answer in the comparison
            answer_b: Second answer in the comparison
            **metrics: Arbitrary keyword arguments for comparison metrics
                      and question metadata (e.g., exact_match=True,
                      question_type='multiple_choice')
        """
        self.answer_a = answer_a
        self.answer_b = answer_b
        # Store metrics in a private dict to avoid namespace clashes
        self._metrics: Dict[str, Any] = metrics

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: Any, max_len: int) -> str:
        if not isinstance(text, str):
            if isinstance(text, Iterable):
                text = ", ".join(map(str, text))
            else:
                text = str(text)
        if len(text) <= max_len:
            return text
        half = (max_len - 3) // 2
        return text[:half] + "..." + text[-half:]

    # ------------------------------------------------------------------
    # Dict/attr-like access to metrics
    # ------------------------------------------------------------------

    def __getattr__(self, item: str):
        if item in self._metrics:
            return self._metrics[item]
        raise AttributeError(item)

    def __getitem__(self, item: str):
        return self._metrics.get(item)

    def to_dict(self) -> Dict[str, Any]:
        """Return all comparison data as a dictionary.

        Returns:
            Dictionary containing answer_a, answer_b, and all metrics

        Examples:
            >>> comp = AnswerComparison("yes", "no", exact_match=False)
            >>> data = comp.to_dict()
            >>> sorted(data.keys())
            ['answer_a', 'answer_b', 'exact_match']
        """
        result = {
            "answer_a": self.answer_a,
            "answer_b": self.answer_b,
        }
        result.update(self._metrics)
        return result

    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        a = self._truncate(self.answer_a, self._truncate_len)
        b = self._truncate(self.answer_b, self._truncate_len)
        metric_parts = []
        for k, v in self._metrics.items():
            metric_parts.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
        return f"AnswerComparison(answer_a='{a}', answer_b='{b}', {', '.join(metric_parts)})"
