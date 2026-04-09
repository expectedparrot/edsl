"""Filter functionality for Results objects.

This module provides the ResultsFilter class which handles filtering operations
on Results objects, including expression validation and evaluation.
"""

import re
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .results import Results

from .exceptions import ResultsFilterError


class ResultsFilter:
    """Handles filtering operations for Results objects.

    This class encapsulates all the filtering logic for Results objects,
    including expression validation and boolean evaluation against Result data.

    Attributes:
        results: The Results object to filter
    """

    def __init__(self, results: "Results"):
        """Initialize the filter with a Results object.

        Args:
            results: The Results object to filter
        """
        self.results = results

    def _get_empty_filter_hint(self, expression: str) -> str:
        """Generate a hint when a filter returns no results, checking for type mismatches."""
        hints = []
        try:
            columns = self.results.columns
            for col in columns:
                if col in expression:
                    values = [
                        r.get_value(col.split(".", 1)[0], col.split(".", 1)[1])
                        for r in self.results.data[:20]
                        if r.get_value(col.split(".", 1)[0], col.split(".", 1)[1]) is not None
                    ]
                    if values:
                        sample_type = type(values[0]).__name__
                        unique_vals = list(set(repr(v) for v in values))[:5]
                        hints.append(
                            f"Column '{col}' contains {sample_type} values "
                            f"(e.g., {', '.join(unique_vals)})."
                        )
                        # Detect bool vs string mismatch
                        if sample_type == "bool" and (
                            "'true'" in expression.lower()
                            or "'false'" in expression.lower()
                            or '"true"' in expression.lower()
                            or '"false"' in expression.lower()
                        ):
                            hints.append(
                                "Hint: You're comparing a bool column against a string. "
                                "Use True/False (without quotes) instead of 'true'/'false'."
                            )
        except Exception:
            pass
        return " ".join(hints) if hints else "Check that your filter values match the actual data types and values."

    def _get_filter_hint(self, expression: str, error: Exception) -> str:
        """Generate a helpful hint based on the error and actual data types.

        Detects common mistakes like using 'true'/'false' instead of True/False,
        or comparing against a string when the column contains booleans (or vice versa).
        """
        error_str = str(error)

        # Detect 'true'/'false' not defined — user likely meant True/False
        if "'true' is not defined" in error_str or "'false' is not defined" in error_str:
            return "Hint: Use Python boolean literals True/False (capitalized), not true/false."

        # Try to detect type mismatches by inspecting the column values
        try:
            columns = self.results.columns
            for col in columns:
                if col in expression:
                    values = [
                        r.get_value(col.split(".", 1)[0], col.split(".", 1)[1])
                        for r in self.results.data[:5]
                        if r.get_value(col.split(".", 1)[0], col.split(".", 1)[1]) is not None
                    ]
                    if values:
                        sample_type = type(values[0]).__name__
                        sample_vals = list(set(repr(v) for v in values[:3]))
                        return (
                            f"Hint: Column '{col}' contains {sample_type} values "
                            f"(e.g., {', '.join(sample_vals)}). Check for type mismatches."
                        )
        except Exception:
            pass

        return ""

    def _expand_wildcards(self, expression: str) -> str:
        """Expand wildcard patterns in filter expressions to OR'd conditions.

        Finds patterns like ``question_text.*`` in the expression and replaces
        them with all matching column names joined by ``or``.

        For example, if columns are ``['question_text.q1', 'question_text.q2']``:
            ``question_text.* == 'Hello'``
        becomes:
            ``(question_text.q1 == 'Hello' or question_text.q2 == 'Hello')``

        Args:
            expression: The filter expression potentially containing wildcards.

        Returns:
            The expression with wildcards expanded, or the original if none found.
        """
        columns = self.results.columns

        # Match wildcard references like data_type.* or data_type.*suffix
        wildcard_pattern = re.compile(r'(\w+\.\*[\w]*)')
        wildcards = wildcard_pattern.findall(expression)

        if not wildcards:
            return expression

        from fnmatch import fnmatch

        for wc in set(wildcards):
            matching_cols = [c for c in columns if fnmatch(c, wc)]
            if not matching_cols:
                continue

            # Build the rest of the expression around the wildcard
            # Find the full comparison containing this wildcard
            # e.g. "question_text.* == 'Hello'" or "question_text.* in ['a', 'b']"
            escaped_wc = re.escape(wc)
            comparison_pattern = re.compile(
                rf'{escaped_wc}\s*(==|!=|>=|<=|>|<|in\b|not\s+in\b)\s*(.+?)(?=\s+(?:and|or)\s+|$)'
            )
            match = comparison_pattern.search(expression)
            if not match:
                continue

            operator = match.group(1)
            value = match.group(2).strip()
            full_match = match.group(0)

            expanded_parts = [f"{col} {operator} {value}" for col in matching_cols]
            expanded = "(" + " or ".join(expanded_parts) + ")"

            expression = expression.replace(full_match, expanded)

        return expression

    @staticmethod
    def has_single_equals(expression: str) -> bool:
        """Check if an expression contains a single equals sign not part of ==, >=, or <=.

        Args:
            expression: String expression to check

        Returns:
            bool: True if there is a standalone = sign

        Examples:
            >>> ResultsFilter.has_single_equals("x = 1")
            True
            >>> ResultsFilter.has_single_equals("x == 1")
            False
            >>> ResultsFilter.has_single_equals("x >= 1")
            False
            >>> ResultsFilter.has_single_equals("x <= 1")
            False
        """
        # First remove valid operators that contain =
        cleaned = (
            expression.replace("==", "")
            .replace(">=", "")
            .replace("<=", "")
            .replace("!=", "")
        )
        return "=" in cleaned

    def filter(self, expression: str) -> "Results":
        """Filter results based on a boolean expression.

        Evaluates a boolean expression against each Result object in the
        collection and returns a new Results object containing only those that match.
        The expression can reference any column in the data and supports standard
        Python operators and syntax.

        Args:
            expression: A string containing a Python expression that evaluates to a boolean.
                       The expression is applied to each Result object individually.
                       Can be a multi-line string for better readability.
                       Supports template-style syntax with {{ field }} notation.

        Returns:
            A new Results object containing only the Result objects that satisfy the expression.

        Raises:
            ResultsFilterError: If the expression is invalid or uses improper syntax
                (like using '=' instead of '==').

        Notes:
            - Column names can be specified with or without their data type prefix
              (e.g., both "how_feeling" and "answer.how_feeling" work if unambiguous)
            - You must use double equals (==) for equality comparison, not single equals (=)
            - You can use logical operators like 'and', 'or', 'not'
            - You can use comparison operators like '==', '!=', '>', '<', '>=', '<='
            - You can use membership tests with 'in'
            - You can use string methods like '.startswith()', '.contains()', etc.
            - The expression can be a multi-line string for improved readability
            - You can use template-style syntax with double curly braces: {{ field }}

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()

            >>> # Simple equality filter
            >>> r.filter("how_feeling == 'Great'").select('how_feeling')
            Dataset([{'answer.how_feeling': ['Great']}])

            >>> # Using OR condition
            >>> r.filter("how_feeling == 'Great' or how_feeling == 'Terrible'").select('how_feeling')
            Dataset([{'answer.how_feeling': ['Great', 'Terrible']}])

            >>> # Filter on agent properties
            >>> r.filter("agent.status == 'Joyful'").select('agent.status')
            Dataset([{'agent.status': ['Joyful', 'Joyful']}])
        """
        # Import here to avoid circular imports
        from .results import Results

        # Normalize expression by removing extra whitespace and newlines
        normalized_expression = " ".join(expression.strip().split())

        # Remove template-style syntax (double curly braces)
        normalized_expression = normalized_expression.replace("{{", "").replace(
            "}}", ""
        )

        if self.has_single_equals(normalized_expression):
            raise ResultsFilterError(
                "You must use '==' instead of '=' in the filter expression."
            )

        # Expand wildcard patterns (e.g. question_text.* == 'Hello')
        normalized_expression = self._expand_wildcards(normalized_expression)

        try:
            # Create new Results object with same class as original but empty data
            filtered_results = Results(
                survey=self.results.survey,
                data=[],  # Empty data list
                created_columns=self.results.created_columns,
            )

            # Process one result at a time
            for result in self.results.data:
                from .results_transformer import ResultsTransformer

                evaluator = ResultsTransformer._create_evaluator(result)
                result.check_expression(normalized_expression)  # check expression
                if evaluator.eval(normalized_expression):
                    filtered_results.append(
                        result
                    )  # Use append method to add matching results

            if len(filtered_results) == 0:
                hint = self._get_empty_filter_hint(normalized_expression)
                warnings.warn(
                    f"No results remain after applying the filter: {expression}\n{hint}"
                )

            return filtered_results

        except ValueError as e:
            raise ResultsFilterError(
                f"Error in filter expression: {expression}\n"
                f"Exception: {e}\n"
                f"See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details."
            )
        except Exception as e:
            hint = self._get_filter_hint(normalized_expression, e)
            raise ResultsFilterError(
                f"Error in filter expression: {expression}\n"
                f"Exception: {e}\n"
                f"{hint}\n"
                f"Make sure the expression is a valid Python expression that evaluates to a boolean.\n"
                f'For example, \'how_feeling == "Great"\' or \'how_feeling in ["Great", "Terrible"]\'.\n'
                f"See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details."
            )
