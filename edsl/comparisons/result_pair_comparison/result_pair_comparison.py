from __future__ import annotations

"""Comare the answers to the same survey, as captured by two Result objects."""

from typing import Dict, Any, List, TYPE_CHECKING, Generator, Tuple

from ...base import Base
from ...comparisons.metrics_collection import MetricsCollection

if TYPE_CHECKING:
    from ...results.results import Results  # pragma: no cover – only for type hints
    from ...scenarios import ScenarioList
    from ...results.results import Result


# Type alias to make it clear that dict keys are question names
QuestionName = str

class ResultPairComparison(Base):
    """Pair-wise comparison of two Result objects.
    
    A 'Result' in EDSL are all the responses by a single agent to a Survey, for a given scenario and model.     
    """

    def __init__(
        self,
        result_A: Result,
        result_B: Result,
        metrics_collection: MetricsCollection | None = None,
    ):
        # Set attributes before calling super().__init__()
        self.result_A = result_A
        self.result_B = result_B
        self.metrics_collection = (
            metrics_collection or MetricsCollection.with_defaults()
        )
        self._comparison = None
        
    @property
    def _common_questions(self) -> List[QuestionName]:
        """Return the names of all questions that are present in both result_A and result_B.
        
        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc._common_questions
            ['how_feeling', 'how_feeling_yesterday']
        """
        return sorted(set[str](self.result_A.get_question_names()) & set[str](self.result_B.get_question_names()))

    @property
    def comparison(self) -> Dict[QuestionName, Dict[str, Any]]:
        """Return the comparison of the two results.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc.comparison
            {'how_feeling': ..., 'how_feeling_yesterday': ...}
        """
        if self._comparison is None:
            self._comparison = dict[QuestionName, Dict[str, Any]](self._calculate_comparison())
        return self._comparison

    def _calculate_comparison(self) -> Generator[Tuple[QuestionName, Dict[str, Any]], None, None]:
        """Calculate the comparison of the two results.
        
        Returns a generator of tuples, where each tuple contains a question name and a dictionary of metrics.
        """
        for question_name in self._common_questions:
            answer_a = self.result_A.get_answer(question_name)
            answer_b = self.result_B.get_answer(question_name)
            yield question_name, self.metrics_collection.compute_metrics(answer_a, answer_b)
    
    def _get_question_info(self, question_name: QuestionName) -> Dict[str, Any]:
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

    def to_scenario_list(self) -> "ScenarioList":
        """Convert comparison results to a ScenarioList with codebook.

        Returns a ScenarioList where each row represents a question comparison
        with short column names as keys and a codebook mapping short names to
        descriptive names.

        Returns:
            ScenarioList: Collection of scenarios with comparison data and codebook

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> sl = rc.to_scenario_list()
            >>> len(sl) > 0
            True
            >>> len(sl.codebook) > 0
            True
            >>> assert len(sl) == len(rc._common_questions), "Number of scenarios should match number of common questions"
        """
        from ...scenarios import Scenario, ScenarioList

        metric_names = [str(fn) for fn in self.metrics_collection.metrics]

        # Build the data rows and codebook
        scenarios = []
        codebook = {}

        # Define column names and their descriptions
        codebook["question"] = "Question"
        codebook["question_text"] = "Question Text"
        codebook["answer_a"] = "Answer A"
        codebook["answer_b"] = "Answer B"

        for m in metric_names:
            # Short name is the metric name itself
            # Pretty name is the formatted version
            pretty = m.replace("_", " ").title()
            codebook[m] = pretty

        codebook["question_type"] = "Question Type"

        # Build rows
        for question_name, metrics in self.comparison.items():
            row = {}
            row["question"] = str(question_name)
            for k, v in self._get_question_info(question_name).items():
                row[k] = v
            row["answer_a"] = metrics.get("answer_a")
            row["answer_b"] = metrics.get("answer_b")

            # Add metric values
            for m in metric_names:
                val = metrics[m]
                if isinstance(val, (int, float)):
                    row[m] = val
                else:
                    row[m] = str(val) if val is not None else None

            scenarios.append(Scenario(row))

        return ScenarioList(scenarios, codebook=codebook)

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
        data = {
            "result_A": self.result_A.to_dict(),
            "result_B": self.result_B.to_dict(),
            "comparison": self._comparison,
            "edsl_class_name": self.__class__.__name__,
            "metrics_collection": self.metrics_collection.to_dict(add_edsl_version=add_edsl_version),
        }
        if add_edsl_version:
            from edsl import __version__
            data["edsl_version"] = __version__

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultPairComparison":
        """Deserialize from dictionary.

        """
        # Import Result to deserialize
        from ...results.results import Result

        # Remove edsl_version if present
        data_copy = {k: v for k, v in data.items() if k != "edsl_version"}

        # Deserialize results
        result_A = Result.from_dict(data_copy["result_A"])
        result_B = Result.from_dict(data_copy["result_B"])

        # Reconstruct comparison_factory
        metrics_collection = MetricsCollection.from_dict(data_copy.get("metrics_collection"))
        
        # Create instance with the deserialized data
        instance = cls(
            result_A = result_A,
            result_B = result_B,
            metrics_collection = metrics_collection,
        )
        instance._comparison = data_copy.get("comparison")
        instance._object_diffs = data_copy.get("object_diffs")
        return instance

    def code(self) -> str:
        """Return Python code to recreate this ResultPairComparison."""
        raise NotImplementedError("The code() method is not implemented for ResultPairComparison objects")

    def __hash__(self) -> int:
        """Return hash of the ResultPairComparison.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> isinstance(hash(rc), int)
            True
        """
        from ...utilities import dict_hash
        return dict_hash(self.to_dict(add_edsl_version=False))

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

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the ResultPairComparison.

        Returns:
            str: A string that can be evaluated to recreate the ResultPairComparison
        """
        return f"ResultPairComparison(result_A, result_B)"

    def _summary_repr(self) -> str:
        """Generate a Rich table representation of all answer comparisons.
        
        Displays multiple tables:
        1. Differences table (if any differences exist)
        2. Survey details table (question metadata)
        3. Metric abbreviations table
        4. Main comparison table with answers and metrics
        5. Note about excluded metrics (if any)

        Returns:
            str: A formatted Rich output with multiple tables
        """
        return self.to_scenario_list().__repr__()


if __name__ == "__main__":  # pragma: no cover
    import doctest
    doctest.testmod()
    rc = ResultPairComparison.example()
