"""
Column selection and data extraction module for Results objects.

This module provides the Selector class that implements the column selection
functionality for the Results object's select() method. It handles column name
normalization, matching, and data extraction, supporting both direct column references
and wildcard patterns.
"""

from typing import Union, List, Dict, Any, Optional, Tuple, Callable
import sys
from collections import defaultdict

# Import is_notebook but defer Dataset import to avoid potential circular imports

from .exceptions import ResultsColumnNotFoundError


class Selector:
    """
    Selects and extracts columns from a Results object to create a Dataset.
    
    The Selector class provides the functionality to extract specific data columns
    from Results objects, handling column name resolution, disambiguation,
    and wildcard matching. It transforms hierarchical Result data into a columnar
    Dataset format optimized for analysis operations.
    
    Attributes:
        known_data_types: List of valid data types (e.g., "answer", "agent", "model")
        columns: List of available column names in dot notation (e.g., "answer.how_feeling")
    """
    
    def __init__(
        self,
        known_data_types: List[str],
        data_type_to_keys: Dict[str, List[str]],
        key_to_data_type: Dict[str, str],
        fetch_list_func: Callable[[str, str], List[Any]],
        columns: List[str],
    ):
        """
        Initialize a Selector object.
        
        Args:
            known_data_types: List of valid data types (e.g., "answer", "agent", "model")
            data_type_to_keys: Mapping from data types to lists of keys available in that type
            key_to_data_type: Mapping from keys to their corresponding data types
            fetch_list_func: Function that retrieves values for a given data type and key
            columns: List of available column names in dot notation
            
        Examples:
            >>> s = Selector(
            ...     known_data_types=["answer", "agent"],
            ...     data_type_to_keys={"answer": ["q1", "q2"], "agent": ["name"]},
            ...     key_to_data_type={"q1": "answer", "q2": "answer", "name": "agent"},
            ...     fetch_list_func=lambda dt, k: [f"{dt}.{k}_val"],
            ...     columns=["answer.q1", "answer.q2", "agent.name"]
            ... )
            >>> isinstance(s, Selector)
            True
        """
        self.known_data_types = known_data_types
        self._data_type_to_keys = data_type_to_keys
        self._key_to_data_type = key_to_data_type
        self._fetch_list = fetch_list_func
        self.columns = columns
        self.items_in_order = []  # Tracks column order for consistent output

    def select(self, *columns: Union[str, List[str]]) -> Optional[Any]:
        """
        Select specific columns from the data and return as a Dataset.
        
        This method processes column specifications, fetches the corresponding data,
        and constructs a Dataset with the selected columns. It handles error cases
        differently in notebook vs non-notebook environments.
        
        Args:
            *columns: Column names to select. Each name can be a simple attribute
                     name (e.g., "how_feeling"), a fully qualified name with type
                     (e.g., "answer.how_feeling"), or a wildcard pattern
                     (e.g., "answer.*"). If no columns provided, selects all data.
                     
        Returns:
            A Dataset object containing the selected data, or None if an error occurs
            in a notebook environment.
            
        Raises:
            ResultsColumnNotFoundError: If a specified column cannot be found (non-notebook only)
            
        Examples:
            >>> import unittest.mock as mock
            >>> mock_selector = Selector(
            ...     known_data_types=["answer", "agent"],
            ...     data_type_to_keys={"answer": ["q1"], "agent": ["name"]},
            ...     key_to_data_type={"q1": "answer", "name": "agent"},
            ...     fetch_list_func=lambda dt, k: [f"{dt}-{k}1", f"{dt}-{k}2"],
            ...     columns=["answer.q1", "agent.name"]
            ... )
            >>> ds = mock_selector.select("q1")
            >>> list(ds[0].values())[0][0]
            'answer-q11'
        """
        try:
            columns = self._normalize_columns(columns)
            to_fetch = self._get_columns_to_fetch(columns)
            new_data = self._fetch_data(to_fetch)
        except ResultsColumnNotFoundError as e:
            # Check is_notebook with explicit import to ensure mock works
            from ..utilities import is_notebook as is_notebook_check
            if is_notebook_check():
                print("Error:", e, file=sys.stderr)
                return None
            else:
                raise e
                
        # Import Dataset here to avoid circular import issues
        from ..dataset import Dataset
        return Dataset(new_data)

    def _normalize_columns(self, columns: Union[str, List[str]]) -> Tuple[str, ...]:
        """
        Normalize column specifications to a standard format.
        
        This method handles various forms of column specifications, including
        converting lists to tuples, handling None values, and applying default
        wildcards when no columns are specified.
        
        Args:
            columns: Column specifications as strings or lists
            
        Returns:
            A tuple of normalized column name strings
            
        Examples:
            >>> s = Selector([], {}, {}, lambda x, y: [], [])
            >>> s._normalize_columns([["a", "b"]])
            ('a', 'b')
            >>> s._normalize_columns(None)
            ('*.*',)
            >>> s._normalize_columns(("a", "b"))
            ('a', 'b')
            >>> s._normalize_columns(("*",))
            ('*.*',)
        """
        if not columns or columns == ("*",) or columns == (None,):
            return ("*.*",)
        if isinstance(columns[0], list):
            return tuple(columns[0])
        return columns

    def _get_columns_to_fetch(self, columns: Tuple[str, ...]) -> Dict[str, List[str]]:
        """
        Process column specifications and determine what data to fetch.
        
        This method iterates through each column specification, finds matching
        columns, validates the matches, and builds a structure that organizes
        which keys to fetch for each data type.
        
        Args:
            columns: Tuple of normalized column specifications
            
        Returns:
            Dictionary mapping data types to lists of keys to fetch
            
        Raises:
            ResultsColumnNotFoundError: If columns are ambiguous or not found
            
        Examples:
            >>> import unittest.mock as mock
            >>> mock_selector = Selector(
            ...     known_data_types=["answer"],
            ...     data_type_to_keys={"answer": ["q1", "q2"]},
            ...     key_to_data_type={"q1": "answer", "q2": "answer"},
            ...     fetch_list_func=lambda dt, k: [],
            ...     columns=["answer.q1", "answer.q2"]
            ... )
            >>> to_fetch = mock_selector._get_columns_to_fetch(("q1",))
            >>> to_fetch["answer"]
            ['q1']
        """
        to_fetch = defaultdict(list)
        self.items_in_order = []

        for column in columns:
            matches = self._find_matching_columns(column)
            self._validate_matches(column, matches)

            if len(matches) == 1:
                column = matches[0]

            data_type, key = self._parse_column(column)
            self._process_column(data_type, key, to_fetch)

        return to_fetch

    def _find_matching_columns(self, partial_name: str) -> List[str]:
        """
        Find columns that match a partial column name.
        
        This method supports both fully qualified column names with data types
        (containing a dot) and simple column names, handling each case appropriately.
        It finds all columns that start with the provided partial name.
        
        Args:
            partial_name: A full or partial column name to match
            
        Returns:
            List of matching column names
            
        Examples:
            >>> s = Selector(
            ...     known_data_types=["answer", "agent"],
            ...     data_type_to_keys={},
            ...     key_to_data_type={},
            ...     fetch_list_func=lambda dt, k: [],
            ...     columns=["answer.q1", "answer.q2", "agent.name"]
            ... )
            >>> s._find_matching_columns("answer.q")
            ['answer.q1', 'answer.q2']
            >>> s._find_matching_columns("q")
            ['q1', 'q2']
        """
        if "." in partial_name:
            search_in_list = self.columns
        else:
            search_in_list = [s.split(".")[1] for s in self.columns]
        matches = [s for s in search_in_list if s.startswith(partial_name)]
        return [partial_name] if partial_name in matches else matches

    def _validate_matches(self, column: str, matches: List[str]) -> None:
        """
        Validate that matched columns are unambiguous and exist.
        
        This method checks that the column specification resolves to exactly
        one column or a wildcard pattern. It raises appropriate exceptions
        for ambiguous matches or when no matches are found.
        
        Args:
            column: The original column specification
            matches: List of matching column names
            
        Raises:
            ResultsColumnNotFoundError: If matches are ambiguous or no matches found
            
        Examples:
            >>> s = Selector([], {}, {}, lambda dt, k: [], [])
            >>> s._validate_matches("col", ["col"])  # No exception
            >>> try:
            ...     s._validate_matches("c", ["col1", "col2"])
            ... except ResultsColumnNotFoundError as e:
            ...     "ambiguous" in str(e).lower()
            True
            >>> try:
            ...     s._validate_matches("xyz", [])
            ... except ResultsColumnNotFoundError as e:
            ...     "not found" in str(e).lower()
            True
        """
        if len(matches) > 1:
            raise ResultsColumnNotFoundError(
                f"Column '{column}' is ambiguous. Did you mean one of {matches}?"
            )
        if len(matches) == 0 and ".*" not in column:
            raise ResultsColumnNotFoundError(f"Column '{column}' not found in data.")

    def _parse_column(self, column: str) -> Tuple[str, str]:
        """
        Parse a column name into data type and key components.
        
        This method handles both fully qualified column names (containing a dot)
        and simple column names, looking up the appropriate data type when needed.
        
        Args:
            column: Column name to parse
            
        Returns:
            Tuple of (data_type, key)
            
        Raises:
            ResultsColumnNotFoundError: When key cannot be found in data
            
        Examples:
            >>> s = Selector(
            ...     [],
            ...     {},
            ...     {"col1": "type1"},
            ...     lambda dt, k: [],
            ...     []
            ... )
            >>> s._parse_column("type2.col2")
            ('type2', 'col2')
            >>> s._parse_column("col1")
            ('type1', 'col1')
        """
        if "." in column:
            parts = column.split(".")
            return (parts[0], parts[1])  # Return as tuple instead of list
        try:
            return self._key_to_data_type[column], column
        except KeyError:
            self._raise_key_error(column)

    def _raise_key_error(self, column: str) -> None:
        """
        Raise an error with helpful suggestions when a column is not found.
        
        This method uses difflib to find close matches to the specified column,
        providing helpful suggestions in the error message when possible.
        
        Args:
            column: The column name that wasn't found
            
        Raises:
            ResultsColumnNotFoundError: Always raised with a descriptive message
            
        Examples:
            >>> import unittest.mock as mock
            >>> s = Selector(
            ...     [],
            ...     {},
            ...     {"column1": "type1", "column2": "type1"},
            ...     lambda dt, k: [],
            ...     []
            ... )
            >>> try:
            ...     s._raise_key_error("colum1")
            ... except ResultsColumnNotFoundError as e:
            ...     "did you mean: column1" in str(e).lower()
            True
        """
        import difflib

        close_matches = difflib.get_close_matches(column, self._key_to_data_type.keys())
        if close_matches:
            suggestions = ", ".join(close_matches)
            raise ResultsColumnNotFoundError(
                f"Column '{column}' not found in data. Did you mean: {suggestions}?"
            )
        else:
            raise ResultsColumnNotFoundError(f"Column '{column}' not found in data")

    def _process_column(self, data_type: str, key: str, to_fetch: Dict[str, List[str]]) -> None:
        """
        Process a parsed column and add it to the list of data to fetch.
        
        This method handles wildcards in both data types and keys, expands them
        appropriately, and tracks the order of items for consistent output.
        
        Args:
            data_type: The data type component (e.g., "answer", "agent")
            key: The key component (e.g., "how_feeling", "status")
            to_fetch: Dictionary to update with data to fetch
            
        Raises:
            ResultsColumnNotFoundError: If the key is not found in any relevant data type
            
        Examples:
            >>> s = Selector(
            ...     ["answer", "agent"],
            ...     {"answer": ["q1", "q2"], "agent": ["name"]},
            ...     {},
            ...     lambda dt, k: [],
            ...     []
            ... )
            >>> to_fetch = defaultdict(list)
            >>> s._process_column("answer", "q1", to_fetch)
            >>> to_fetch["answer"]
            ['q1']
            >>> s.items_in_order
            ['answer.q1']
        """
        data_types = self._get_data_types_to_return(data_type)
        found_once = False

        for dt in data_types:
            relevant_keys = self._data_type_to_keys[dt]
            for k in relevant_keys:
                if k == key or key == "*":
                    found_once = True
                    to_fetch[dt].append(k)
                    self.items_in_order.append(f"{dt}.{k}")

        if not found_once:
            raise ResultsColumnNotFoundError(f"Key '{key}' not found in data.")

    def _get_data_types_to_return(self, parsed_data_type: str) -> List[str]:
        """
        Determine which data types to include based on the parsed data type.
        
        This method handles wildcards in data types, returning either all known
        data types or validating that a specific data type exists.
        
        Args:
            parsed_data_type: Data type string or wildcard (*)
            
        Returns:
            List of data types to include
            
        Raises:
            ResultsColumnNotFoundError: If the data type is not known
            
        Examples:
            >>> s = Selector(
            ...     ["answer", "agent", "model"],
            ...     {},
            ...     {},
            ...     lambda dt, k: [],
            ...     []
            ... )
            >>> s._get_data_types_to_return("*")
            ['answer', 'agent', 'model']
            >>> s._get_data_types_to_return("answer")
            ['answer']
            >>> try:
            ...     s._get_data_types_to_return("unknown")
            ... except ResultsColumnNotFoundError:
            ...     True
            True
        """
        if parsed_data_type == "*":
            return self.known_data_types
        if parsed_data_type not in self.known_data_types:
            raise ResultsColumnNotFoundError(
                f"Data type '{parsed_data_type}' not found in data. Did you mean one of {self.known_data_types}?"
            )
        return [parsed_data_type]

    def _fetch_data(self, to_fetch: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        Fetch the actual data for the specified columns.
        
        This method retrieves values for each data type and key combination
        and structures the results for conversion to a Dataset.
        
        Args:
            to_fetch: Dictionary mapping data types to lists of keys to fetch
            
        Returns:
            List of dictionaries containing the fetched data
            
        Examples:
            >>> fetch_mock = lambda dt, k: [f"{dt}-{k}-val1", f"{dt}-{k}-val2"]
            >>> s = Selector(
            ...     ["answer"],
            ...     {"answer": ["q1"]},
            ...     {},
            ...     fetch_mock,
            ...     []
            ... )
            >>> s.items_in_order = ["answer.q1"]
            >>> data = s._fetch_data({"answer": ["q1"]})
            >>> data[0]["answer.q1"]
            ['answer-q1-val1', 'answer-q1-val2']
        """
        new_data = []
        for data_type, keys in to_fetch.items():
            for key in keys:
                entries = self._fetch_list(data_type, key)
                new_data.append({f"{data_type}.{key}": entries})

        # Ensure items are returned in the order they were requested
        return [d for key in self.items_in_order for d in new_data if key in d]


if __name__ == "__main__":
    import doctest

    doctest.testmod()
