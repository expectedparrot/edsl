from __future__ import annotations

"""Container for result pair comparison differences."""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .result_pair_comparison import ResultPairComparison
    from .answer_comparison import AnswerComparison

from ..prompts import Prompt

base_template = Prompt(text = """
An AI agent was asked the question "{{ question_text }}"
The question type was "{{ question_type }}".
The question options were "{{ question_options }}"

The true answer from the human was: {{ actual_answer }}
The AI agent's answer was: "{{ candidate_answer }}"
""")

class ResultDifferences:
    """Report on differences between two results.
    """

    def __init__(
        self,
        result_pair_comparison: "ResultPairComparison",
        template: Optional[str] = None,
        exclude_exact_match: bool = True,
    ):
        """Initialize ResultDifferences container.

        Args:
            differences: List of formatted difference strings for each question
            question_names: List of question names corresponding to differences
            result_comparison: The ResultPairComparison object that created these differences
            template: Optional Jinja2 template string used for formatting
        """
        self.result_pair_comparison = result_pair_comparison
        if template is None:
            template = base_template
        elif isinstance(template, str):
            template = Prompt(text = template)
        self.template = template
        self.exclude_exact_match = exclude_exact_match

    @classmethod
    def example(cls) -> ResultDifferences:
        """Return an example ResultDifferences."""
        from .result_pair_comparison import ResultPairComparison
        return cls(ResultPairComparison.example())

    def generate_report(self) -> str:
        """Generate a report on the differences between the two results."""
        report = Prompt("")
        for scenario in self.result_pair_comparison.to_scenario_list():
            d = {}
            d['question_text'] = scenario.question_text
            d['question_type'] = scenario.question_type
            d['question_options'] = scenario.question_options
            d['actual_answer'] = scenario.answer_b
            d['candidate_answer'] = scenario.answer_a
            for key, value in self.result_pair_comparison.scenario_A.items():
                d[key] = value
            report += self.template.render(primary_replacement=d)
        return report  



if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
