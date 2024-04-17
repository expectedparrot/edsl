"""Mixin class for exporting results."""
import base64
import csv
import io
from functools import wraps

from typing import Literal, Optional

from edsl.utilities.utilities import is_notebook

from IPython.display import HTML, display
import pandas as pd
from edsl.utilities import (
    print_list_of_dicts_with_rich,
    print_list_of_dicts_as_html_table,
    print_dict_with_rich,
    print_list_of_dicts_as_markdown_table,
)


class ResultsExportMixin:
    """Mixin class for exporting Results objects."""

    def _convert_decorator(func):
        """Convert the Results object to a Dataset object before calling the function."""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            """Return the function with the Results object converted to a Dataset object."""
            if self.__class__.__name__ == "Results":
                return func(self.select(), *args, **kwargs)
            elif self.__class__.__name__ == "Dataset":
                return func(self, *args, **kwargs)
            else:
                raise Exception(
                    f"Class {self.__class__.__name__} not recognized as a Results or Dataset object."
                )

        return wrapper

    @_convert_decorator
    def _make_tabular(self, remove_prefix) -> tuple[list, list]:
        """Turn the results into a tabular format."""
        d = {}
        full_header = sorted(list(self.relevant_columns()))
        for entry in self.data:
            key, list_of_values = list(entry.items())[0]
            d[key] = list_of_values
        if remove_prefix:
            header = [h.split(".")[-1] for h in full_header]
        else:
            header = full_header
        num_observations = len(list(self[0].values())[0])
        rows = []
        # rows.append(header)
        for i in range(num_observations):
            row = [d[h][i] for h in full_header]
            rows.append(row)
        return header, rows

    def print_long(self) -> None:
        """Print the results in long format."""
        for result in self:
            if hasattr(result, "combined_dict"):
                d = result.combined_dict
            else:
                d = result
            print_dict_with_rich(d)

    @_convert_decorator
    def print(
        self,
        pretty_labels: Optional[dict] = None,
        filename: Optional[str] = None,
        format: Literal["rich", "html", "markdown"] = None,
        interactive: bool = False,
        split_at_dot: bool = True,
        max_rows=None,
    ) -> None:
        """Print the results in a pretty format.

        :param pretty_labels: A dictionary of pretty labels for the columns.
        :param filename: The filename to save the results to.
        :param format: The format to print the results in. Options are 'rich', 'html', or 'markdown'.
        :param interactive: Whether to print the results interactively in a Jupyter notebook.
        :param split_at_dot: Whether to split the column names at the last dot w/ a newline.

        Example: Print in rich format at the terminal

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.print()
        >>> r.select('how_feeling').print(format = "rich")
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ OK           │
        ├──────────────┤
        │ Great        │
        ├──────────────┤
        │ Terrible     │
        ├──────────────┤
        │ OK           │
        └──────────────┘

        Example: using the pretty_labels parameter

        >>> r.select('how_feeling').print(format="rich", pretty_labels = {'answer.how_feeling': "How you are feeling"})
        ┏━━━━━━━━━━━━━━━━━━━━━┓
        ┃ How you are feeling ┃
        ┡━━━━━━━━━━━━━━━━━━━━━┩
        │ OK                  │
        ├─────────────────────┤
        │ Great               │
        ├─────────────────────┤
        │ Terrible            │
        ├─────────────────────┤
        │ OK                  │
        └─────────────────────┘

        Example: printing in markdown format

        >>> r.select('how_feeling').print(format='markdown')
        | answer.how_feeling |
        |--|
        | OK |
        | Great |
        | Terrible |
        | OK |


        """
        if format is None:
            if is_notebook():
                format = "html"
            else:
                format = "rich"

        if pretty_labels is None:
            pretty_labels = {}

        if format not in ["rich", "html", "markdown"]:
            raise ValueError("format must be one of 'rich', 'html', or 'markdown'.")

        new_data = []
        for index, entry in enumerate(self):
            key, list_of_values = list(entry.items())[0]
            new_data.append({pretty_labels.get(key, key): list_of_values})

        if max_rows is not None:
            for entry in new_data:
                for key in entry:
                    entry[key] = entry[key][:max_rows]

        if format == "rich":
            print_list_of_dicts_with_rich(
                new_data, filename=filename, split_at_dot=split_at_dot
            )
        elif format == "html":
            notebook = is_notebook()
            html = print_list_of_dicts_as_html_table(
                new_data, filename=None, interactive=interactive, notebook=notebook
            )
            # print(html)
            display(HTML(html))
        elif format == "markdown":
            print_list_of_dicts_as_markdown_table(new_data, filename=filename)

    @_convert_decorator
    def to_csv(
        self,
        filename: Optional[str] = None,
        remove_prefix: bool = False,
        download_link: bool = False,
    ):
        """Export the results to a CSV file.

        :param filename: The filename to save the CSV file to.
        :param remove_prefix: Whether to remove the prefix from the column names.
        :param download_link: Whether to display a download link in a Jupyter notebook.

        Example:

        >>> r = create_example_results()
        >>> r.select('how_feeling').to_csv()
        'result.how_feeling\\r\\nBad\\r\\nBad\\r\\nGreat\\r\\nGreat\\r\\n'
        """
        header, rows = self._make_tabular(remove_prefix)

        if filename is not None:
            with open(filename, "w") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerows(rows)
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(header)
            writer.writerows(rows)

            if download_link:
                csv_file = output.getvalue()
                b64 = base64.b64encode(csv_file.encode()).decode()
                download_link = f'<a href="data:file/csv;base64,{b64}" download="my_data.csv">Download CSV file</a>'
                display(HTML(download_link))
            else:
                return output.getvalue()

    @_convert_decorator
    def to_pandas(self, remove_prefix: bool = False) -> pd.DataFrame:
        """Convert the results to a pandas DataFrame.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> r.select('how_feeling').to_pandas()
        answer.how_feeling
        0                 OK
        1              Great
        2           Terrible
        3                 OK

        """
        csv_string = self.to_csv(remove_prefix=remove_prefix)
        csv_buffer = io.StringIO(csv_string)
        df = pd.read_csv(csv_buffer)
        df_sorted = df.sort_index(axis=1)  # Sort columns alphabetically
        return df_sorted
        # return df

    @_convert_decorator
    def to_dicts(self, remove_prefix: bool = False) -> list[dict]:
        """Convert the results to a list of dictionaries.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_dicts()
        [{'answer.how_feeling': 'OK'}, {'answer.how_feeling': 'Great'}, {'answer.how_feeling': 'Terrible'}, {'answer.how_feeling': 'OK'}]

        """
        df = self.to_pandas(remove_prefix=remove_prefix)
        df = df.convert_dtypes()
        list_of_dicts = df.to_dict(orient="records")
        # Convert any pd.NA values to None
        list_of_dicts = [
            {k: (None if pd.isna(v) else v) for k, v in record.items()}
            for record in list_of_dicts
        ]
        return list_of_dicts

    @_convert_decorator
    def to_list(self) -> list[list]:
        """Convert the results to a list of lists.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_list()
        ['OK', 'Great', 'Terrible', 'OK']
        """
        if len(self) == 1:
            return list(self[0].values())[0]
        else:
            return tuple([list(x.values())[0] for x in self])


if __name__ == "__main__":
    import doctest

    doctest.testmod()
