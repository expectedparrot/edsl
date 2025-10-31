from __future__ import annotations

"""Comare the answers to the same survey, as captured by two Result objects."""

from typing import Dict, Any, List, TYPE_CHECKING, Generator, Tuple, Iterator

from ..metrics.metrics_collection import MetricsCollection

if TYPE_CHECKING:
    from ...results.results import Results  # pragma: no cover – only for type hints
    from ...results.results import Result


# Type alias to make it clear that dict keys are question names
QuestionName = str


class ResultPairComparison:
    """Pair-wise comparison of two Result objects.

    Access comparison data via the `comparisons` attribute, which is a dictionary
    mapping question names to their comparison metrics.

    Examples:
        >>> rc = ResultPairComparison.example()
        >>> 'how_feeling' in rc.comparisons
        True
        >>> 'metrics' in rc.comparisons['how_feeling']
        True
        >>> 'question_info' in rc.comparisons['how_feeling']
        True
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
        # Compute comparison data immediately
        self.comparisons = dict[QuestionName, Dict[str, Any]](
            self._calculate_comparison()
        )

    @property
    def _common_questions(self) -> List[QuestionName]:
        """Return the names of all questions that are present in both result_A and result_B.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc._common_questions
            ['how_feeling', 'how_feeling_yesterday']
        """
        return sorted(
            set[str](self.result_A.get_question_names())
            & set[str](self.result_B.get_question_names())
        )

    @property
    def scenario_A(self):
        """Return the scenario data from result_A.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc.scenario_A is not None
            True
        """
        return self.result_A.scenario

    @property
    def scenario_B(self):
        """Return the scenario data from result_B.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> rc.scenario_B is not None
            True
        """
        return self.result_B.scenario

    def _calculate_comparison(
        self,
    ) -> Generator[Tuple[QuestionName, Dict[str, Any]], None, None]:
        """Calculate the comparison of the two results.

        Returns a generator of tuples, where each tuple contains a question name and a dictionary of metrics.
        """
        for question_name in self._common_questions:
            answer_a = self.result_A.get_answer(question_name)
            answer_b = self.result_B.get_answer(question_name)
            yield question_name, {
                "metrics": self.metrics_collection.compute_metrics(answer_a, answer_b),
                "question_info": self._get_question_info(question_name),
                "answer_a": answer_a,
                "answer_b": answer_b,
            }

    def _get_question_info(self, question_name: QuestionName) -> Dict[str, str]:
        """Return the information about a question.

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> info = rc._get_question_info('how_feeling')
            >>> info['question_type']
            'multiple_choice'
            >>> 'How are you' in info['question_text']
            True
        """
        from ...prompts.prompt import Prompt

        try:
            d = self.result_A.scenario_dict
            answers_dict = {
                k: {"answer": v} for k, v in self.result_A.sub_dicts["answers"].items()
            }
            combined_dict = {**d, **answers_dict}
            question_text = (
                Prompt(self.result_A.get_question_text(question_name))
                .render(primary_replacement=combined_dict)
                .text
            )
        except Exception as e:
            question_text = "Unknown"
            import warnings

            warnings.warn(f"Error getting question text: {e}")
            question_text = "Error getting question text: " + str(e)
            warnings.warn(
                f"Raw question text: {self.result_A.get_question_text(question_name)}"
            )
            warnings.warn(f"Primary replacement: {self.result_A.scenario}")
        return {
            "question_text": question_text,
            "question_type": self.result_A.get_question_type(question_name),
            "question_options": self.result_A.get_question_options(question_name),
        }

    def __repr__(self) -> str:
        """Generate a summary representation of the ResultPairComparison with Rich formatting.

        Displays all questions and their complete comparison data without truncation.
        Order: question_info, answer_a, answer_b, metrics.
        """
        from rich.console import Console
        from rich.text import Text
        import io
        import shutil

        # Get terminal width
        terminal_width = shutil.get_terminal_size().columns

        # Build the Rich text
        output = Text()
        output.append("ResultPairComparison(\n", style="bold cyan")
        output.append(f"    num_questions={len(self.comparisons)},\n")
        output.append("    comparisons={\n")

        # Show all questions (no truncation)
        for i, (question_name, comparison_data) in enumerate(self.comparisons.items()):
            # Show question name
            output.append("        ")
            output.append(f"'{question_name}'", style="bold yellow")
            output.append(": {\n")

            # Show question_info section first (no truncation)
            if "question_info" in comparison_data:
                question_info = comparison_data["question_info"]
                output.append("            ")
                output.append("'question_info'", style="bold magenta")
                output.append(": {\n")

                for key, value in question_info.items():
                    output.append("                ")
                    output.append(f"'{key}'", style="bold green")
                    output.append(f": {repr(value)},\n")

                output.append("            },\n")

            # Show answer_a (no truncation)
            if "answer_a" in comparison_data:
                answer_a = comparison_data["answer_a"]
                output.append("            ")
                output.append("'answer_a'", style="bold magenta")
                output.append(f": {repr(answer_a)},\n")

            # Show answer_b (no truncation)
            if "answer_b" in comparison_data:
                answer_b = comparison_data["answer_b"]
                output.append("            ")
                output.append("'answer_b'", style="bold magenta")
                output.append(f": {repr(answer_b)},\n")

            # Show metrics section last (no truncation)
            if "metrics" in comparison_data:
                metrics_dict = comparison_data["metrics"]

                output.append("            ")
                output.append("'metrics'", style="bold magenta")
                output.append(": {\n")

                for metric_name, metric_value in metrics_dict.items():
                    output.append("                ")
                    output.append(f"'{metric_name}'", style="bold green")
                    output.append(f": {repr(metric_value)},\n")

                output.append("            }\n")

            output.append("        }")

            # Add comma and newline unless it's the last one
            if i < len(self.comparisons) - 1:
                output.append(",\n")
            else:
                output.append("\n")

        output.append("    }\n")
        output.append(")", style="bold cyan")

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
        console.print(output, end="")
        return console.file.getvalue()

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
            "comparisons": self.comparisons,
            "edsl_class_name": self.__class__.__name__,
            "metrics_collection": self.metrics_collection.to_dict(
                add_edsl_version=add_edsl_version
            ),
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
            >>> len(rc2.comparisons) == len(rc.comparisons)
            True
            >>> list(rc2.comparisons.keys()) == list(rc.comparisons.keys())
            True
            >>> rc2.comparisons['how_feeling']['metrics']['exact_match'] == rc.comparisons['how_feeling']['metrics']['exact_match']
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
        metrics_collection = MetricsCollection.from_dict(
            data_copy.get("metrics_collection")
        )

        # Create instance (this will compute comparison data)
        instance = cls(
            result_A=result_A,
            result_B=result_B,
            metrics_collection=metrics_collection,
        )

        # If we have pre-computed comparison data, use it (for backward compatibility with old serialization)
        # Handles old formats: "data", "comparison_data", or new format: "comparisons"
        if "comparisons" in data_copy:
            instance.comparisons = data_copy["comparisons"]
        elif "comparison_data" in data_copy:
            instance.comparisons = data_copy["comparison_data"]
        elif "data" in data_copy:
            instance.comparisons = data_copy["data"]

        return instance

    def to_scenario_list(self) -> "ScenarioList":
        """Convert comparison data to a ScenarioList with one scenario per question-metric pair.

        Creates a "long" format where each scenario contains:
        - question_name: The name of the question being compared
        - answer_a: The answer from result_A
        - answer_b: The answer from result_B
        - metric_name: The name of the metric
        - metric_value: The value of the metric

        Returns:
            ScenarioList with one scenario per question-metric combination

        Examples:
            >>> rc = ResultPairComparison.example()
            >>> sl = rc.to_scenario_list()
            >>> len(sl) > 0
            True
            >>> 'question_name' in sl[0]
            True
            >>> 'metric_name' in sl[0]
            True
            >>> 'metric_value' in sl[0]
            True
        """
        from ...scenarios.scenario import Scenario
        from ...scenarios.scenario_list import ScenarioList

        scenarios = []
        for question_name, comparison_data in self.comparisons.items():
            answer_a = comparison_data["answer_a"]
            answer_b = comparison_data["answer_b"]
            metrics = comparison_data["metrics"]

            for metric_name, metric_value in metrics.items():
                scenario_dict = {
                    "question_name": question_name,
                    "answer_a": answer_a,
                    "answer_b": answer_b,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                }
                scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)

    @classmethod
    def example(
        cls,
        metrics_collection: MetricsCollection | None = None,
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
            metrics_collection=metrics_collection,
        )


if __name__ == "__main__":  # pragma: no cover
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
    rc = ResultPairComparison.example()
