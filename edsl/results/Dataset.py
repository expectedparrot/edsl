from collections import UserList
import numpy as np

from edsl.results.ResultsExportMixin import ResultsExportMixin


class Dataset(UserList, ResultsExportMixin):
    def __init__(self, data=None):
        super().__init__(data)

    def relevant_columns(self) -> set:
        return set([list(result.keys())[0] for result in self.data])

    def _key_to_value(self, key):
        for d in self.data:
            if key in d:
                return d[key]
        else:
            raise KeyError(f"Key '{key}' not found in any of the dictionaries.")

    def first(self):
        "Gets the first value of the first key in the first dictionary."

        def get_values(d):
            return list(d.values())[0]

        return get_values(self.data[0])[0]

    def order_by(self, sort_key, reverse=False):
        def sort_indices(lst):
            """
            Returns the indices that would sort the list.

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
