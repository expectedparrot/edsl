from __future__ import annotations

"""Jaccard similarity comparison metric for EDSL answers."""

from typing import List, Optional, Any
from ..metrics_abc import ComparisonFunction


class JaccardSimilarity(ComparisonFunction):
    """Computes Jaccard similarity between two lists of iterable answers.

    Jaccard similarity is defined as the size of the intersection divided by
    the size of the union of two sets. This provides a measure of how similar
    two sets are, ranging from 0.0 (completely different) to 1.0 (identical).

    Unlike the Overlap metric which divides by the minimum set size, Jaccard
    divides by the union size, providing a more balanced measure of similarity
    that accounts for both overlapping and non-overlapping elements.

    The score ranges from 0.0 (no overlap) to 1.0 (identical sets).
    Returns None for non-iterable answers.

    Examples:
        Basic list Jaccard similarity:

        >>> jaccard = JaccardSimilarity()
        >>> answers_A = [['a', 'b', 'c'], ['x', 'y']]
        >>> answers_B = [['b', 'c', 'd'], ['y', 'z']]
        >>> jaccard.execute(answers_A, answers_B)
        [0.5, 0.3333333333333333]

        String answers return None (not treated as iterables):

        >>> jaccard.execute(['hello'], ['world'])
        [None]

        Empty collections return 0.0:

        >>> jaccard.execute([[]], [['a']])
        [0.0]

        Identical sets:

        >>> jaccard.execute([['a', 'b']], [['a', 'b']])
        [1.0]

        No overlap:

        >>> jaccard.execute([['a', 'b']], [['c', 'd']])
        [0.0]

        Multi-select question example (subset vs superset):

        >>> correct = [['Learning']]
        >>> answer = [['Task Iteration', 'Learning', 'Validation', 'Feedback']]
        >>> jaccard.execute(correct, answer)
        [0.25]
    """

    short_name = "jaccard_similarity"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        """Compute Jaccard similarity between two answer lists.

        Args:
            answers_A: First list of answers (should be iterables)
            answers_B: Second list of answers (should be iterables)
            questions: Unused in this implementation

        Returns:
            List of Jaccard similarity scores where each score is:
            - Float between 0.0-1.0: |intersection| / |union|
            - 0.0: When one or both collections are empty
            - None: When either answer is not an iterable (or is string/bytes)

        Note:
            Strings and bytes are explicitly not treated as iterables to avoid
            character-level comparison which is usually not desired.
        """

        from collections.abc import Iterable

        def is_sequence(obj: Any) -> bool:
            return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))

        jaccard_scores: List[Optional[float]] = []
        for a, b in zip(answers_A, answers_B):
            if not (is_sequence(a) and is_sequence(b)):
                jaccard_scores.append(None)
                continue

            set_a, set_b = set(a), set(b)

            # Handle empty sets
            if len(set_a) == 0 and len(set_b) == 0:
                jaccard_scores.append(1.0)  # Two empty sets are identical
                continue

            if len(set_a) == 0 or len(set_b) == 0:
                jaccard_scores.append(0.0)
                continue

            intersection_size = len(set_a & set_b)
            union_size = len(set_a | set_b)
            jaccard_scores.append(intersection_size / union_size)

        return jaccard_scores
