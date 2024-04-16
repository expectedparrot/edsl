"""A module to represent a dataset of observations."""
from __future__ import annotations
import numpy as np
from collections import UserList
from typing import Any
from edsl.results.ResultsExportMixin import ResultsExportMixin


class Dataset(UserList, ResultsExportMixin):
    """A class to represent a dataset of observations."""

    def __init__(self, data: list[dict[str, Any]] = None):
        """Initialize the dataset with the given data."""
        super().__init__(data)

    def relevant_columns(self) -> set:
        """Return the set of keys that are present in the dataset."""
        return set([list(result.keys())[0] for result in self.data])

    def _key_to_value(self, key: str) -> Any:
        """Retrieve the value associated with the given key from the dataset."""
        for d in self.data:
            if key in d:
                return d[key]
        else:
            raise KeyError(f"Key '{key}' not found in any of the dictionaries.")

    def first(self) -> dict[str, Any]:
        """Get the first value of the first key in the first dictionary."""

        def get_values(d):
            """Get the values of the first key in the dictionary."""
            return list(d.values())[0]

        return get_values(self.data[0])[0]

    def _repr_html_(self) -> str:
        """Return an HTML representation of the dataset."""
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.data)

    def order_by(self, sort_key: str, reverse: bool = False) -> Dataset:
        """Return a new dataset with the observations sorted by the given key."""

        def sort_indices(lst: list[Any]) -> list[int]:
            """
            Return the indices that would sort the list.

            :param lst: The list to be sorted.
            :return: A list of indices that would sort the list.
            """
            indices = np.argsort(lst).tolist()
            if reverse:
                indices.reverse()
            return indices

        if not any(sort_key in d for d in self.data):
            raise ValueError(f"Key '{sort_key}' not found in any of the dictionaries.")

        relevant_values = self._key_to_value(sort_key)
        sort_indices_list = sort_indices(relevant_values)
        new_data = []
        for observation in self.data:
            print(observation)
            key, values = list(observation.items())[0]
            new_values = [values[i] for i in sort_indices_list]
            new_data.append({key: new_values})

        return Dataset(new_data)
