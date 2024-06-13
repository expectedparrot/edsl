"""Mixin class for exporting results."""

import base64
import csv
import io
import random
from functools import wraps

from typing import Literal, Optional

from edsl.utilities.utilities import is_notebook

from IPython.display import HTML, display
import pandas as pd
from edsl.utilities.interface import (
    print_dataset_with_rich,
    print_list_of_dicts_as_html_table,
    print_list_of_dicts_as_markdown_table,
    create_latex_table_from_data,
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
    def relevant_columns(
        self, data_type: Optional[str] = None, remove_prefix=False
    ) -> list:
        """Return the set of keys that are present in the dataset.

        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.relevant_columns()
        ['a.b']

        >>> d.relevant_columns(remove_prefix=True)
        ['b']

        >>> from edsl.results import Results; Results.example().select('how_feeling', 'how_feeling_yesterday').relevant_columns()
        ['answer.how_feeling', 'answer.how_feeling_yesterday']
        """
        columns = [list(x.keys())[0] for x in self]
        # columns = set([list(result.keys())[0] for result in self.data])
        if remove_prefix:
            columns = [column.split(".")[-1] for column in columns]

        if data_type:
            columns = [
                column for column in columns if column.split(".")[0] == data_type
            ]

        return columns

    # @_convert_decorator
    def sample(self, n: int) -> "Results":
        """Return a random sample of the results.

        :param n: The number of samples to return.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> len(r.sample(2))
        2
        """
        indices = None

        for entry in self:
            key, values = list(entry.items())[0]
            if indices is None:  # gets the indices for the first time
                indices = list(range(len(values)))
                sampled_indices = random.sample(indices, n)
                if n > len(indices):
                    raise ValueError(
                        f"Cannot sample {n} items from a list of length {len(indices)}."
                    )
            entry[key] = [values[i] for i in sampled_indices]

        return self

    @_convert_decorator
    def _make_tabular(self, remove_prefix: bool, pretty_labels: Optional[dict] = None):
        """Turn the results into a tabular format.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling')._make_tabular(remove_prefix = True)
        (['how_feeling'], [['OK'], ['Great'], ['Terrible'], ['OK']])

        >>> r.select('how_feeling')._make_tabular(remove_prefix = True, pretty_labels = {'how_feeling': "How are you feeling"})
        (['How are you feeling'], [['OK'], ['Great'], ['Terrible'], ['OK']])
        """
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
        if pretty_labels is not None:
            header = [pretty_labels.get(h, h) for h in header]
        return header, rows

    def print_long(self, max_rows=None) -> None:
        """Print the results in long format.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').print_long(max_rows = 2)
        ┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━┓
        ┃ Result index ┃ Key         ┃ Value ┃
        ┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━┩
        │ 0            │ how_feeling │ OK    │
        │ 1            │ how_feeling │ Great │
        └──────────────┴─────────────┴───────┘
        """
        from edsl.utilities.interface import print_results_long

        print_results_long(self, max_rows=max_rows)

    @_convert_decorator
    def print(
        self,
        pretty_labels: Optional[dict] = None,
        filename: Optional[str] = None,
        format: Literal["rich", "html", "markdown", "latex"] = None,
        interactive: bool = False,
        split_at_dot: bool = True,
        max_rows=None,
        tee=False,
        iframe=False,
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

        >>> r.select('how_feeling').print(format="rich", pretty_labels = {'answer.how_feeling': "How are you feeling"})
        ┏━━━━━━━━━━━━━━━━━━━━━┓
        ┃ How are you feeling ┃
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
        ...
        """
        if format is None:
            if is_notebook():
                format = "html"
            else:
                format = "rich"

        if pretty_labels is None:
            pretty_labels = {}

        if format not in ["rich", "html", "markdown", "latex"]:
            raise ValueError("format must be one of 'rich', 'html', or 'markdown'.")

        new_data = []
        for index, entry in enumerate(self):
            key, list_of_values = list(entry.items())[0]
            new_data.append({pretty_labels.get(key, key): list_of_values})

        if max_rows is not None:
            for entry in new_data:
                for key in entry:
                    actual_rows = len(entry[key])
                    entry[key] = entry[key][:max_rows]
            # print(f"Showing only the first {max_rows} rows of {actual_rows} rows.")

        if format == "rich":
            print_dataset_with_rich(
                new_data, filename=filename, split_at_dot=split_at_dot
            )
        elif format == "html":
            notebook = is_notebook()
            html_source = print_list_of_dicts_as_html_table(
                new_data, filename=None, interactive=interactive, notebook=notebook
            )
            if iframe:
                import html

                height = 200
                width = 600
                escaped_output = html.escape(html_source)
                # escaped_output = html_source
                iframe = f""""
                <iframe srcdoc="{ escaped_output }" style="width: {width}px; height: {height}px;"></iframe>
                """
                display(HTML(iframe))
            else:
                display(HTML(html_source))
        elif format == "markdown":
            print_list_of_dicts_as_markdown_table(new_data, filename=filename)
        elif format == "latex":
            df = self.to_pandas()
            df.columns = [col.replace("_", " ") for col in df.columns]
            latex_string = df.to_latex()
            if filename is not None:
                with open(filename, "w") as f:
                    f.write(latex_string)
            else:
                return latex_string
            # raise NotImplementedError("Latex format not yet implemented.")
            # latex_string = create_latex_table_from_data(new_data, filename=filename)
            # if filename is None:
            #     return latex_string
            # Not working quite

        else:
            raise ValueError("format not recognized.")

        if tee:
            return self

    @_convert_decorator
    def to_csv(
        self,
        filename: Optional[str] = None,
        remove_prefix: bool = False,
        download_link: bool = False,
        pretty_labels: Optional[dict] = None,
    ):
        """Export the results to a CSV file.

        :param filename: The filename to save the CSV file to.
        :param remove_prefix: Whether to remove the prefix from the column names.
        :param download_link: Whether to display a download link in a Jupyter notebook.

        Example:

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_csv()
        'answer.how_feeling\\r\\nOK\\r\\nGreat\\r\\nTerrible\\r\\nOK\\r\\n'
        """
        if pretty_labels is None:
            pretty_labels = {}
        header, rows = self._make_tabular(
            remove_prefix=remove_prefix, pretty_labels=pretty_labels
        )

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

        >>> from edsl.results import Results
        >>> r = Results.example()
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

    @_convert_decorator
    def to_scenario_list(self, remove_prefix: bool = True) -> list[dict]:
        """Convert the results to a list of dictionaries, one per scenario.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_scenario_list()
        ScenarioList([Scenario({'how_feeling': 'OK'}), Scenario({'how_feeling': 'Great'}), Scenario({'how_feeling': 'Terrible'}), Scenario({'how_feeling': 'OK'})])
        """
        from edsl import ScenarioList, Scenario

        list_of_dicts = self.to_dicts(remove_prefix=remove_prefix)
        return ScenarioList([Scenario(d) for d in list_of_dicts])

    def to_agent_list(self, remove_prefix: bool = True):
        from edsl import AgentList, Agent

        list_of_dicts = self.to_dicts(remove_prefix=remove_prefix)
        return AgentList([Agent(d) for d in list_of_dicts])

    @_convert_decorator
    def to_dicts(self, remove_prefix: bool = True) -> list[dict]:
        """Convert the results to a list of dictionaries.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_dicts()
        [{'how_feeling': 'OK'}, {'how_feeling': 'Great'}, {'how_feeling': 'Terrible'}, {'how_feeling': 'OK'}]

        """
        list_of_keys = []
        list_of_values = []
        for entry in self:
            key, values = list(entry.items())[0]
            list_of_keys.append(key)
            list_of_values.append(values)

        if remove_prefix:
            list_of_keys = [key.split(".")[-1] for key in list_of_keys]
        #        else:
        #            list_of_keys = [key.replace(".", "_") for key in list_of_keys]

        list_of_dicts = []
        for entries in zip(*list_of_values):
            list_of_dicts.append(dict(zip(list_of_keys, entries)))

        return list_of_dicts

    @_convert_decorator
    def to_list(self, flatten=False, remove_none=False) -> list[list]:
        """Convert the results to a list of lists.

        >>> from edsl.results import Results
        >>> Results.example().select('how_feeling', 'how_feeling_yesterday')
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}, {'answer.how_feeling_yesterday': ['Great', 'Good', 'OK', 'Terrible']}])

        >>> Results.example().select('how_feeling', 'how_feeling_yesterday').to_list()
        [('OK', 'Great'), ('Great', 'Good'), ('Terrible', 'OK'), ('OK', 'Terrible')]

        >>> r = Results.example()
        >>> r.select('how_feeling').to_list()
        ['OK', 'Great', 'Terrible', 'OK']
        """
        if len(self.relevant_columns()) > 1 and flatten:
            raise ValueError(
                "Cannot flatten a list of lists when there are multiple columns selected."
            )

        if len(self.relevant_columns()) == 1:
            # if only one 'column' is selected (which is typical for this method
            list_to_return = list(self[0].values())[0]
        else:
            keys = self.relevant_columns()
            data = self.to_dicts(remove_prefix=False)
            list_to_return = []
            for d in data:
                list_to_return.append(tuple([d[key] for key in keys]))

        if remove_none:
            list_to_return = [item for item in list_to_return if item is not None]

        if flatten:
            new_list = []
            for item in list_to_return:
                if isinstance(item, list):
                    new_list.extend(item)
                else:
                    new_list.append(item)
            list_to_return = new_list

        return list_to_return

    @_convert_decorator
    def html(
        self, filename: str = None, cta: str = "Open in browser", return_link=False
    ):
        import os
        import tempfile

        df = self.to_pandas()

        if filename is None:
            current_directory = os.getcwd()
            filename = tempfile.NamedTemporaryFile(
                "w", delete=False, suffix=".html", dir=current_directory
            ).name

        with open(filename, "w") as f:
            f.write(df.to_html())

        if is_notebook():
            html_url = f"/files/{filename}"
            html_link = f'<a href="{html_url}" target="_blank">{cta}</a>'
            display(HTML(html_link))
        else:
            print(f"Saved to {filename}")
            import webbrowser
            import os

            webbrowser.open(f"file://{os.path.abspath(filename)}")
            # webbrowser.open(filename)

        if return_link:
            return filename

    @_convert_decorator
    def tally(self, *fields: Optional[str], top_n=None, format=None):
        """Tally the values of a field or perform a cross-tab of multiple fields.

        :param fields: The field(s) to tally, multiple fields for cross-tabulation.

        >>> r = Results.example()
        >>> r.select('how_feeling').tally('answer.how_feeling')
        {'OK': 2, 'Great': 1, 'Terrible': 1}
        >>> r.tally('field1', 'field2')
        {('X', 'A'): 1, ('X', 'B'): 1, ('Y', 'A'): 1}
        """
        from collections import Counter

        if len(fields) == 0:
            fields = self.relevant_columns()

        relevant_columns_without_prefix = [
            column.split(".")[-1] for column in self.relevant_columns()
        ]

        if not all(
            f in self.relevant_columns() or f in relevant_columns_without_prefix
            for f in fields
        ):
            raise ValueError("One or more specified fields are not in the dataset.")

        if len(fields) == 1:
            field = fields[0]
            values = self._key_to_value(field)
        else:
            values = list(zip(*(self._key_to_value(field) for field in fields)))

        tally = dict(Counter(values))
        sorted_tally = dict(sorted(tally.items(), key=lambda item: -item[1]))
        if top_n is not None:
            sorted_tally = dict(list(sorted_tally.items())[:top_n])

        if format is not None:
            if format == "rich":
                from edsl.utilities.interface import print_tally_with_rich

                print_tally_with_rich(sorted_tally)
                return None

        return sorted_tally


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
