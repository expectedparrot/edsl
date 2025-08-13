"""
Results scoring functionality.

This module provides the ResultsScorer class which handles scoring operations
for Results objects, including function-based scoring and answer key scoring.
"""

from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Results


class ResultsScorer:
    """
    Handles scoring operations for Results objects.

    This class encapsulates methods for scoring Results objects using
    functions or answer keys, providing a clean separation of scoring
    logic from the main Results class.
    """

    def __init__(self, results: "Results"):
        """
        Initialize the ResultsScorer with a Results object.

        Args:
            results: The Results object to perform scoring operations on
        """
        self.results = results

    def score(self, f: Callable) -> list:
        """Score the results using a function.

        Applies a scoring function to each Result object in the Results collection
        and returns a list of scores.

        Args:
            f: A function that takes values from a Result object and returns a score.

        Returns:
            list: A list of scores, one for each Result object.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> scorer = ResultsScorer(r)
            >>> def f(status): return 1 if status == 'Joyful' else 0
            >>> scorer.score(f)
            [1, 1, 0, 0]
        """
        return [r.score(f) for r in self.results.data]

    def score_with_answer_key(self, answer_key: dict) -> list:
        """Score the results using an answer key.

        Applies an answer key dictionary to each Result object in the Results
        collection and returns a list of scores.

        Args:
            answer_key: A dictionary that maps answer values to scores.

        Returns:
            list: A list of scores, one for each Result object.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> scorer = ResultsScorer(r)
            >>> answer_key = {'Great': 5, 'OK': 3, 'Terrible': 1}
            >>> scores = scorer.score_with_answer_key(answer_key)
            >>> isinstance(scores, list)
            True
        """
        return [r.score_with_answer_key(answer_key) for r in self.results.data]
