from __future__ import annotations

"""Container for result pair comparison differences."""

from typing import Sequence, Optional, List, Callable, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from .result_pair_comparison import ResultPairComparison
    from .answer_comparison import AnswerComparison


class ResultDifferences:
    """Container for differences between two results with interactive display.

    Holds a list of formatted question comparison differences and provides
    an interactive HTML view with navigation controls.
    """

    def __init__(
        self,
        differences: List[str],
        question_names: List[str],
        result_comparison: "ResultPairComparison",
        template: Optional[str] = None,
        exclude_exact_match: bool = True,
        exclude_answer_values: Optional[Sequence[str]] = None,
        filter_func: Optional[Callable[[str, "AnswerComparison"], bool]] = None,
    ):
        """Initialize ResultDifferences container.

        Args:
            differences: List of formatted difference strings for each question
            question_names: List of question names corresponding to differences
            result_comparison: The ResultPairComparison object that created these differences
            template: Optional Jinja2 template string used for formatting
            exclude_exact_match: Whether exact matches were excluded
            exclude_answer_values: Values that were excluded from differences
            filter_func: Custom filter function that was applied
        """
        self.differences = differences
        self.question_names = question_names
        self.result_comparison = result_comparison
        self.template = template
        self.exclude_exact_match = exclude_exact_match
        self.exclude_answer_values = exclude_answer_values
        self.filter_func = filter_func

    def __repr__(self) -> str:
        """Return string representation of ResultDifferences."""
        return f"ResultDifferences(count={len(self.differences)})"

    def __len__(self) -> int:
        """Return the number of differences."""
        return len(self.differences)

    def __getitem__(self, index: int) -> str:
        """Get a specific difference by index."""
        return self.differences[index]

    def __iter__(self):
        """Iterate over differences."""
        return iter(self.differences)

    def __str__(self) -> str:
        """Return all differences joined by double newlines."""
        return "\n\n".join(self.differences)

    @classmethod
    def from_comparison(
        cls,
        result_comparison: "ResultPairComparison",
        question_names: Optional[Sequence[str]] = None,
        template: Optional[str] = None,
        exclude_exact_match: bool = True,
        exclude_answer_values: Optional[Sequence[str]] = None,
        filter_func: Optional[Callable[[str, "AnswerComparison"], bool]] = None,
    ) -> "ResultDifferences":
        """Create ResultDifferences from a ResultPairComparison.

        Args:
            result_comparison: The ResultPairComparison to extract differences from
            question_names: Optional sequence of question names to include.
                          If None, includes all questions (subject to filters).
            template: Optional Jinja2 template string for formatting
            exclude_exact_match: If True, exclude questions where exact_match is True.
                               Default: True
            exclude_answer_values: Sequence of answer values to exclude. Questions where
                                 answer_b matches any of these values (case-insensitive)
                                 will be excluded. Default: ["n/a", "none", "missing"]
            filter_func: Optional custom filter function that takes (question_name,
                        AnswerComparison) and returns True to include

        Returns:
            ResultDifferences instance with formatted differences

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> from edsl.comparisons.result_differences import ResultDifferences
            >>> rc = ResultPairComparison.example()
            >>> rd = ResultDifferences.from_comparison(rc)
            >>> len(rd) > 0
            True
        """
        from .comparison_formatter import ComparisonFormatter

        # Set default exclude values if not provided
        if exclude_answer_values is None:
            exclude_answer_values = ["n/a", "none", "missing"]

        # Get the scenario list
        sl = result_comparison.to_scenario_list()

        # Create formatter
        formatter = ComparisonFormatter(sl, template=template)

        # Determine which questions to consider
        if question_names is None:
            candidate_questions = list(result_comparison.comparison.keys())
        else:
            candidate_questions = list(question_names)

        # Apply filters and format
        formatted_parts = []
        included_question_names = []

        for qname in candidate_questions:
            # Skip if question not found
            if qname not in result_comparison.comparison:
                continue

            # Apply built-in filters
            if not result_comparison.should_include_question(
                qname,
                exclude_exact_match=exclude_exact_match,
                exclude_answer_values=exclude_answer_values,
            ):
                continue

            # Apply custom filter if provided
            if filter_func is not None:
                comparison_data = result_comparison.comparison[qname]
                if not filter_func(qname, comparison_data):
                    continue

            # Format this question
            try:
                formatted_parts.append(formatter.format_question(qname))
                included_question_names.append(qname)
            except KeyError:
                # Question not found in formatter, skip it
                pass

        return cls(
            differences=formatted_parts,
            question_names=included_question_names,
            result_comparison=result_comparison,
            template=template,
            exclude_exact_match=exclude_exact_match,
            exclude_answer_values=exclude_answer_values,
            filter_func=filter_func,
        )

    def show(self) -> str:
        """Generate interactive HTML with navigation controls.

        Returns an HTML string with forward/backward buttons to navigate through
        differences one at a time.

        Returns:
            HTML string with interactive navigation

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> from edsl.comparisons.result_differences import ResultDifferences
            >>> rc = ResultPairComparison.example()
            >>> rd = ResultDifferences.from_comparison(rc)
            >>> html = rd.show()
            >>> "button" in html.lower()
            True
        """
        if not self.differences:
            return "<div><p>No differences to display.</p></div>"

        # Generate a unique ID for this widget instance
        widget_id = f"result-diff-{uuid.uuid4().hex[:8]}"
        # JavaScript-safe function name (replace hyphens with underscores)
        js_func_name = widget_id.replace("-", "_")

        # Escape HTML entities in the content to prevent XSS, but preserve formatting
        import json

        # Just use the differences as-is - they'll render with proper angle brackets
        formatted_differences = self.differences

        # Build the HTML
        html_parts = []

        # Add styles
        html_parts.append(
            f"""
<style>
    #{widget_id} {{
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
        max-width: 900px;
        margin: 20px auto;
        border: 1px solid #ddd;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    #{widget_id} .header {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 15px 20px;
        border-radius: 8px 8px 0 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    #{widget_id} .header h3 {{
        margin: 0;
        font-size: 18px;
        font-weight: 600;
    }}
    #{widget_id} .counter {{
        background: rgba(255,255,255,0.2);
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 14px;
    }}
    #{widget_id} .content {{
        padding: 25px;
        background: #f9fafb;
        min-height: 300px;
        white-space: pre-wrap;
        font-size: 14px;
        line-height: 1.6;
    }}
    #{widget_id} .controls {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px 20px;
        background: white;
        border-radius: 0 0 8px 8px;
        border-top: 1px solid #e5e7eb;
    }}
    #{widget_id} button {{
        background: #667eea;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: all 0.2s;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    #{widget_id} button:hover:not(:disabled) {{
        background: #5568d3;
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(102, 126, 234, 0.3);
    }}
    #{widget_id} button:disabled {{
        background: #d1d5db;
        cursor: not-allowed;
        opacity: 0.6;
    }}
    #{widget_id} .question-name {{
        color: #6b7280;
        font-size: 13px;
        font-weight: 500;
    }}
</style>
"""
        )

        # Add the widget structure
        html_parts.append(
            f"""
<div id="{widget_id}">
    <div class="header">
        <h3>Result Differences</h3>
        <div class="counter">
            <span id="{widget_id}-current">1</span> / <span id="{widget_id}-total">{len(self.differences)}</span>
        </div>
    </div>
    <div class="content" id="{widget_id}-content">
        {formatted_differences[0] if formatted_differences else 'No differences'}
    </div>
    <div class="controls">
        <button id="{widget_id}-prev" onclick="{js_func_name}_navigate(-1)">
            <span>←</span> Previous
        </button>
        <div class="question-name" id="{widget_id}-question">
            {self.question_names[0] if self.question_names else ''}
        </div>
        <button id="{widget_id}-next" onclick="{js_func_name}_navigate(1)">
            Next <span>→</span>
        </button>
    </div>
</div>
"""
        )

        # Add JavaScript for navigation
        # Embed the differences data as a JSON array
        differences_json = json.dumps(formatted_differences)
        questions_json = json.dumps(self.question_names)

        html_parts.append(
            f"""
<script>
(function() {{
    const differences = {differences_json};
    const questions = {questions_json};
    let currentIndex = 0;
    
    window.{js_func_name}_navigate = function(direction) {{
        currentIndex += direction;
        
        // Clamp to valid range
        if (currentIndex < 0) currentIndex = 0;
        if (currentIndex >= differences.length) currentIndex = differences.length - 1;
        
        // Update content
        document.getElementById('{widget_id}-content').textContent = differences[currentIndex];
        document.getElementById('{widget_id}-current').textContent = currentIndex + 1;
        document.getElementById('{widget_id}-question').textContent = questions[currentIndex];
        
        // Update button states
        document.getElementById('{widget_id}-prev').disabled = (currentIndex === 0);
        document.getElementById('{widget_id}-next').disabled = (currentIndex === differences.length - 1);
    }};
    
    // Initialize button states
    document.getElementById('{widget_id}-prev').disabled = true;
    if (differences.length <= 1) {{
        document.getElementById('{widget_id}-next').disabled = true;
    }}
}})();
</script>
"""
        )

        return "".join(html_parts)

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebooks."""
        return self.show()


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
