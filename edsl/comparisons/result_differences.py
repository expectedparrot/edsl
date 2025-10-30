from __future__ import annotations

"""Container for result pair comparison differences."""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .result_pair_comparison import ResultPairComparison

from ..prompts import Prompt

base_template = Prompt(
    text="""
<question>
{{ question_text }}
</question>

<question_type>
{{ question_type }}
</question_type>

The question options were 
<question_options>
{{ question_options }}"
</question_options>

<actual_answer>
{{ actual_answer }}
</actual_answer>

<candidate_answer>
{{ candidate_answer }}
</candidate_answer>
"""
)


class ResultDifferences:
    """Report on differences between two results."""

    def __init__(
        self,
        result_pair_comparison: "ResultPairComparison",
        template: Optional[str] = None,
        exclude_exact_match: bool = True,
        separator="\n\n--------------------------------\n",
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
            template = Prompt(text=template)
        self.template = template
        self.exclude_exact_match = exclude_exact_match
        self.separator = separator

    @classmethod
    def example(cls) -> ResultDifferences:
        """Return an example ResultDifferences."""
        from .result_pair_comparison import ResultPairComparison

        return cls(ResultPairComparison.example())

    def generate_report(self) -> str:
        """Generate a report on the differences between the two results."""
        report = Prompt("")
        for (
            question_name,
            comparison_data,
        ) in self.result_pair_comparison.comparisons.items():
            d = {}
            d["question_text"] = comparison_data["question_info"]["question_text"]
            d["question_type"] = comparison_data["question_info"]["question_type"]
            d["question_options"] = comparison_data["question_info"]["question_options"]
            d["actual_answer"] = comparison_data["answer_b"]
            d["candidate_answer"] = comparison_data["answer_a"]
            for key, value in self.result_pair_comparison.scenario_A.items():
                d[key] = value
            report += self.template.render(primary_replacement=d) + self.separator
        return report


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
