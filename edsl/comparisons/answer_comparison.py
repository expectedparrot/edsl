from __future__ import annotations

"""Container that bundles answers and metric values for a single question."""

from typing import Any, Dict
from collections.abc import Iterable

__all__ = ["AnswerComparison"]


class AnswerComparison:
    """Container for a single question's answer pair and all comparison metrics.

    This class stores two answers and all computed comparison metrics for a single
    question, providing flexible access to both the raw answers and computed scores.
    It's designed to be metric-agnostic, accepting arbitrary comparison results
    as keyword arguments.

    The class also provides utility methods for display formatting and data export.

    Attributes:
        answer_a: The first answer being compared
        answer_b: The second answer being compared
        _truncate_len: Class-level setting for display truncation (60 characters)

    Examples:
        Basic usage with metrics:

        >>> comparison = AnswerComparison(
        ...     answer_a="yes",
        ...     answer_b="no",
        ...     exact_match=False,
        ...     similarity=0.2,
        ...     question_type="yes_no"
        ... )
        >>> comparison.answer_a
        'yes'
        >>> comparison.exact_match
        False
        >>> comparison.similarity
        0.2

        Attribute access for question metadata:

        >>> comparison.question_type
        'yes_no'

        Dictionary conversion:

        >>> data = comparison.to_dict()
        >>> data['answer_a']
        'yes'
        >>> data['exact_match']
        False

        Display truncation:

        >>> long_answer = "This is a very long answer that will be truncated for display purposes"
        >>> AnswerComparison._truncate(long_answer, 20)
        'This is ...purposes'

        Working with numeric answers:

        >>> comp = AnswerComparison(42, 43, difference=1, percent_diff=0.024)
        >>> comp.answer_a
        42
        >>> comp.answer_b
        43
        >>> comp.difference
        1

        Working with list answers:

        >>> comp = AnswerComparison(
        ...     answer_a=["option1", "option2"],
        ...     answer_b=["option2", "option3"],
        ...     jaccard=0.33,
        ...     overlap_count=1
        ... )
        >>> comp.answer_a
        ['option1', 'option2']
        >>> comp.jaccard
        0.33

        Dictionary-style access:

        >>> comp = AnswerComparison("A", "B", score=0.85)
        >>> comp["score"]
        0.85
        >>> comp["nonexistent"] is None
        True

        Multiple metrics at once:

        >>> comp = AnswerComparison(
        ...     "Paris",
        ...     "London",
        ...     exact_match=False,
        ...     semantic_similarity=0.45,
        ...     edit_distance=5,
        ...     category="geography"
        ... )
        >>> comp.edit_distance
        5
        >>> comp.category
        'geography'
        >>> len(comp.to_dict())
        6
    """

    _truncate_len: int = 60  # characters for display

    def __init__(self, answer_a: Any, answer_b: Any, **metrics: Any):
        """Initialize with answer pair and arbitrary metrics.

        Args:
            answer_a: First answer in the comparison
            answer_b: Second answer in the comparison
            **metrics: Arbitrary keyword arguments for comparison metrics
                      and question metadata (e.g., exact_match=True,
                      question_type='multiple_choice')
        """
        self.answer_a = answer_a
        self.answer_b = answer_b
        # Store metrics in a private dict to avoid namespace clashes
        self._metrics: Dict[str, Any] = metrics

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: Any, max_len: int) -> str:
        """Truncate text to maximum length, showing start and end.

        Args:
            text: Text to truncate (string, iterable, or any object)
            max_len: Maximum length for the result

        Returns:
            Truncated string with '...' in the middle if needed

        Examples:
            String shorter than max length is unchanged:

            >>> AnswerComparison._truncate("short", 20)
            'short'

            Long string gets truncated:

            >>> AnswerComparison._truncate("abcdefghijklmnopqrstuvwxyz", 10)
            'abc...xyz'

            Non-string objects are converted:

            >>> AnswerComparison._truncate(42, 10)
            '42'
            >>> AnswerComparison._truncate(True, 10)
            'True'

            Lists are joined with commas:

            >>> AnswerComparison._truncate([1, 2, 3], 20)
            '1, 2, 3'
            >>> AnswerComparison._truncate(["apple", "banana", "cherry"], 15)
            'apple,...cherry'
        """
        if not isinstance(text, str):
            if isinstance(text, Iterable):
                text = ", ".join(map(str, text))
            else:
                text = str(text)
        if len(text) <= max_len:
            return text
        half = (max_len - 3) // 2
        return text[:half] + "..." + text[-half:]

    # ------------------------------------------------------------------
    # Dict/attr-like access to metrics
    # ------------------------------------------------------------------

    def __getattr__(self, item: str):
        if item in self._metrics:
            return self._metrics[item]
        raise AttributeError(item)

    def __getitem__(self, item: str):
        return self._metrics.get(item)

    def to_dict(self) -> Dict[str, Any]:
        """Return all comparison data as a dictionary.

        Returns:
            Dictionary containing answer_a, answer_b, and all metrics

        Examples:
            >>> comp = AnswerComparison("yes", "no", exact_match=False)
            >>> data = comp.to_dict()
            >>> sorted(data.keys())
            ['answer_a', 'answer_b', 'exact_match']
        """
        result = {
            "answer_a": self.answer_a,
            "answer_b": self.answer_b,
        }
        result.update(self._metrics)
        return result

    # ------------------------------------------------------------------
    # Display methods
    # ------------------------------------------------------------------

    def _summary_repr(self) -> str:
        """Generate a Rich-formatted table representation of the comparison.

        Returns:
            str: Two formatted tables - one for question/answers, one for comparison metrics
        """
        from rich.console import Console
        from rich.table import Table
        import io

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        
        # Table 1: Question and Answers
        answers_table = Table(title="Question & Answers", show_header=True)
        answers_table.add_column("", style="bold cyan", width=20)
        answers_table.add_column("Value", style="white", width=60)
        
        # Add question metadata if available
        question_metadata = ['question_text', 'question_type', 'question_options']
        for key in question_metadata:
            if key in self._metrics and self._metrics[key] is not None:
                value = self._metrics[key]
                # Format the label
                label = key.replace('question_', '').replace('_', ' ').title()
                # Truncate long values
                val_str = str(value)
                if len(val_str) > 60:
                    val_str = val_str[:57] + "..."
                answers_table.add_row(f"[dim]{label}[/dim]", f"[dim]{val_str}[/dim]")
        
        # Add separator before answers if we had question metadata
        if any(key in self._metrics for key in question_metadata):
            answers_table.add_section()
        
        # Truncate answers for display
        answer_a_display = self._truncate(self.answer_a, 60)
        answer_b_display = self._truncate(self.answer_b, 60)
        
        answers_table.add_row("[yellow]Answer A[/yellow]", f"[yellow]{answer_a_display}[/yellow]")
        answers_table.add_row("[green]Answer B[/green]", f"[green]{answer_b_display}[/green]")
        
        console.print(answers_table)
        
        # Table 2: Comparison Metrics (excluding question metadata)
        if self._metrics:
            console.print()
            stats_table = Table(title="Comparison Metrics", show_header=True)
            stats_table.add_column("Metric", style="cyan", width=40)
            stats_table.add_column("Value", style="white", width=25)
            
            # Show most important comparison metrics
            priority_metrics = ['exact_match', 'cosine_similarity (all-MiniLM-L6-v2)', 
                              'cosine_similarity (all-mpnet-base-v2)', 'jaccard_similarity', 
                              'overlap', 'negative_squared_distance']
            
            # Exclude question metadata from comparison metrics
            excluded_metadata = ['question_text', 'question_type', 'question_options']
            
            for key in priority_metrics:
                if key in self._metrics:
                    value = self._metrics[key]
                    if isinstance(value, float):
                        formatted_val = f"[magenta]{value:.4f}[/magenta]"
                    elif isinstance(value, bool):
                        color = "green" if value else "red"
                        symbol = "✓" if value else "✗"
                        formatted_val = f"[{color}]{symbol}[/{color}]"
                    elif value is None:
                        formatted_val = "[dim]-[/dim]"
                    else:
                        formatted_val = str(value)
                    stats_table.add_row(key, formatted_val)
            
            # Add other metrics (excluding question metadata)
            other_metrics = [(k, v) for k, v in sorted(self._metrics.items()) 
                           if k not in priority_metrics 
                           and k not in excluded_metadata
                           and v is not None]
            
            if other_metrics:
                stats_table.add_section()
                for key, value in other_metrics:
                    if isinstance(value, float):
                        formatted_val = f"[dim]{value:.4f}[/dim]"
                    elif isinstance(value, bool):
                        formatted_val = "[dim]✓[/dim]" if value else "[dim]✗[/dim]"
                    else:
                        # Truncate long values
                        val_str = str(value)
                        if len(val_str) > 40:
                            val_str = val_str[:37] + "..."
                        formatted_val = f"[dim]{val_str}[/dim]"
                    stats_table.add_row(f"[dim]{key}[/dim]", formatted_val)
            
            console.print(stats_table)
        
        return console.file.getvalue()

    def __repr__(self) -> str:  # pragma: no cover
        a = self._truncate(self.answer_a, self._truncate_len)
        b = self._truncate(self.answer_b, self._truncate_len)
        metric_parts = []
        for k, v in self._metrics.items():
            metric_parts.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
        return f"AnswerComparison(answer_a='{a}', answer_b='{b}', {', '.join(metric_parts)})"


if __name__ == "__main__":
    import doctest
    doctest.testmod()
