from __future__ import annotations

"""Comare the answers to the same survey, as captured by two Result objects."""

from collections import UserDict
from typing import Dict, Any, List, TYPE_CHECKING, Generator, Tuple

from ..metrics.metrics_collection import MetricsCollection

if TYPE_CHECKING:
    from ...results.results import Results  # pragma: no cover – only for type hints
    from ...scenarios import ScenarioList
    from ...results.results import Result


# Type alias to make it clear that dict keys are question names
QuestionName = str

class ResultPairComparison(UserDict):
    """Pair-wise comparison of two Result objects.    
    """

    def __init__(
        self,
        result_A: Result,
        result_B: Result,
        metrics_collection: MetricsCollection | None = None,
    ):
        self.result_A = result_A
        self.result_B = result_B
        self.metrics_collection = (
            metrics_collection or MetricsCollection.with_defaults()
        )
        # Compute comparison data immediately and initialize UserDict with it
        comparison_data = dict[QuestionName, Dict[str, Any]](self._calculate_comparison())
        UserDict.__init__(self, comparison_data)
        
    @property
    def _common_questions(self) -> List[QuestionName]:
        """Return the names of all questions that are present in both result_A and result_B.
        
        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc._common_questions
            ['how_feeling', 'how_feeling_yesterday']
        """
        return sorted(set[str](self.result_A.get_question_names()) & set[str](self.result_B.get_question_names()))

    def _calculate_comparison(self) -> Generator[Tuple[QuestionName, Dict[str, Any]], None, None]:
        """Calculate the comparison of the two results.
        
        Returns a generator of tuples, where each tuple contains a question name and a dictionary of metrics.
        """
        for question_name in self._common_questions:
            answer_a = self.result_A.get_answer(question_name)
            answer_b = self.result_B.get_answer(question_name)
            yield question_name, self.metrics_collection.compute_metrics(answer_a, answer_b)
    
    def _get_question_info(self, question_name: QuestionName) -> Dict[str, str]:
        """Return the information about a question.
        
        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc._get_question_info('how_feeling')
            {'question_text': 'How are you this {{ period }}?', 'question_type': 'multiple_choice', 'question_options': ['Good', 'Great', 'OK', 'Terrible']}
        """
        return {
            "question_text": self.result_A.get_question_text(question_name),
            "question_type": self.result_A.get_question_type(question_name),
            "question_options": self.result_A.get_question_options(question_name),
        }

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize to dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version

        Returns:
            Dictionary representation

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> d = rc.to_dict()
            >>> 'result_A' in d
            True
            >>> 'result_B' in d
            True
        """
        result = {
            "result_A": self.result_A.to_dict(),
            "result_B": self.result_B.to_dict(),
            "data": dict(self.data),
            "edsl_class_name": self.__class__.__name__,
            "metrics_collection": self.metrics_collection.to_dict(add_edsl_version=add_edsl_version),
        }
        if add_edsl_version:
            from edsl import __version__
            result["edsl_version"] = __version__

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultPairComparison":
        """Deserialize from dictionary.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> d = rc.to_dict(add_edsl_version=False)
            >>> rc2 = ResultPairComparison.from_dict(d)
            >>> len(rc2) == len(rc)
            True
            >>> list(rc2.keys()) == list(rc.keys())
            True
            >>> rc2['how_feeling']['exact_match'] == rc['how_feeling']['exact_match']
            True
        """
        # Import Result to deserialize
        from ...results.results import Result

        # Remove edsl_version if present
        data_copy = {k: v for k, v in data.items() if k != "edsl_version"}

        # Deserialize results
        result_A = Result.from_dict(data_copy["result_A"])
        result_B = Result.from_dict(data_copy["result_B"])

        # Reconstruct metrics collection
        metrics_collection = MetricsCollection.from_dict(data_copy.get("metrics_collection"))
        
        # Create instance (this will compute comparison data)
        instance = cls(
            result_A = result_A,
            result_B = result_B,
            metrics_collection = metrics_collection,
        )
        return instance

    @classmethod
    def example(
        cls, metrics_collection: MetricsCollection | None = None,
        first_index: int = 0,
        second_index: int = 1,
    ) -> "ResultPairComparison":
        """Return a *ResultPairComparison* instance based on `edsl.Results.example()`.

        The helper uses two example *Result* entries and a
        default metric set (including cosine similarity).
        """

        # Use provided factory or default to full ComparisonFactory with COSINE metrics
        if metrics_collection is None:
            metrics_collection = MetricsCollection.with_defaults()

        from ...results import Results

        # Rely on edsl built-in example results ----------------------------
        example_results: "Results" = Results.example()

        return cls(
            example_results[first_index],
            example_results[second_index],
            metrics_collection = metrics_collection,
        )


if __name__ == "__main__":  # pragma: no cover
    import doctest
    doctest.testmod()
    rc = ResultPairComparison.example()
