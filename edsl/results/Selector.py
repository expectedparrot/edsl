from typing import Union, List, Dict, Any
from collections import defaultdict
from edsl.results.Dataset import Dataset


class Selector:
    def __init__(
        self,
        known_data_types: List[str],
        data_type_to_keys: Dict[str, List[str]],
        key_to_data_type: Dict[str, str],
        fetch_list_func,
        columns: List[str],
    ):
        """Selects columns from a Results object"""
        self.known_data_types = known_data_types
        self._data_type_to_keys = data_type_to_keys
        self._key_to_data_type = key_to_data_type
        self._fetch_list = fetch_list_func
        self.columns = columns

    def select(self, *columns: Union[str, List[str]]) -> "Dataset":
        columns = self._normalize_columns(columns)
        to_fetch = self._get_columns_to_fetch(columns)
        # breakpoint()
        new_data = self._fetch_data(to_fetch)
        return Dataset(new_data)

    def _normalize_columns(self, columns: Union[str, List[str]]) -> tuple:
        """Normalize the columns to a tuple of strings

        >>> s = Selector([], {}, {}, lambda x, y: x, [])
        >>> s._normalize_columns([["a", "b"], ])
        ('a', 'b')
        >>> s._normalize_columns(None)
        ('*.*',)
        """
        if not columns or columns == ("*",) or columns == (None,):
            return ("*.*",)
        if isinstance(columns[0], list):
            return tuple(columns[0])
        return columns

    def _get_columns_to_fetch(self, columns: tuple) -> Dict[str, List[str]]:
        to_fetch = defaultdict(list)
        self.items_in_order = []

        for column in columns:
            matches = self._find_matching_columns(column)
            # breakpoint()
            self._validate_matches(column, matches)

            if len(matches) == 1:
                column = matches[0]

            data_type, key = self._parse_column(column)
            self._process_column(data_type, key, to_fetch)

        return to_fetch

    def _find_matching_columns(self, partial_name: str) -> list[str]:
        if "." in partial_name:
            search_in_list = self.columns
        else:
            search_in_list = [s.split(".")[1] for s in self.columns]
        # breakpoint()
        matches = [s for s in search_in_list if s.startswith(partial_name)]
        return [partial_name] if partial_name in matches else matches

    def _validate_matches(self, column: str, matches: List[str]):
        if len(matches) > 1:
            raise ValueError(
                f"Column '{column}' is ambiguous. Did you mean one of {matches}?"
            )
        if len(matches) == 0 and ".*" not in column:
            raise ValueError(f"Column '{column}' not found in data.")

    def _parse_column(self, column: str) -> tuple[str, str]:
        if "." in column:
            return column.split(".")
        try:
            return self._key_to_data_type[column], column
        except KeyError:
            self._raise_key_error(column)

    def _raise_key_error(self, column: str):
        import difflib

        close_matches = difflib.get_close_matches(column, self._key_to_data_type.keys())
        if close_matches:
            suggestions = ", ".join(close_matches)
            raise KeyError(
                f"Column '{column}' not found in data. Did you mean: {suggestions}?"
            )
        else:
            raise KeyError(f"Column {column} not found in data")

    def _process_column(self, data_type: str, key: str, to_fetch: Dict[str, List[str]]):
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
            raise ValueError(f"Key {key} not found in data.")

    def _get_data_types_to_return(self, parsed_data_type: str) -> List[str]:
        if parsed_data_type == "*":
            return self.known_data_types
        if parsed_data_type not in self.known_data_types:
            raise ValueError(
                f"Data type {parsed_data_type} not found in data. Did you mean one of {self.known_data_types}"
            )
        return [parsed_data_type]

    def _fetch_data(self, to_fetch: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        new_data = []
        for data_type, keys in to_fetch.items():
            for key in keys:
                entries = self._fetch_list(data_type, key)
                new_data.append({f"{data_type}.{key}": entries})

        return [d for key in self.items_in_order for d in new_data if key in d]


if __name__ == "__main__":
    import doctest

    doctest.testmod()
