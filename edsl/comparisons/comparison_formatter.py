from __future__ import annotations

"""Formatter for comparison data from ScenarioList."""

from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList


class ComparisonFormatter:
    """Format comparison data from a ScenarioList into readable strings.

    Takes a ScenarioList produced by ResultPairComparison.to_scenario_list()
    and provides methods to format individual question comparisons.
    """

    DEFAULT_TEMPLATE = """<question_text>
{{ question_text }}
</question_text>

<correct_answer>
{{ answer_b }}
</correct_answer>

<your_answer>
{{ answer_a }}
</your_answer>

Answer metric comparisons:
{% for metric_name, metric_value in metrics.items() -%}
- {{ metric_name }}: {{ metric_value }}
{% endfor %}"""

    def __init__(self, scenario_list: "ScenarioList", template: Optional[str] = None):
        """Initialize the formatter with a ScenarioList.

        Args:
            scenario_list: ScenarioList from ResultPairComparison.to_scenario_list()
            template: Optional Jinja2 template string. If None, uses DEFAULT_TEMPLATE.
        """
        self.scenario_list = scenario_list
        self.template_string = template or self.DEFAULT_TEMPLATE

        # Build a lookup dict for quick access by question name
        self._question_lookup = {}
        for scenario in scenario_list:
            question_name = scenario["question"]
            self._question_lookup[question_name] = scenario

    def format_question(self, question_name: str) -> str:
        """Format a specific question's comparison data.

        Args:
            question_name: Name of the question to format

        Returns:
            Formatted string showing question text, answers, and metric comparisons

        Raises:
            KeyError: If question_name is not found in the scenario list

        Examples:
            >>> from edsl.comparisons import ResultPairComparison, ComparisonFormatter
            >>> rc = ResultPairComparison.example()
            >>> sl = rc.to_scenario_list()
            >>> formatter = ComparisonFormatter(sl)
            >>> # Get first question name
            >>> first_question = sl[0]["question"]
            >>> output = formatter.format_question(first_question)
            >>> "<question_text>" in output
            True
            >>> "<correct_answer>" in output
            True
        """
        from jinja2 import Template

        if question_name not in self._question_lookup:
            available = list(self._question_lookup.keys())
            raise KeyError(
                f"Question '{question_name}' not found. Available: {available}"
            )

        scenario = self._question_lookup[question_name]

        # Extract the data for template
        question_text = scenario.get("question_text", "")
        answer_a = scenario.get("answer_a", "")
        answer_b = scenario.get("answer_b", "")

        # Get all metric values (exclude the standard fields)
        standard_fields = {
            "question",
            "question_text",
            "answer_a",
            "answer_b",
            "question_type",
        }
        metrics = {}

        # Use codebook to get pretty names if available
        codebook = (
            self.scenario_list.codebook
            if hasattr(self.scenario_list, "codebook")
            else {}
        )

        for key, value in scenario.items():
            if key not in standard_fields:
                # Use codebook for pretty name, or format the key
                pretty_name = codebook.get(key, key.replace("_", " ").title())
                metrics[pretty_name] = value

        # Render template
        template = Template(self.template_string)
        return template.render(
            question_text=question_text,
            answer_a=answer_a,
            answer_b=answer_b,
            metrics=metrics,
        )

    def format_all_questions(self) -> List[str]:
        """Format all questions in the scenario list.

        Returns:
            List of formatted strings, one per question
        """
        return [self.format_question(q) for q in self._question_lookup.keys()]

    @classmethod
    def example(cls) -> "ComparisonFormatter":
        """Create an example ComparisonFormatter using ResultPairComparison.example().

        Examples:
            >>> from edsl.comparisons import ComparisonFormatter
            >>> formatter = ComparisonFormatter.example()
            >>> isinstance(formatter, ComparisonFormatter)
            True
        """
        from .result_pair_comparison import ResultPairComparison

        rc = ResultPairComparison.example()
        sl = rc.to_scenario_list()
        return cls(sl)


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
