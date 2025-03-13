
from ..base import BaseException

class ResultsError(BaseException):
    """
    Base exception class for all results-related errors.
    
    This is the parent class for all exceptions related to Results objects
    operations, including data manipulation, selection, and filtering.
    
    This exception is raised in the following cases:
    - When trying to add two Results objects with different surveys or created columns
    - When trying to sample more items than available
    - When Survey is not defined when accessing answer_keys
    - When fetching remote Results fails
    - When inappropriate model types are used with Results methods
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html"


class ResultsDeserializationError(ResultsError):
    """
    Exception raised when Results object deserialization fails.
    
    This exception occurs when a Results object cannot be properly reconstructed
    from its serialized representation, typically during from_dict() operations.
    
    Reasons this might occur:
    - Missing required fields in the serialized data
    - Corrupted serialized data
    - Version incompatibility between serialized data and current code
    
    To fix this error:
    1. Check that the serialized data is complete and uncorrupted
    2. Ensure you're using a compatible version of EDSL to deserialize the data
    3. If the issue persists, you may need to recreate the results from raw data
    
    Examples:
        ```python
        Results.from_dict(incomplete_or_corrupted_data)  # Raises ResultsDeserializationError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html#saving-and-loading-results"


class ResultsBadMutationstringError(ResultsError):
    """
    Exception raised when an invalid mutation string is provided.
    
    This exception occurs when the mutation string doesn't follow the required format,
    which should be 'column_name = expression' where expression is a valid Python
    expression that can reference other columns.
    
    To fix this error:
    1. Ensure your mutation string contains an equals sign
    2. Check that the left side is a valid column name
    3. Verify the right side is a valid Python expression
    
    Examples:
        ```python
        results.mutate("invalid_mutation_no_equals")  # Raises ResultsBadMutationstringError
        results.mutate("column_name == value")  # Raises ResultsBadMutationstringError (should use single =)
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html#creating-new-columns"


class ResultsColumnNotFoundError(ResultsError):
    """
    Exception raised when attempting to access a non-existent column.
    
    This exception occurs when trying to access, filter, or perform operations
    on a column that doesn't exist in the Results object.
    
    To fix this error:
    1. Check for typos in the column name
    2. Verify the column exists using results.columns() or results.df.columns
    3. If the column is dynamic, ensure it has been created with mutate() first
    
    The error message typically includes suggestions for similar column names 
    that do exist, which can help identify typos.
    
    Examples:
        ```python
        results.table(keys=["non_existent_column"])  # Raises ResultsColumnNotFoundError
        results.select("typo_in_column_name")  # Raises ResultsColumnNotFoundError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html#selecting-columns"


class ResultsInvalidNameError(ResultsError):
    """
    Exception raised when an invalid column name is provided.
    
    This exception occurs when:
    - The provided name is not a valid Python identifier
    - The name conflicts with reserved names or methods
    - The name contains invalid characters or starts with a number
    
    To fix this error:
    1. Use names that follow Python variable naming rules
    2. Avoid using reserved words or existing method names
    3. Use only letters, numbers, and underscores (not starting with a number)
    
    Examples:
        ```python
        results.mutate("123invalid = 1")  # Raises ResultsInvalidNameError (starts with number)
        results.mutate("invalid-name = 1")  # Raises ResultsInvalidNameError (contains hyphen)
        results.mutate("filter = 1")  # Raises ResultsInvalidNameError (reserved method name)
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html#creating-new-columns"


class ResultsMutateError(ResultsError):
    """
    Exception raised when a mutation operation fails.
    
    This exception occurs when an error happens during the execution of a mutation
    expression, such as:
    - Syntax errors in the expression
    - Reference to non-existent columns
    - Type errors in operations (e.g., adding a string to a number)
    
    To fix this error:
    1. Check the expression syntax
    2. Verify all columns referenced in the expression exist
    3. Ensure type compatibility in operations
    4. Test the expression with simple cases first
    
    Examples:
        ```python
        results.mutate("new_col = old_col + 'text'")  # Raises ResultsMutateError if old_col contains numbers
        results.mutate("new_col = undefined_col + 1")  # Raises ResultsMutateError if undefined_col doesn't exist
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html#creating-new-columns"


class ResultsFilterError(ResultsError):
    """
    Exception raised when a filter operation fails.
    
    This exception occurs when there's an error in the filter expression, such as:
    - Using single equals (=) instead of double equals (==) for comparison
    - Syntax errors in the filter expression
    - Reference to non-existent columns
    - Type errors in comparisons
    
    To fix this error:
    1. Use == (double equals) for equality comparisons, not = (single equals)
    2. Check the filter expression syntax
    3. Verify all columns referenced in the expression exist
    4. Ensure type compatibility in comparisons
    
    Examples:
        ```python
        results.filter("column = value")  # Raises ResultsFilterError (use == instead)
        results.filter("column == undefined_var")  # Raises ResultsFilterError if undefined_var isn't defined
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/results.html#filtering-results"
