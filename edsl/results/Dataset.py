"""A module to represent a dataset of observations."""

from __future__ import annotations
import random
import json
from collections import UserList
from typing import Any, Union, Optional

import numpy as np

from edsl.results.ResultsExportMixin import ResultsExportMixin
from edsl.results.DatasetTree import Tree


class TableDisplay:
    max_height = 400

    html_template = """
    <div style="
        height: {height}px;
        max-width: 100%%;
        overflow: auto;
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 4px;
        margin-left: 0; 
    ">
        <style>
            .scroll-table {{
                border-collapse: collapse;
                width: auto;
                white-space: nowrap;
            }}
            .scroll-table th, .scroll-table td {{
                padding: 8px;
                text-align: left !important;
                border-bottom: 1px solid #ddd;
                min-width: 100px;  /* Minimum column width */
                max-width: 300px;  /* Maximum column width */
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .scroll-table th {{
                background-color: #f5f5f5;
                position: sticky;
                top: 0;
                z-index: 1;
            }}
            .scroll-table tr:hover {{
                background-color: #f5f5f5;
            }}
            /* Add horizontal scrollbar styles */
            .scroll-table-wrapper {{
                overflow-x: auto;
                margin-bottom: 10px;
            }}
            /* Optional: Style scrollbars for webkit browsers */
            .scroll-table-wrapper::-webkit-scrollbar {{
                height: 8px;
            }}
            .scroll-table-wrapper::-webkit-scrollbar-track {{
                background: #f1f1f1;
            }}
            .scroll-table-wrapper::-webkit-scrollbar-thumb {{
                background: #888;
                border-radius: 4px;
            }}
            .scroll-table-wrapper::-webkit-scrollbar-thumb:hover {{
                background: #555;
            }}
        </style>
        <div class="scroll-table-wrapper">
            {table}
        </div>
    </div>
    """

    def __init__(self, headers, data, tablefmt="simple", raw_data_set=None):
        self.headers = headers
        self.data = data
        self.tablefmt = tablefmt
        self.raw_data_set = raw_data_set

    def to_csv(self, filename: str):
        self.raw_data_set.to_csv(filename)

    def __repr__(self):
        from tabulate import tabulate

        return tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

    def _repr_html_(self):
        from tabulate import tabulate

        num_rows = len(self.data)
        height = min(
            num_rows * 30 + 50, self.max_height
        )  # Added extra space for header

        # Generate HTML table with the scroll-table class
        html_content = tabulate(self.data, headers=self.headers, tablefmt="html")
        html_content = html_content.replace("<table>", '<table class="scroll-table">')

        return self.html_template.format(table=html_content, height=height)


class DisplayTable:

    def __init__(self, table_string: str):
        self.table_string = table_string

    def __repr__(self):
        return self.table_string


class Dataset(UserList, ResultsExportMixin):
    """A class to represent a dataset of observations."""

    def __init__(self, data: list[dict[str, Any]] = None):
        """Initialize the dataset with the given data."""
        super().__init__(data)

    def __len__(self) -> int:
        """Return the number of observations in the dataset.

        Need to override the __len__ method to return the number of observations in the dataset because
        otherwise, the UserList class would return the number of dictionaries in the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> len(d)
        4
        """
        _, values = list(self.data[0].items())[0]
        return len(values)

    def keys(self):
        """Return the keys of the first observation in the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.keys()
        ['a.b']
        """
        return [list(o.keys())[0] for o in self]

    def __repr__(self) -> str:
        """Return a string representation of the dataset."""
        return f"Dataset({self.data})"

    def _tabular(self):
        # Extract headers
        headers = []
        for entry in self.data:
            headers.extend(entry.keys())
        headers = list(dict.fromkeys(headers))  # Ensure unique headers

        # Extract data
        max_len = max(len(values) for entry in self.data for values in entry.values())
        rows = []
        for i in range(max_len):
            row = []
            for header in headers:
                for entry in self.data:
                    if header in entry:
                        values = entry[header]
                        row.append(values[i] if i < len(values) else None)
                        break
                else:
                    row.append(None)  # Default to None if header is missing
            rows.append(row)

        return headers, rows

    def _key_to_value(self, key: str) -> Any:
        """Retrieve the value associated with the given key from the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d._key_to_value('a.b')
        [1, 2, 3, 4]

        >>> d._key_to_value('a')
        Traceback (most recent call last):
        ...
        KeyError: "Key 'a' not found in any of the dictionaries."

        """
        potential_matches = []
        for data_dict in self.data:
            data_key, data_values = list(data_dict.items())[0]
            if key == data_key:
                return data_values
            if key == data_key.split(".")[-1]:
                potential_matches.append((data_key, data_values))

        if len(potential_matches) == 1:
            return potential_matches[0][1]
        elif len(potential_matches) > 1:
            raise KeyError(
                f"Key '{key}' found in more than one location: {[m[0] for m in potential_matches]}"
            )

        raise KeyError(f"Key '{key}' not found in any of the dictionaries.")

    def first(self) -> dict[str, Any]:
        """Get the first value of the first key in the first dictionary.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.first()
        1
        """

        def get_values(d):
            """Get the values of the first key in the dictionary."""
            return list(d.values())[0]

        return get_values(self.data[0])[0]

    def select(self, *keys):
        """Return a new dataset with only the selected keys.

        :param keys: The keys to select.

        >>> d = Dataset([{'a.b':[1,2,3,4]}, {'c.d':[5,6,7,8]}])
        >>> d.select('a.b')
        Dataset([{'a.b': [1, 2, 3, 4]}])

        >>> d.select('a.b', 'c.d')
        Dataset([{'a.b': [1, 2, 3, 4]}, {'c.d': [5, 6, 7, 8]}])
        """
        if isinstance(keys, str):
            keys = [keys]

        new_data = []
        for observation in self.data:
            observation_key = list(observation.keys())[0]
            if observation_key in keys:
                new_data.append(observation)
        return Dataset(new_data)

    def to_json(self):
        """Return a JSON representation of the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.to_json()
        [{'a.b': [1, 2, 3, 4]}]
        """
        return json.loads(
            json.dumps(self.data)
        )  # janky but I want to make sure it's serializable & deserializable

    def _repr_html_(self) -> str:
        """Return an HTML representation of the dataset."""
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.data)

    def shuffle(self, seed=None) -> Dataset:
        """Return a new dataset with the observations shuffled.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.shuffle(seed=0)
        Dataset([{'a.b': [3, 1, 2, 4]}])
        """
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

    def sample(
        self,
        n: int = None,
        frac: float = None,
        with_replacement: bool = True,
        seed: Union[str, int, float] = None,
    ) -> Dataset:
        """Return a new dataset with a sample of the observations.

        :param n: The number of samples to take.
        :param frac: The fraction of samples to take.
        :param with_replacement: Whether to sample with replacement.
        :param seed: The seed for the random number generator.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.sample(n=2, seed=0, with_replacement=True)
        Dataset([{'a.b': [4, 4]}])

        >>> d.sample(n = 10, seed=0, with_replacement=False)
        Traceback (most recent call last):
        ...
        ValueError: Sample size cannot be greater than the number of available elements when sampling without replacement.
        """
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
            raise ValueError(
                "Sample size cannot be greater than the number of available elements when sampling without replacement."
            )

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
        """Return a new dataset with the observations sorted by the given key.

        :param sort_key: The key to sort the observations by.
        :param reverse: Whether to sort in reverse order.

        >>> d = Dataset([{'a':[1,2,3,4]}, {'b':[4,3,2,1]}])
        >>> d.order_by('a')
        Dataset([{'a': [1, 2, 3, 4]}, {'b': [4, 3, 2, 1]}])

        >>> d.order_by('a', reverse=True)
        Dataset([{'a': [4, 3, 2, 1]}, {'b': [1, 2, 3, 4]}])

        >>> d = Dataset([{'X.a':[1,2,3,4]}, {'X.b':[4,3,2,1]}])
        >>> d.order_by('a')
        Dataset([{'X.a': [1, 2, 3, 4]}, {'X.b': [4, 3, 2, 1]}])


        """

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

        number_found = 0
        for obs in self.data:
            key, values = list(obs.items())[0]
            # an obseration is {'a':[1,2,3,4]}
            # key = list(obs.keys())[0]
            if (
                sort_key == key or sort_key == key.split(".")[-1]
            ):  # e.g., "age" in "scenario.age"
                relevant_values = values
                number_found += 1

        if number_found == 0:
            raise ValueError(f"Key '{sort_key}' not found in any of the dictionaries.")
        elif number_found > 1:
            raise ValueError(f"Key '{sort_key}' found in more than one dictionary.")

        # relevant_values = self._key_to_value(sort_key)
        sort_indices_list = sort_indices(relevant_values)
        new_data = []
        for observation in self.data:
            # print(observation)
            key, values = list(observation.items())[0]
            new_values = [values[i] for i in sort_indices_list]
            new_data.append({key: new_values})

        return Dataset(new_data)

    @property
    def tree(self):
        """Return a tree representation of the dataset.

        >>> d = Dataset([{'a':[1,2,3,4]}, {'b':[4,3,2,1]}])
        >>> d.tree.print_tree()
        Tree has not been constructed yet.
        """
        return Tree(self)

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = "simple",
        max_rows: Optional[int] = None,
    ):
        # from tabulate import tabulate

        headers, data = self._tabular()

        if max_rows:
            if len(data) < max_rows:
                max_rows = None

        if fields:
            full_data = data
            data = []
            indices = []
            for field in fields:
                indices.append(headers.index(field))
            headers = fields
            for row in full_data:
                data.append([row[i] for i in indices])

        if max_rows is not None:
            if max_rows > len(data):
                raise ValueError(
                    "max_rows cannot be greater than the number of rows in the dataset."
                )
            last_line = data[-1]
            spaces = len(data[max_rows])
            filler_line = ["." for i in range(spaces)]
            # breakpoint()
            data = data[:max_rows]
            data.append(filler_line)
            data.append(last_line)

        return TableDisplay(
            data=data, headers=headers, tablefmt=tablefmt, raw_data_set=self
        )

    def summary(self):
        return Dataset([{"num_observations": [len(self)], "keys": [self.keys()]}])

    @classmethod
    def example(self):
        """Return an example dataset.

        >>> Dataset.example()
        Dataset([{'a': [1, 2, 3, 4]}, {'b': [4, 3, 2, 1]}])
        """
        return Dataset([{"a": [1, 2, 3, 4]}, {"b": [4, 3, 2, 1]}])


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
