"""Data type and column caching functionality for Results objects."""

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .results import Results


class DataTypeCacheManager:
    """Manages caching of expensive data type and column operations for Results objects.

    This class handles the caching of key-to-data-type mappings, data-type-to-keys mappings,
    column lists, and fetch operations to avoid expensive recomputation when the underlying
    data hasn't changed.

    Attributes:
        results: The Results object this cache manager is associated with
        _key_to_data_type_cache: Cached mapping of keys to data types
        _data_type_to_keys_cache: Cached mapping of data types to keys
        _columns_cache: Cached list of column names
        _fetch_list_cache: Cached results of fetch_list operations
        _cache_dirty: Flag indicating if caches need to be regenerated
    """

    def __init__(self, results: "Results"):
        """Initialize the cache manager for a Results object.

        Args:
            results: The Results object to manage caches for
        """
        self.results = results
        self._key_to_data_type_cache = None
        self._data_type_to_keys_cache = None
        self._columns_cache = None
        self._fetch_list_cache = {}
        self._cache_dirty = True

    def invalidate_cache(self) -> None:
        """Invalidate all cached expensive operations when data changes."""
        self._key_to_data_type_cache = None
        self._data_type_to_keys_cache = None
        self._columns_cache = None
        self._fetch_list_cache = {}
        self._cache_dirty = True

    @property
    def key_to_data_type(self) -> dict[str, str]:
        """Return a mapping of keys to data types.

        Objects such as Agent, Answer, Model, Scenario, etc.
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`

        Returns:
            dict[str, str]: Mapping of keys (how_feeling, status, etc.) to data types
        """
        if self._key_to_data_type_cache is None or self._cache_dirty:
            d: dict = {}
            for result in self.results.data:
                d.update(result.key_to_data_type)
            for column in self.results.created_columns:
                d[column] = "answer"
            self._key_to_data_type_cache = d
            self._cache_dirty = False

        return self._key_to_data_type_cache

    @property
    def data_type_to_keys(self) -> dict[str, str]:
        """Return a mapping of data types to keys.

        Return mapping of data types (Agent, Answer, Model, Scenario, etc.) to
        keys (how_feeling, status, etc.)
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`

        Returns:
            dict[str, str]: Mapping of data types to sets of keys
        """
        if self._data_type_to_keys_cache is None or self._cache_dirty:
            d: dict = defaultdict(set)
            for result in self.results.data:
                for key, value in result.key_to_data_type.items():
                    d[value].add(key)
            for column in self.results.created_columns:
                d["answer"].add(column)
            self._data_type_to_keys_cache = d

        return self._data_type_to_keys_cache

    @property
    def columns(self) -> list[str]:
        """Return a cached list of all columns in the Results.

        Returns:
            list[str]: Sorted list of all column names in "data_type.key" format
        """
        if self._columns_cache is None or self._cache_dirty:
            column_names = [f"{v}.{k}" for k, v in self.key_to_data_type.items()]
            from ..utilities.PrettyList import PrettyList

            self._columns_cache = PrettyList(sorted(column_names))

        return self._columns_cache

    def fetch_list(self, data_type: str, key: str) -> list:
        """Return a cached list of values from the data for a given data type and key.

        Uses the filtered data, not the original data.

        Args:
            data_type: The type of data to fetch (e.g., 'answer', 'agent', 'scenario').
            key: The key to fetch from each data type dictionary.

        Returns:
            list: A list of values, one from each result in the data.
        """
        cache_key = (data_type, key)
        if cache_key not in self._fetch_list_cache:
            returned_list = []
            for row in self.results.data:
                returned_list.append(row.sub_dicts[data_type].get(key, None))
            self._fetch_list_cache[cache_key] = returned_list

        return self._fetch_list_cache[cache_key]
