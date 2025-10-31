from __future__ import annotations

"""Exact match comparison metric for EDSL answers."""

from typing import List, Any
from ..metrics_abc import ComparisonFunction


class ExactMatch(ComparisonFunction):
    """Performs exact equality comparison between corresponding answer pairs.

    This is the simplest comparison function that returns True when answers
    are exactly equal using Python's == operator, and False otherwise.
    Useful for categorical questions or when precise matching is required.

    Examples:
        Basic exact matching:

        >>> exact = ExactMatch()
        >>> answers_A = ['yes', 'no', 'maybe']
        >>> answers_B = ['yes', 'no', 'perhaps']
        >>> exact.execute(answers_A, answers_B)
        [True, True, False]

        Works with any comparable types:

        >>> exact.execute([1, 2.5, None], [1, 2.5, None])
        [True, True, True]

        Case-sensitive string comparison:

        >>> exact.execute(['Hello'], ['hello'])
        [False]

        Empty lists:

        >>> exact.execute([], [])
        []
    """

    short_name = "exact_match"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[bool]:
        """Compare answers for exact equality.

        Args:
            answers_A: First list of answers
            answers_B: Second list of answers
            questions: Unused in this implementation

        Returns:
            List of boolean values where True indicates exact equality
            and False indicates difference.

        Note:
            Uses Python's == operator, so comparison behavior depends
            on the types being compared.
        """
        return [a == b for a, b in zip(answers_A, answers_B)]
