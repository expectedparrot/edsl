from __future__ import annotations

"""Squared distance comparison metric for EDSL answers."""

from typing import List, Optional, Any
from ..metrics_abc import ComparisonFunction


class SquaredDistance(ComparisonFunction):
    """*Negative* squared distance

    Returns ``-((a - b) ** 2)`` for numerical questions so that **higher values
    indicate better similarity**, aligning with other metrics such as cosine
    similarity or exact match. Non-numerical questions yield ``None``.
    """

    short_name = "negative_squared_distance"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        if questions is None:
            questions = [None] * len(answers_A)

        scores: List[Optional[float]] = []
        for a, b, q in zip(answers_A, answers_B, questions):
            if not (isinstance(q, dict) and q.get("question_type") == "numerical"):
                scores.append(None)
                continue
            try:
                diff_sq = (float(a) - float(b)) ** 2
                scores.append(-diff_sq)  # negative to make larger better
            except (ValueError, TypeError):
                scores.append(None)
        return scores
