"""A module to represent a dataset of observations."""

from __future__ import annotations
import random
import json
from collections import UserList
from typing import Any, Union, Optional
import sys
import numpy as np

from edsl.results.ResultsExportMixin import ResultsExportMixin
from edsl.results.DatasetTree import Tree
from edsl.results.TableDisplay import TableDisplay

from edsl.Base import PersistenceMixin, HashingMixin


class Dataset(UserList, ResultsExportMixin, PersistenceMixin, HashingMixin):
    """A class to represent a dataset of observations."""

    def __init__(
        self, data: list[dict[str, Any]] = None, print_parameters: Optional[dict] = None
    ):
        """Initialize the dataset with the given data."""
        super().__init__(data)
        self.print_parameters = print_parameters

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

    def view(self):
        from perspective.widget import PerspectiveWidget

        w = PerspectiveWidget(
            self.to_pandas(),
            plugin="Datagrid",
            aggregates={"datetime": "any"},
            sort=[["date", "desc"]],
        )
        return w

    def keys(self) -> list[str]:
        """Return the keys of the first observation in the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.keys()
        ['a.b']
        """
        return [list(o.keys())[0] for o in self]

    def filter(self, expression):
        return self.to_scenario_list().filter(expression).to_dataset()

    def long(self, exclude_fields: list[str] = None) -> Dataset:
        headers, data = self._tabular()
        exclude_fields = exclude_fields or []

        # Initialize result dictionaries for each column
        result_dict = {}

        for index, row in enumerate(data):
            row_values = dict(zip(headers, row))
            excluded_values = {field: row_values[field] for field in exclude_fields}

            # Transform non-excluded fields to long format
            for header, value in row_values.items():
                if header not in exclude_fields:
                    # Initialize lists in result_dict if needed
                    if not result_dict:
                        result_dict = {
                            "row": [],
                            "key": [],
                            "value": [],
                            **{field: [] for field in exclude_fields},
                        }

                    # Add values to each column
                    result_dict["row"].append(index)
                    result_dict["key"].append(header)
                    result_dict["value"].append(value)
                    for field in exclude_fields:
                        result_dict[field].append(excluded_values[field])

        return Dataset([{k: v} for k, v in result_dict.items()])

    def wide(self) -> "Dataset":
        """
        Convert a long-format dataset (with row, key, value columns) to wide format.

        Expected input format:
        - A dataset with three columns containing dictionaries:
          - row: list of row indices
          - key: list of column names
          - value: list of values

        Returns:
        - Dataset: A new dataset with columns corresponding to unique keys
        """
        # Extract the component arrays
        row_dict = next(col for col in self if "row" in col)
        key_dict = next(col for col in self if "key" in col)
        value_dict = next(col for col in self if "value" in col)

        rows = row_dict["row"]
        keys = key_dict["key"]
        values = value_dict["value"]

        if not (len(rows) == len(keys) == len(values)):
            raise ValueError("All input arrays must have the same length")

        # Get unique keys and row indices
        unique_keys = sorted(set(keys))
        unique_rows = sorted(set(rows))

        # Create a dictionary to store the result
        result = {key: [None] * len(unique_rows) for key in unique_keys}

        # Populate the result dictionary
        for row_idx, key, value in zip(rows, keys, values):
            # Find the position in the output array for this row
            output_row_idx = unique_rows.index(row_idx)
            result[key][output_row_idx] = value

        # Convert to list of column dictionaries format
        return Dataset([{key: values} for key, values in result.items()])

    def __repr__(self) -> str:
        """Return a string representation of the dataset."""
        return f"Dataset({self.data})"

    def write(self, filename: str, tablefmt: Optional[str] = None) -> None:
        return self.table(tablefmt=tablefmt).write(filename)

    def _repr_html_(self):
        # headers, data = self._tabular()
        return self.table(print_parameters=self.print_parameters)._repr_html_()
        # return TableDisplay(headers=headers, data=data, raw_data_set=self)

    def _tabular(self) -> tuple[list[str], list[list[Any]]]:
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

    def remove_prefix(self) -> Dataset:
        new_data = []
        for observation in self.data:
            key, values = list(observation.items())[0]
            if "." in key:
                new_key = key.split(".")[1]
                new_data.append({new_key: values})
            else:
                new_data.append({key: values})
        return Dataset(new_data)

    def print(self, pretty_labels=None, **kwargs):
        if "format" in kwargs:
            if kwargs["format"] not in ["html", "markdown", "rich", "latex"]:
                raise ValueError(f"Format '{kwargs['format']}' not supported.")
        if pretty_labels is None:
            pretty_labels = {}
        else:
            return self.rename(pretty_labels).print(**kwargs)
        return self.table()

    def rename(self, rename_dic) -> Dataset:
        new_data = []
        for observation in self.data:
            key, values = list(observation.items())[0]
            new_key = rename_dic.get(key, key)
            new_data.append({new_key: values})
        return Dataset(new_data)

    def merge(self, other: Dataset, by_x, by_y) -> Dataset:
        """Merge the dataset with another dataset on the given keys.""

        merged_df = df1.merge(df2, how="left", on=["key1", "key2"])
        """
        df1 = self.to_pandas()
        df2 = other.to_pandas()
        merged_df = df1.merge(df2, how="left", left_on=by_x, right_on=by_y)
        return Dataset.from_pandas_dataframe(merged_df)

    def to(self, survey_or_question: Union["Survey", "QuestionBase"]) -> "Jobs":
        from edsl.surveys.Survey import Survey
        from edsl.questions.QuestionBase import QuestionBase

        if isinstance(survey_or_question, Survey):
            return survey_or_question.by(self.to_scenario_list())
        elif isinstance(survey_or_question, QuestionBase):
            return Survey([survey_or_question]).by(self.to_scenario_list())

    def select(self, *keys) -> Dataset:
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

    def expand(self, field):
        return self.to_scenario_list().expand(field).to_dataset()

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

    def tree(self, node_order: Optional[list[str]] = None) -> Tree:
        """Return a tree representation of the dataset.

        >>> d = Dataset([{'a':[1,2,3,4]}, {'b':[4,3,2,1]}])
        >>> d.tree()
        Tree(Dataset({'a': [1, 2, 3, 4], 'b': [4, 3, 2, 1]}))
        """
        return Tree(self, node_order=node_order)

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        max_rows: Optional[int] = None,
        pretty_labels=None,
        print_parameters: Optional[dict] = None,
    ):
        if pretty_labels is not None:
            new_fields = []
            for field in fields:
                new_fields.append(pretty_labels.get(field, field))
            return self.rename(pretty_labels).table(
                *new_fields, tablefmt=tablefmt, max_rows=max_rows
            )

        self.print_parameters = print_parameters

        headers, data = self._tabular()

        if tablefmt is not None:
            from tabulate import tabulate_formats

            if tablefmt not in tabulate_formats:
                print(
                    f"Error: The following table format is not supported: {tablefmt}",
                    file=sys.stderr,
                )
                print(f"\nAvailable formats are: {tabulate_formats}", file=sys.stderr)
                return None

        if max_rows:
            if len(data) < max_rows:
                max_rows = None

        if fields:
            full_data = data
            data = []
            indices = []
            for field in fields:
                if field not in headers:
                    print(
                        f"Error: The following field was not found: {field}",
                        file=sys.stderr,
                    )
                    print(f"\nAvailable fields are: {headers}", file=sys.stderr)

                    # Optional: Suggest similar fields using difflib
                    import difflib

                    matches = difflib.get_close_matches(field, headers)
                    if matches:
                        print(f"\nDid you mean: {matches[0]} ?", file=sys.stderr)
                    return None
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
            data = data[:max_rows]
            data.append(filler_line)
            data.append(last_line)

        return TableDisplay(
            data=data, headers=headers, tablefmt=tablefmt, raw_data_set=self
        )

    def summary(self):
        return Dataset([{"num_observations": [len(self)], "keys": [self.keys()]}])

    @classmethod
    def example(self, n: int = None):
        """Return an example dataset.

        >>> Dataset.example()
        Dataset([{'a': [1, 2, 3, 4]}, {'b': [4, 3, 2, 1]}])
        """
        if n is None:
            return Dataset([{"a": [1, 2, 3, 4]}, {"b": [4, 3, 2, 1]}])
        else:
            return Dataset([{"a": [1] * n}, {"b": [2] * n}])

    @classmethod
    def from_edsl_object(cls, object):
        d = object.to_dict(add_edsl_version=False)
        return cls([{"key": list(d.keys())}, {"value": list(d.values())}])

    @classmethod
    def from_pandas_dataframe(cls, df):
        result = cls([{col: df[col].tolist()} for col in df.columns])
        return result


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
