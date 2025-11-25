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
        survey: Optional[Any] = None,
    ):
        """
        Initialize a Selector object.

        Args:
            known_data_types: List of valid data types (e.g., "answer", "agent", "model")
            data_type_to_keys: Mapping from data types to lists of keys available in that type
            key_to_data_type: Mapping from keys to their corresponding data types
            fetch_list_func: Function that retrieves values for a given data type and key
            columns: List of available column names in dot notation
            survey: Optional survey object to determine question order for answer columns

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
        self.survey = survey
        self.items_in_order = []  # Tracks column order for consistent output

    @classmethod
    def from_cache_manager(cls, cache_manager) -> "Selector":
        """
        Create a Selector from a DataTypeCacheManager (simplified constructor).

        This is the preferred way to create a Selector as it reduces the number of
        parameters needed and ensures consistency by getting all required data
        from the cache manager.

        Args:
            cache_manager: A DataTypeCacheManager instance that provides access to
                          all the data and metadata needed by the Selector

        Returns:
            Selector: A new Selector instance configured with data from the cache manager

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> selector = Selector.from_cache_manager(r._cache_manager)
            >>> isinstance(selector, Selector)
            True
        """
        return cls(
            known_data_types=cache_manager.results.known_data_types,
            data_type_to_keys=cache_manager.data_type_to_keys,
            key_to_data_type=cache_manager.key_to_data_type,
            fetch_list_func=cache_manager.fetch_list,
            columns=cache_manager.columns,
            survey=cache_manager.results.survey,
        )

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
                # Single match - process normally
                matched_column = matches[0]
                data_type, key = self._parse_column(matched_column)
                self._process_column(data_type, key, to_fetch)
            elif len(matches) > 1:
                # Multiple matches from wildcard - process each one
                for matched_column in matches:
                    data_type, key = self._parse_column(matched_column)
                    self._process_column(data_type, key, to_fetch)
            else:
                # No matches but validation passed - this handles wildcard patterns like ".*"
                data_type, key = self._parse_column(column)
                self._process_column(data_type, key, to_fetch)

        return to_fetch

    def _find_matching_columns(self, partial_name: str) -> List[str]:
        """
        Find columns that match a partial column name or wildcard pattern.

        This method supports both fully qualified column names with data types
        (containing a dot) and simple column names, handling each case appropriately.
        It supports wildcard patterns using '*' that can match any substring.

        Args:
            partial_name: A full or partial column name to match, potentially with wildcards

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
            >>> s._find_matching_columns("answer.*")
            ['answer.q1', 'answer.q2']
        """
        if "." in partial_name:
            search_in_list = self.columns
        else:
            search_in_list = [s.split(".")[1] for s in self.columns]

        # Handle wildcard patterns
        if "*" in partial_name:
            matches = self._match_wildcard_pattern(partial_name, search_in_list)
        else:
            matches = [s for s in search_in_list if s.startswith(partial_name)]

        return [partial_name] if partial_name in matches else matches

    def _match_wildcard_pattern(self, pattern: str, candidates: List[str]) -> List[str]:
        """
        Match a wildcard pattern against a list of candidate strings.

        This method supports patterns with '*' wildcards that can match any substring.
        It handles patterns like:
        - "prefix*" (match anything starting with prefix)
        - "*suffix" (match anything ending with suffix)
        - "prefix*suffix" (match anything starting with prefix and ending with suffix)
        - "data_type.*suffix" (for qualified names with wildcards)

        Args:
            pattern: The pattern string containing wildcards (*)
            candidates: List of strings to match against

        Returns:
            List of strings that match the pattern

        Examples:
            >>> s = Selector([], {}, {}, lambda dt, k: [], [])
            >>> candidates = ["answer.q1_cost", "answer.q2_cost", "answer.q1_tokens", "agent.name"]
            >>> s._match_wildcard_pattern("answer.*_cost", candidates)
            ['answer.q1_cost', 'answer.q2_cost']
            >>> s._match_wildcard_pattern("*_cost", ["q1_cost", "q2_cost", "q1_tokens"])
            ['q1_cost', 'q2_cost']
        """
        import re

        # Convert wildcard pattern to regex pattern
        # Escape special regex characters except *
        regex_pattern = re.escape(pattern)
        # Replace escaped \* with .* to match any characters
        regex_pattern = regex_pattern.replace(r'\*', '.*')
        # Ensure full match from start to end
        regex_pattern = f'^{regex_pattern}$'

        compiled_pattern = re.compile(regex_pattern)

        matches = [candidate for candidate in candidates if compiled_pattern.match(candidate)]
        return matches

    def _validate_matches(self, column: str, matches: List[str]) -> None:
        """
        Validate that matched columns are unambiguous and exist.

        This method checks that the column specification resolves to exactly
        one column or a wildcard pattern. It raises appropriate exceptions
        for ambiguous matches or when no matches are found.

        For wildcard patterns (containing '*'), multiple matches are allowed and expected.

        Args:
            column: The original column specification
            matches: List of matching column names

        Raises:
            ResultsColumnNotFoundError: If matches are ambiguous or no matches found

        Examples:
            >>> s = Selector([], {}, {}, lambda dt, k: [], [])
            >>> s._validate_matches("col", ["col"])  # No exception
            >>> s._validate_matches("*_cost", ["col1_cost", "col2_cost"])  # No exception - wildcard
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
        # Allow multiple matches for wildcard patterns
        if len(matches) > 1 and "*" not in column:
            raise ResultsColumnNotFoundError(
                f"Column '{column}' is ambiguous. Did you mean one of {matches}?"
            )
        if len(matches) == 0 and ".*" not in column and "*" not in column:
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

    def _process_column(
        self, data_type: str, key: str, to_fetch: Dict[str, List[str]]
    ) -> None:
        """
        Process a parsed column and add it to the list of data to fetch.

        This method handles wildcards in both data types and keys, expands them
        appropriately, and tracks the order of items for consistent output.
        For answer columns, it orders them according to the survey question order.

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

            # For answer columns with wildcard, order by survey question order
            if (
                dt == "answer"
                and key == "*"
                and self.survey
                and hasattr(self.survey, "questions")
            ):
                # Get question names in survey order
                survey_question_names = [
                    q.question_name
                    for q in self.survey.questions
                    if hasattr(q, "question_name")
                ]

                # Order relevant keys by survey question order, then add any extras
                ordered_keys = []
                for question_name in survey_question_names:
                    if question_name in relevant_keys:
                        ordered_keys.append(question_name)

                # Add any remaining keys not in survey (e.g., created columns)
                for k in relevant_keys:
                    if k not in ordered_keys:
                        ordered_keys.append(k)

                # Use the ordered keys
                keys_to_process = ordered_keys
            else:
                # For non-answer columns or specific keys, use original order
                keys_to_process = relevant_keys

            for k in keys_to_process:
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
        # Check if we can use the optimized batch fetching (when _fetch_list is a bound method)
        if hasattr(self._fetch_list, "__self__"):
            # Optimized batch fetching: extract all needed data in one pass
            data_dict = {}

            # Check what's already cached and initialize result lists
            uncached_requests = []

            # Access Results instance through the bound method
            results_instance = self._fetch_list.__self__

            # If the bound method is from a DataTypeCacheManager, get the Results instance from it
            if hasattr(results_instance, "results"):
                results_instance = results_instance.results

            # Get the fetch list cache safely (handle test scenarios with mocks)
            fetch_list_cache = {}
            try:
                if hasattr(results_instance, "_cache_manager") and hasattr(
                    results_instance._cache_manager, "_fetch_list_cache"
                ):
                    cache_obj = results_instance._cache_manager._fetch_list_cache
                    # Verify it's dict-like by testing if we can use 'in' operator
                    if hasattr(cache_obj, "__contains__"):
                        fetch_list_cache = cache_obj
                elif hasattr(results_instance, "_fetch_list_cache"):
                    # Fallback for older code or test scenarios
                    cache_obj = results_instance._fetch_list_cache
                    # Verify it's dict-like by testing if we can use 'in' operator
                    if hasattr(cache_obj, "__contains__"):
                        fetch_list_cache = cache_obj
            except (AttributeError, TypeError):
                # If anything goes wrong, fall back to empty dict
                fetch_list_cache = {}

            for data_type, keys in to_fetch.items():
                for key in keys:
                    column_name = f"{data_type}.{key}"
                    cache_key = (data_type, key)

                    if cache_key in fetch_list_cache:
                        # Use cached data
                        data_dict[column_name] = fetch_list_cache[cache_key]
                    else:
                        # Mark for batch extraction
                        data_dict[column_name] = []
                        uncached_requests.append((data_type, key, column_name))

            # Batch extract all uncached data in a single pass through results
            if uncached_requests:
                try:
                    # Check if results_instance.data is iterable (handle mock objects in tests)
                    if hasattr(results_instance.data, "__iter__"):
                        for row in results_instance.data:
                            for data_type, key, column_name in uncached_requests:
                                value = row.sub_dicts[data_type].get(key, None)
                                data_dict[column_name].append(value)
                    else:
                        # Fallback: use direct fetch_list calls for each request
                        for data_type, key, column_name in uncached_requests:
                            data_dict[column_name] = self._fetch_list(data_type, key)
                except (TypeError, AttributeError):
                    # Fallback: use direct fetch_list calls for each request
                    for data_type, key, column_name in uncached_requests:
                        data_dict[column_name] = self._fetch_list(data_type, key)

                # Update cache for newly computed columns (if cache is available)
                if fetch_list_cache is not None:
                    for data_type, key, column_name in uncached_requests:
                        cache_key = (data_type, key)
                        fetch_list_cache[cache_key] = data_dict[column_name]

            return [
                {key: data_dict[key]} for key in self.items_in_order if key in data_dict
            ]
        else:
            # Fallback to original method for lambdas/functions without __self__
            data_dict = {}
            for data_type, keys in to_fetch.items():
                for key in keys:
                    column_name = f"{data_type}.{key}"
                    data_dict[column_name] = self._fetch_list(data_type, key)

            return [
                {key: data_dict[key]} for key in self.items_in_order if key in data_dict
            ]


if __name__ == "__main__":
    import doctest

    doctest.testmod()
