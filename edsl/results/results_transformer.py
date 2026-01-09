"""
Results data transformation functionality.

This module provides the ResultsTransformer class which handles data transformation
operations for Results objects, including mutating columns, renaming columns, and
sorting results.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from . import Results
    from .result import Result
    from simpleeval import EvalWithCompoundTypes

from .exceptions import (
    ResultsBadMutationstringError,
    ResultsInvalidNameError,
    ResultsMutateError,
    ResultsColumnNotFoundError,
)


class ResultsTransformer:
    """
    Handles data transformation operations for Results objects.

    This class encapsulates methods for transforming Results objects including
    creating new derived columns (mutate), renaming columns, and sorting results,
    providing a clean separation of transformation logic from the main Results class.
    """

    def __init__(self, results: "Results"):
        """
        Initialize the ResultsTransformer with a Results object.

        Args:
            results: The Results object to perform transformation operations on
        """
        self.results = results

    @staticmethod
    def _create_evaluator(
        result: "Result", functions_dict: Optional[dict] = None
    ) -> "EvalWithCompoundTypes":
        """Create an evaluator for the expression.

        Args:
            result: The Result object to create an evaluator for
            functions_dict: Optional dictionary of custom functions to include

        Returns:
            EvalWithCompoundTypes: An evaluator that can evaluate expressions
                against the result's data

        Examples:
            >>> from unittest.mock import Mock
            >>> result = Mock()
            >>> result.combined_dict = {'how_feeling': 'OK'}
            >>> evaluator = ResultsTransformer._create_evaluator(result = result, functions_dict = {})
            >>> evaluator.eval("how_feeling == 'OK'")
            True

            >>> result.combined_dict = {'answer': {'how_feeling': 'OK'}}
            >>> evaluator = ResultsTransformer._create_evaluator(result = result, functions_dict = {})
            >>> evaluator.eval("answer.how_feeling== 'OK'")
            True

            Note that you need to refer to the answer dictionary in the expression.

            >>> evaluator.eval("how_feeling== 'OK'")
            Traceback (most recent call last):
            ...
            simpleeval.NameNotDefined: 'how_feeling' is not defined for expression 'how_feeling== 'OK''
        """
        from simpleeval import EvalWithCompoundTypes

        if functions_dict is None:
            functions_dict = {}
        evaluator = EvalWithCompoundTypes(
            names=result.combined_dict, functions=functions_dict
        )
        evaluator.functions.update(int=int, float=float)
        return evaluator

    def _parse_column(self, column: str) -> tuple[str, str]:
        """Parse a column name into a data type and key.

        Args:
            column: Column name to parse, either simple name or "data_type.key" format

        Returns:
            tuple[str, str]: (data_type, key) pair
        """
        if "." in column:
            return column.split(".", 1)
        return self.results._cache_manager.key_to_data_type[column], column

    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict] = None
    ) -> "Results":
        """Create a new column based on a computational expression.

        The mutate method allows you to create new derived variables based on existing data.
        You provide an assignment expression where the left side is the new column name
        and the right side is a Python expression that computes the value. The expression
        can reference any existing columns in the Results object.

        Args:
            new_var_string: A string containing an assignment expression in the form
                "new_column_name = expression". The expression can reference
                any existing column and use standard Python syntax.
            functions_dict: Optional dictionary of custom functions that can be used in
                the expression. Keys are function names, values are function objects.

        Returns:
            A new Results object with the additional column.

        Notes:
            - The expression must contain an equals sign (=) separating the new column name
              from the computation expression
            - The new column name must be a valid Python variable name
            - The expression is evaluated for each Result object individually
            - The expression can access any data in the Result object using the column names
            - New columns are added to the "answer" data type
            - Created columns are tracked in the `created_columns` property

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> transformer = ResultsTransformer(r)

            >>> # Create a simple derived column
            >>> result = transformer.mutate('how_feeling_x = how_feeling + "x"')
            >>> result.select('how_feeling_x')
            Dataset([{'answer.how_feeling_x': ['OKx', 'Greatx', 'Terriblex', 'OKx']}])

            >>> # Create a binary indicator column
            >>> result = transformer.mutate('is_great = 1 if how_feeling == "Great" else 0')
            >>> result.select('is_great')
            Dataset([{'answer.is_great': [0, 1, 0, 0]}])

            >>> # Create a column with custom functions
            >>> def sentiment(text):
            ...     return len(text) > 5
            >>> result = transformer.mutate('is_long = sentiment(how_feeling)',
            ...                           functions_dict={'sentiment': sentiment})
            >>> result.select('is_long')
            Dataset([{'answer.is_long': [False, False, True, False]}])
        """
        # extract the variable name and the expression
        if "=" not in new_var_string:
            raise ResultsBadMutationstringError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()
        from ..utilities.utilities import is_valid_variable_name

        if not is_valid_variable_name(var_name):
            raise ResultsInvalidNameError(f"{var_name} is not a valid variable name.")

        # create the evaluator
        functions_dict = functions_dict or {}

        def new_result(old_result: "Result", var_name: str) -> "Result":
            evaluator = self._create_evaluator(old_result, functions_dict)
            value = evaluator.eval(expression)
            new_result = old_result.copy()
            new_result["answer"][var_name] = value
            return new_result

        try:
            new_data = [new_result(result, var_name) for result in self.results.data]
        except Exception as e:
            raise ResultsMutateError(f"Error in mutate. Exception:{e}")

        # Import here to avoid circular import
        from . import Results

        new_results = Results(
            survey=self.results.survey,
            data=new_data,
            created_columns=self.results.created_columns + [var_name],
        )
        new_results._cache_manager.invalidate_cache()
        return new_results

    def rename(self, old_name: str, new_name: str) -> "Results":
        """Rename an answer column in a Results object.

        Args:
            old_name: The current name of the column to rename
            new_name: The new name for the column

        Returns:
            Results: A new Results object with the column renamed

        Raises:
            ResultsColumnNotFoundError: If old_name does not exist in the results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> transformer = ResultsTransformer(r)
            >>> result = transformer.rename('how_feeling', 'how_feeling_new')  # doctest: +SKIP
            >>> result.select('how_feeling_new')  # doctest: +SKIP
            Dataset([{'answer.how_feeling_new': ['OK', 'Great', 'Terrible', 'OK']}])
        """
        # Import here to avoid circular import
        from . import Results

        # Validate that old_name exists in all results
        for obs in self.results.data:
            if old_name not in obs.get("answer", {}):
                raise ResultsColumnNotFoundError(
                    f"The column '{old_name}' is not present in the results."
                )

        # Create new Results object with same properties but empty data
        new_results = Results(
            survey=self.results.survey,
            data=[],
            created_columns=self.results.created_columns,
        )

        # Update created_columns if old_name was in there
        if old_name in new_results.created_columns:
            new_results.created_columns.remove(old_name)
            new_results.created_columns.append(new_name)

        # Process one result at a time
        for obs in self.results.data:
            new_result = obs.copy()
            new_result["answer"][new_name] = new_result["answer"][old_name]
            del new_result["answer"][old_name]
            new_results.append(new_result)

        new_results._cache_manager.invalidate_cache()
        return new_results

    def order_by(self, *columns: str, reverse: bool = False) -> "Results":
        """Sort the results by one or more columns.

        Args:
            columns: One or more column names as strings.
            reverse: A boolean that determines whether to sort in reverse order.

        Returns:
            Results: A new Results object with sorted data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> transformer = ResultsTransformer(r)
            >>> sorted_results = transformer.order_by('how_feeling')
            >>> len(sorted_results) == len(r)
            True
        """

        def to_numeric_if_possible(v):
            try:
                return float(v)
            except (ValueError, TypeError):
                return v

        def sort_key(item):
            key_components = []
            for col in columns:
                data_type, key = self._parse_column(col)
                value = item.get_value(data_type, key)
                if isinstance(value, (str, bytes)):
                    key_components.append(str(value))
                else:
                    key_components.append(to_numeric_if_possible(value))
            return tuple(key_components)

        # Create a new sorted view of the data without materializing it
        sorted_data = sorted(self.results.data, key=sort_key, reverse=reverse)

        # Import here to avoid circular import
        from . import Results

        # Create new Results object that uses the sorted iterator
        return Results(
            survey=self.results.survey,
            data=sorted_data,  # This will be an iterator, not a materialized list
            created_columns=self.results.created_columns,
            sort_by_iteration=False,
        )
