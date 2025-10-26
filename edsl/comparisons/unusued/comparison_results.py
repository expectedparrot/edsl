from __future__ import annotations

"""Rich container for comparison results with analysis and rendering capabilities."""

from typing import Dict, List, Any, Optional
from .answer_comparison import AnswerComparison

# Optional import for rich functionality
try:
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

__all__ = ["ComparisonResults"]


class ComparisonResults:
    """Rich container for comparison results with analysis and rendering capabilities.

    This class wraps a collection of AnswerComparison objects (one per question)
    and provides high-level methods for analysis, data extraction, and visualization.
    It maintains references to the comparison functions used and offers convenient
    access to question metadata and comparison metrics.

    Attributes:
        comparisons: Dictionary mapping question names to AnswerComparison objects
        comparison_fns: List of ComparisonFunction objects used to generate results

    Examples:
        Basic usage (requires actual AnswerComparison objects):

        >>> # Create mock comparisons for testing
        >>> from collections import OrderedDict
        >>> from .metrics import ExactMatch
        >>> from .factory import ComparisonFactory
        >>> comparisons = OrderedDict([
        ...     ('q1', AnswerComparison('yes', 'no', exact_match=False, question_type='yes_no')),
        ...     ('q2', AnswerComparison('maybe', 'perhaps', exact_match=False, question_type='free_text'))
        ... ])
        >>> factory = ComparisonFactory().add_comparison(ExactMatch())
        >>> results = ComparisonResults(comparisons, factory.comparison_fns)

        Dictionary-like access:

        >>> results['q1'].answer_a
        'yes'
        >>> results['q1'].exact_match
        False

        Iteration:

        >>> list(results.keys())
        ['q1', 'q2']
        >>> len(list(results.items()))
        2

        Question metadata access:

        >>> types = results.question_types()
        >>> types['q1']
        'yes_no'
        >>> types['q2']
        'free_text'

        Grouping by question type:

        >>> by_type = results.questions_by_type
        >>> by_type['yes_no']
        ['q1']
        >>> by_type['free_text']
        ['q2']
    """

    def __init__(
        self, comparisons: Dict[str, AnswerComparison], comparison_fns: List[Any]
    ):
        """Initialize with comparison results and function metadata.

        Args:
            comparisons: Dictionary mapping question names to AnswerComparison objects
            comparison_fns: List of ComparisonFunction objects used to generate the results
        """
        self.comparisons = comparisons
        self.comparison_fns = comparison_fns

    def __getitem__(self, key: str) -> AnswerComparison:
        """Get AnswerComparison by question name.

        Args:
            key: Question name

        Returns:
            AnswerComparison object for the specified question
        """
        return self.comparisons[key]

    def __iter__(self):
        """Iterate over question names."""
        return iter(self.comparisons)

    def items(self):
        """Return (question_name, AnswerComparison) pairs."""
        return self.comparisons.items()

    def keys(self):
        """Return question names."""
        return self.comparisons.keys()

    def values(self):
        """Return AnswerComparison objects."""
        return self.comparisons.values()

    def question_types(self) -> Dict[str, Optional[str]]:
        """Get question types for all questions.

        Returns:
            Dict mapping question names to their question types
        """
        return {
            qname: getattr(comparison, "question_type", None)
            for qname, comparison in self.comparisons.items()
        }

    def question_texts(self) -> Dict[str, Optional[str]]:
        """Get question texts for all questions.

        Returns:
            Dict mapping question names to their question texts
        """
        return {
            qname: getattr(comparison, "question_text", None)
            for qname, comparison in self.comparisons.items()
        }

    def question_options(self) -> Dict[str, Optional[List]]:
        """Get question options for all questions.

        Returns:
            Dict mapping question names to their question options (if any)
        """
        return {
            qname: getattr(comparison, "question_options", None)
            for qname, comparison in self.comparisons.items()
        }

    def get_question_attribute(self, attribute: str) -> Dict[str, Any]:
        """Get a specific question attribute for all questions.

        Args:
            attribute: The attribute name to retrieve (e.g., 'question_type', 'question_text', 'question_options')

        Returns:
            Dict mapping question names to the requested attribute values
        """
        return {
            qname: getattr(comparison, attribute, None)
            for qname, comparison in self.comparisons.items()
        }

    @property
    def all_question_types(self) -> List[str]:
        """Get a list of all unique question types in the results."""
        types = set()
        for comparison in self.comparisons.values():
            qtype = getattr(comparison, "question_type", None)
            if qtype:
                types.add(qtype)
        return sorted(list(types))

    @property
    def questions_by_type(self) -> Dict[str, List[str]]:
        """Group question names by their question type."""
        by_type = {}
        for qname, comparison in self.comparisons.items():
            qtype = getattr(comparison, "question_type", "unknown")
            if qtype not in by_type:
                by_type[qtype] = []
            by_type[qtype].append(qname)
        return by_type

    def to_scenario_list(self):
        """Convert the comparison results to a ScenarioList."""
        from edsl import ScenarioList, Scenario

        scenarios = []
        for q, answer_comparison in self.comparisons.items():
            combined_dict = {"question_name": q}
            combined_dict.update(answer_comparison.to_dict())
            scenarios.append(Scenario(combined_dict))
        return ScenarioList(scenarios)

    def render_table(self):
        """Create a rich Table for the comparison results."""
        if not RICH_AVAILABLE:
            raise ImportError(
                "rich is required for table rendering. Install with: pip install rich"
            )

        table = Table(title="Answer Comparison", show_lines=True)
        table.add_column("Question", style="bold")

        metrics_to_show: List[str] = [str(fn) for fn in self.comparison_fns]

        for short in metrics_to_show:
            table.add_column(short.replace("_", " ").title(), justify="right")

        table.add_column("Answer A", overflow="fold")
        table.add_column("Answer B", overflow="fold")

        for q, metrics in self.comparisons.items():
            # First column: question name plus (question_type) if available
            q_cell = str(q)
            qtype = getattr(metrics, "question_type", None)
            if qtype:
                q_cell = f"{q}\n({qtype})"

            row: List[str] = [q_cell]
            for short in metrics_to_show:
                val = getattr(metrics, short, None)
                if isinstance(val, (int, float)):
                    row.append(f"{val:.3f}")
                else:
                    row.append(str(val))

            row.extend(
                [
                    AnswerComparison._truncate(metrics.answer_a, 100),
                    AnswerComparison._truncate(metrics.answer_b, 100),
                ]
            )

            table.add_row(*row)

        return table
