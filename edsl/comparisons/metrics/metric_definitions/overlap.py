from __future__ import annotations

"""Overlap comparison metric for EDSL answers."""

from typing import List, Optional, Any
from ..metrics_abc import ComparisonFunction


class Overlap(ComparisonFunction):
    """Computes normalized overlap between two lists of iterable answers.

    This comparison function treats answers as collections and computes the overlap
    as the size of the intersection divided by the minimum collection size.
    String and bytes objects are not treated as iterables to avoid character-level
    comparison.

    The overlap score ranges from 0.0 (no overlap) to 1.0 (complete overlap of
    the smaller set). Returns None for non-iterable answers.

    Examples:
        Basic list overlap:

        >>> overlap = Overlap()
        >>> answers_A = [['a', 'b', 'c'], ['x', 'y']]
        >>> answers_B = [['b', 'c', 'd'], ['y', 'z']]
        >>> overlap.execute(answers_A, answers_B)
        [0.6666666666666666, 0.5]

        String answers return None (not treated as iterables):

        >>> overlap.execute(['hello'], ['world'])
        [None]

        Empty collections return 0.0:

        >>> overlap.execute([[]], [['a']])
        [0.0]

        Complete overlap:

        >>> overlap.execute([['a', 'b']], [['a', 'b']])
        [1.0]

        No overlap:

        >>> overlap.execute([['a', 'b']], [['c', 'd']])
        [0.0]
    """

    short_name = "overlap"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        """Compute normalized overlap between two answer lists.

        Args:
            answers_A: First list of answers (should be iterables)
            answers_B: Second list of answers (should be iterables)
            questions: Unused in this implementation

        Returns:
            List of overlap scores where each score is:
            - Float between 0.0-1.0: |intersection| / min(len(a), len(b))
            - 0.0: When one collection is empty
            - None: When either answer is not an iterable (or is string/bytes)

        Note:
            Strings and bytes are explicitly not treated as iterables to avoid
            character-level comparison which is usually not desired.
        """

        from collections.abc import Iterable

        def is_sequence(obj: Any) -> bool:
            return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))

        overlap_frac: List[Optional[float]] = []
        for a, b in zip(answers_A, answers_B):
            if not (is_sequence(a) and is_sequence(b)):
                overlap_frac.append(None)
                continue

            set_a, set_b = set(a), set(b)

            if len(set_a) == 0 or len(set_b) == 0:
                overlap_frac.append(0.0)
                continue

            intersection_size = len(set_a & set_b)
            overlap_frac.append(intersection_size / min(len(set_a), len(set_b)))

        return overlap_frac
