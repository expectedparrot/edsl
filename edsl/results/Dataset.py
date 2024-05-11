"""A module to represent a dataset of observations."""
from __future__ import annotations
import random
from collections import UserList
from typing import Any

import numpy as np

from edsl.results.ResultsExportMixin import ResultsExportMixin

class Dataset(UserList, ResultsExportMixin):
    """A class to represent a dataset of observations."""

    def __init__(self, data: list[dict[str, Any]] = None):
        """Initialize the dataset with the given data."""
        super().__init__(data)


    def __len__(self) -> int:
        """Return the number of observations in the dataset.
        
        Need to override the __len__ method to return the number of observations in the dataset because 
        otherwise, the UserList class would return the number of dictionaries in the dataset.
        """
        #breakpoint()
        _, values = list(self.data[0].items())[0]
        return len(values)

    def relevant_columns(self, remove_prefix=False) -> set:
        """Return the set of keys that are present in the dataset."""
        columns = set([list(result.keys())[0] for result in self.data])
        if remove_prefix:
            columns = set([column.split(".")[-1] for column in columns])
        return columns

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

    def shuffle(self, seed = None) -> Dataset:
        if seed is not None:
           random.seed(seed)
    
        indices = None

        for entry in self:
            key, values = list(entry.items())[0]
            if indices is None:
                indices = list(range(len(values)))
                random.shuffle(indices)
            entry[key] = [values[i] for i in indices]

        return self
    
    def sample(self, n:int = None, frac:float = None, with_replacement:bool = True, seed = None) -> 'Dataset':
        if seed is not None:
            random.seed(seed)
        
        # Validate the input for sampling parameters
        if n is None and frac is None:
            raise ValueError("Either 'n' or 'frac' must be provided for sampling.")
        if n is not None and frac is not None:
            raise ValueError("Only one of 'n' or 'frac' should be specified.")
        
        # Get the length of the lists from the first entry
        first_key, first_values = list(self[0].items())[0]
        total_length = len(first_values)
        
        # Determine the number of samples based on 'n' or 'frac'
        if n is None:
            n = int(total_length * frac)
        
        if not with_replacement and n > total_length:
            raise ValueError("Sample size cannot be greater than the number of available elements when sampling without replacement.")
        
        # Sample indices based on the method chosen
        if with_replacement:
            indices = [random.randint(0, total_length - 1) for _ in range(n)]
        else:
            indices = random.sample(range(total_length), k=n)
        
        # Apply the same indices to all entries
        for entry in self:
            key, values = list(entry.items())[0]
            entry[key] = [values[i] for i in indices]

        return self

    

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
