"""Filter functionality for Results objects.

This module provides the ResultsFilter class which handles filtering operations
on Results objects, including expression validation and evaluation.
"""

import warnings
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .results import Results
    from .result import Result

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

        This method evaluates a boolean expression against each Result object in the
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

        try:
            # Create new Results object with same class as original but empty data
            filtered_results = Results(
                survey=self.results.survey,
                data=[],  # Empty data list
                created_columns=self.results.created_columns,
                data_class=self.results._data_class,  # Preserve the original data class
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
                warnings.warn("No results remain after applying the filter.")

            return filtered_results

        except ValueError as e:
            raise ResultsFilterError(
                f"Error in filter. Exception:{e}",
                f"The expression you provided was: {expression}",
                "See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details.",
            )
        except Exception as e:
            raise ResultsFilterError(
                f"Error in filter. Exception:{e}.",
                f"The expression you provided was: {expression}.",
                "Please make sure that the expression is a valid Python expression that evaluates to a boolean.",
                'For example, \'how_feeling == "Great"\' is a valid expression, as is \'how_feeling in ["Great", "Terrible"]\'.',
                "However, 'how_feeling = \"Great\"' is not a valid expression.",
                "See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details.",
            )
