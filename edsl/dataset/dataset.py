from __future__ import annotations
import sys
import json
import random
from collections import UserList
from typing import Any, Union, Optional, TYPE_CHECKING, Callable

from ..base import PersistenceMixin, HashingMixin

from .dataset_tree import Tree
from .exceptions import DatasetKeyError, DatasetValueError, DatasetTypeError


from .display.table_display import TableDisplay
#from .smart_objects import FirstObject
from .dataset_operations_mixin import DatasetOperationsMixin

if TYPE_CHECKING:
    from ..surveys import Survey
    from ..questions import QuestionBase
    from ..jobs import Job  # noqa: F401


class Dataset(UserList, DatasetOperationsMixin, PersistenceMixin, HashingMixin):
    """
    A versatile data container for tabular data with powerful manipulation capabilities.
    
    The Dataset class is a fundamental data structure in EDSL that represents tabular data
    in a column-oriented format. It provides a rich set of methods for data manipulation,
    transformation, analysis, visualization, and export through the DatasetOperationsMixin.
    
    Key features:
    
    1. Column-oriented data structure optimized for LLM experiment results
    2. Rich data manipulation API similar to dplyr/pandas (filter, select, mutate, etc.)
    3. Visualization capabilities including tables, plots, and reports
    4. Export to various formats (CSV, Excel, SQLite, pandas, etc.)
    5. Serialization for storage and transport
    6. Tree-based data exploration
    
    A Dataset typically contains multiple columns, each represented as a dictionary
    with a single key-value pair. The key is the column name and the value is a list
    of values for that column. All columns must have the same length.
    
    The Dataset class inherits from:
    - UserList: Provides list-like behavior for storing column data
    - DatasetOperationsMixin: Provides data manipulation methods
    - PersistenceMixin: Provides serialization capabilities
    - HashingMixin: Provides hashing functionality for comparison and storage
    
    Datasets are typically created by transforming other EDSL container types like
    Results, AgentList, or ScenarioList, but can also be created directly from data.
    """

    def __init__(
        self, data: list[dict[str, Any]] = None, print_parameters: Optional[dict] = None
    ):
        """
        Initialize a new Dataset instance.
        
        Parameters:
            data: A list of dictionaries, where each dictionary represents a column
                 in the dataset. Each dictionary should have a single key-value pair,
                 where the key is the column name and the value is a list of values.
                 All value lists must have the same length.
            print_parameters: Optional dictionary of parameters controlling how the
                             dataset is displayed when printed.
                
        Examples:
            >>> # Create a dataset with two columns
            >>> d = Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])
            >>> len(d)
            3
            
            >>> # Dataset with a single column
            >>> Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible']}])
            Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible']}])
        """
        super().__init__(data)
        #self.data = data
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

    def tail(self, n: int = 5) -> Dataset:
        """Return the last n observations in the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.tail(2)
        Dataset([{'a.b': [3, 4]}])
        """
        new_data = []
        for observation in self.data:
            key, values = list(observation.items())[0]
            new_data.append({key: values[-n:]})
        return Dataset(new_data)

    def head(self, n: int = 5) -> Dataset:
        """Return the first n observations in the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.head(2)
        Dataset([{'a.b': [1, 2]}])
        """
        new_data = []
        for observation in self.data:
            key, values = list(observation.items())[0]
            new_data.append({key: values[:n]})
        return Dataset(new_data)

    # def expand(self, field):
    #     return self.to_scenario_list().expand(field)


    def keys(self) -> list[str]:
        """Return the keys of the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.keys()
        ['a.b']

        >>> d = Dataset([{'a.b':[1,2,3,4]}, {'c.d':[5,6,7,8]}])
        >>> d.keys()
        ['a.b', 'c.d']


        ['a.b']
        """
        return [list(o.keys())[0] for o in self]

    def filter(self, expression):
        return self.to_scenario_list().filter(expression).to_dataset()
    
    def mutate(self, new_var_string: str, functions_dict: Optional[dict[str, Callable]] = None) -> "Dataset":
        return self.to_scenario_list().mutate(new_var_string, functions_dict).to_dataset()
    
    def collapse(self, field:str, separator: Optional[str] = None) -> "Dataset":
        return self.to_scenario_list().collapse(field, separator).to_dataset()

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
            raise DatasetValueError("All input arrays must have the same length")

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
            from .exceptions import DatasetKeyError
            raise DatasetKeyError(
                f"Key '{key}' found in more than one location: {[m[0] for m in potential_matches]}"
            )

        from .exceptions import DatasetKeyError
        raise DatasetKeyError(f"Key '{key}' not found in any of the dictionaries.")

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

    def latex(self, **kwargs):
        return self.table().latex()

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
        """
        Print the dataset in a formatted way.
        
        Args:
            pretty_labels: A dictionary mapping column names to their display names
            **kwargs: Additional arguments
                format: The output format ("html", "markdown", "rich", "latex")
                
        Returns:
            TableDisplay object
        """
        if "format" in kwargs:
            if kwargs["format"] not in ["html", "markdown", "rich", "latex"]:
                raise DatasetValueError(f"Format '{kwargs['format']}' not supported.")
            
            # If rich format is requested, set tablefmt accordingly
            if kwargs["format"] == "rich":
                kwargs["tablefmt"] = "rich"
                
        if pretty_labels is None:
            pretty_labels = {}
        else:
            return self.rename(pretty_labels).print(**kwargs)
            
        # Pass through any tablefmt parameter
        tablefmt = kwargs.get("tablefmt", None)
        return self.table(tablefmt=tablefmt)

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

    def to(self, survey_or_question: Union["Survey", "QuestionBase"]) -> "Job":
        """Return a new dataset with the observations transformed by the given survey or question.
        
        >>> d = Dataset([{'person_name':["John"]}])
        >>> from edsl import QuestionFreeText 
        >>> q = QuestionFreeText(question_text = "How are you, {{ person_name ?}}?", question_name = "how_feeling")
        >>> jobs = d.to(q)
        >>> isinstance(jobs, object)
        True
        """
        from ..surveys import Survey
        from ..questions import QuestionBase

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
        for key in keys:
            if key not in self.keys():
                from .exceptions import DatasetValueError
                raise DatasetValueError(f"Key '{key}' not found in the dataset. "
                                        f"Available keys: {self.keys()}"
                                       )
            
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

    def expand_field(self, field):
        """Expand a field in the dataset.
        
        Renamed to avoid conflict with the expand method defined earlier.
        """
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
        """
        if seed is not None:
            random.seed(seed)

        # Validate the input for sampling parameters
        if n is None and frac is None:
            from .exceptions import DatasetValueError
            raise DatasetValueError("Either 'n' or 'frac' must be provided for sampling.")

        if n is not None and frac is not None:
            from .exceptions import DatasetValueError
            raise DatasetValueError("Only one of 'n' or 'frac' should be specified.")

        # Get the length of the lists from the first entry
        first_key, first_values = list(self[0].items())[0]
        total_length = len(first_values)

        # Determine the number of samples based on 'n' or 'frac'
        if n is None:
            n = int(total_length * frac)

        if not with_replacement and n > total_length:
            from .exceptions import DatasetValueError
            raise DatasetValueError(
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

    def get_sort_indices(self, lst: list[Any], reverse: bool = False, use_numpy: bool = True) -> list[int]:
        """
        Return the indices that would sort the list, using either numpy or pure Python.
        None values are placed at the end of the sorted list.

        Args:
            lst: The list to be sorted
            reverse: Whether to sort in descending order
            use_numpy: Whether to use numpy implementation (falls back to pure Python if numpy is unavailable)

        Returns:
            A list of indices that would sort the list
        """
        if use_numpy:
            try:
                import numpy as np
                # Convert list to numpy array
                arr = np.array(lst, dtype=object)
                # Get mask of non-None values
                mask = ~(arr is None)
                # Get indices of non-None and None values
                non_none_indices = np.where(mask)[0]
                none_indices = np.where(~mask)[0]
                # Sort non-None values
                sorted_indices = non_none_indices[np.argsort(arr[mask])]
                # Combine sorted non-None indices with None indices
                indices = np.concatenate([sorted_indices, none_indices]).tolist()
                if reverse:
                    # When reversing, keep None values at end
                    indices = sorted_indices[::-1].tolist() + none_indices.tolist()
                return indices
            except ImportError:
                # Fallback to pure Python if numpy is not available
                pass
        
        # Pure Python implementation
        enumerated = list(enumerate(lst))
        # Sort None values to end by using (is_none, value) as sort key
        sorted_pairs = sorted(enumerated, 
                            key=lambda x: (x[1] is None, x[1]), 
                            reverse=reverse)
        return [index for index, _ in sorted_pairs]

    def order_by(self, sort_key: str, reverse: bool = False, use_numpy: bool = True) -> Dataset:
        """Return a new dataset with the observations sorted by the given key.

        Args:
            sort_key: The key to sort the observations by
            reverse: Whether to sort in reverse order
            use_numpy: Whether to use numpy for sorting (faster for large lists)
        """
        number_found = 0
        for obs in self.data:
            key, values = list(obs.items())[0]
            if sort_key == key or sort_key == key.split(".")[-1]:
                relevant_values = values
                number_found += 1

        if number_found == 0:
            raise DatasetKeyError(f"Key '{sort_key}' not found in any of the dictionaries.")
        elif number_found > 1:
            raise DatasetKeyError(f"Key '{sort_key}' found in more than one dictionary.")

        sort_indices_list = self.get_sort_indices(relevant_values, reverse=reverse, use_numpy=use_numpy)
        new_data = []
        for observation in self.data:
            key, values = list(observation.items())[0]
            new_values = [values[i] for i in sort_indices_list]
            new_data.append({key: new_values})

        return Dataset(new_data)

    def tree(self, node_order: Optional[list[str]] = None) -> Tree:
        """Return a tree representation of the dataset.

        >>> d = Dataset([{'a':[1,2,3,4]}, {'b':[4,3,2,1]}])
        >>> d.tree()
        Tree(Dataset({'a': [1, 2, 3, 4], 'b': [4, 3, 2, 1]}), node_order=['a', 'b'])
        """
        if node_order is None:
            node_order = self.keys()
        return Tree(self, node_order=node_order)

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = "rich",
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

        if tablefmt is not None and tablefmt != "rich":
            # Rich format is handled separately, so we don't validate it against tabulate_formats
            from tabulate import tabulate_formats

            if tablefmt not in tabulate_formats:
                print(
                    f"Error: The following table format is not supported: {tablefmt}",
                    file=sys.stderr,
                )
                print(f"\nAvailable formats are: {tabulate_formats} and 'rich'", file=sys.stderr)
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
                from .exceptions import DatasetValueError
                raise DatasetValueError(
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
    
    def to_dict(self) -> dict:
        """
        Convert the dataset to a dictionary.
        """
        return {'data': self.data}

    @classmethod
    def from_dict(cls, data: dict) -> 'Dataset':
        """
        Convert a dictionary to a dataset.
        """
        return cls(data['data'])

    def to_docx(self, output_file: str, title: str = None) -> None:
        """
        Convert the dataset to a Word document.
        
        Args:
            output_file (str): Path to save the Word document
            title (str, optional): Title for the document
        """
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        # Create document
        doc = Document()
        
        # Add title if provided
        if title:
            title_heading = doc.add_heading(title, level=1)
            title_heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Get headers and data
        headers, data = self._tabular()
        
        # Create table
        table = doc.add_table(rows=len(data) + 1, cols=len(headers))
        table.style = 'Table Grid'
        
        # Add headers
        for j, header in enumerate(headers):
            cell = table.cell(0, j)
            cell.text = str(header)
        
        # Add data
        for i, row in enumerate(data):
            for j, cell_content in enumerate(row):
                cell = table.cell(i + 1, j)
                cell.text = str(cell_content) if cell_content is not None else ""
        
        # Adjust column widths
        for column in table.columns:
            max_width = 0
            for cell in column.cells:
                text_width = len(str(cell.text))
                max_width = max(max_width, text_width)
            for cell in column.cells:
                cell.width = Inches(min(max_width * 0.1 + 0.5, 6))
        
        # Save the document
        doc.save(output_file)

    def expand(self, field: str, number_field: bool = False) -> "Dataset":
        """
        Expand a field containing lists into multiple rows.
        
        Args:
            field: The field containing lists to expand
            number_field: If True, adds a number field indicating the position in the original list
            
        Returns:
            A new Dataset with the expanded rows
            
        Example:
            >>> from edsl.dataset import Dataset
            >>> d = Dataset([{'a': [[1, 2, 3], [4, 5, 6]]}, {'b': ['x', 'y']}])
            >>> d.expand('a')
            Dataset([{'a': [1, 2, 3, 4, 5, 6]}, {'b': ['x', 'x', 'x', 'y', 'y', 'y']}])
        """
        from collections.abc import Iterable
        
        # Find the field in the dataset
        field_data = None
        for entry in self.data:
            key = list(entry.keys())[0]
            if key == field:
                field_data = entry[key]
                break
            
        if field_data is None:
            raise DatasetKeyError(f"Field '{field}' not found in dataset. Available fields are: {self.keys()}")


        # Validate that the field contains lists
        if not all(isinstance(v, list) for v in field_data):
            raise DatasetTypeError(f"Field '{field}' must contain lists in all entries")
        
        # Create new expanded data structure
        new_data = []
        
        # Process each field
        for entry in self.data:
            key, values = list(entry.items())[0]
            new_values = []
            
            if key == field:
                # This is the field to expand - flatten all sublists
                for row_values in values:
                    if not isinstance(row_values, Iterable) or isinstance(row_values, str):
                        row_values = [row_values]
                    new_values.extend(row_values)
            else:
                # For other fields, repeat each value the appropriate number of times
                for i, row_value in enumerate(values):
                    expand_length = len(field_data[i]) if i < len(field_data) else 0
                    new_values.extend([row_value] * expand_length)
            
            new_data.append({key: new_values})
        
        # Add number field if requested
        if number_field:
            number_values = []
            for i, lst in enumerate(field_data):
                number_values.extend(range(1, len(lst) + 1))
            new_data.append({f"{field}_number": number_values})
        
        return Dataset(new_data)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
