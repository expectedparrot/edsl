"""Mixin class for exporting results."""

import base64
import csv
import io

from typing import Literal, Optional, Union


class DatasetExportMixin:
    """Mixin class"""

    def relevant_columns(
        self, data_type: Optional[str] = None, remove_prefix=False
    ) -> list:
        """Return the set of keys that are present in the dataset.

        :param data_type: The data type to filter by.
        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results.Dataset import Dataset
        >>> d = Dataset([{'a.b':[1,2,3,4]}])
        >>> d.relevant_columns()
        ['a.b']

        >>> d.relevant_columns(remove_prefix=True)
        ['b']

        >>> from edsl.results import Results; Results.example().select('how_feeling', 'how_feeling_yesterday').relevant_columns()
        ['answer.how_feeling', 'answer.how_feeling_yesterday']
        """
        columns = [list(x.keys())[0] for x in self]
        if remove_prefix:
            columns = [column.split(".")[-1] for column in columns]

        if data_type:
            columns = [
                column for column in columns if column.split(".")[0] == data_type
            ]

        return columns

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

    def print_long(self):
        """Print the results in a long format.
        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').print_long()
        answer.how_feeling: OK
        answer.how_feeling: Great
        answer.how_feeling: Terrible
        answer.how_feeling: OK
        """
        for entry in self:
            key, list_of_values = list(entry.items())[0]
            for value in list_of_values:
                print(f"{key}: {value}")

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
        iframe_height: int = 200,
        iframe_width: int = 600,
        web=False,
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

        >>> r = Results.example()
        >>> r2 = r.select("how_feeling").print(format = "rich", tee = True, max_rows = 2)
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ OK           │
        ├──────────────┤
        │ Great        │
        └──────────────┘
        >>> r2
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}])

        >>> r.select('how_feeling').print(format = "rich", max_rows = 2)
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ OK           │
        ├──────────────┤
        │ Great        │
        └──────────────┘

        >>> r.select('how_feeling').print(format = "rich", split_at_dot = False)
        ┏━━━━━━━━━━━━━━━━━━━━┓
        ┃ answer.how_feeling ┃
        ┡━━━━━━━━━━━━━━━━━━━━┩
        │ OK                 │
        ├────────────────────┤
        │ Great              │
        ├────────────────────┤
        │ Terrible           │
        ├────────────────────┤
        │ OK                 │
        └────────────────────┘

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
        from IPython.display import HTML, display
        from edsl.utilities.utilities import is_notebook

        if format is None:
            if is_notebook():
                format = "html"
            else:
                format = "rich"

        if pretty_labels is None:
            pretty_labels = {}
        else:
            # if the user passes in pretty_labels, we don't want to split at the dot
            split_at_dot = False

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

        if format == "rich":
            from edsl.utilities.interface import print_dataset_with_rich

            print_dataset_with_rich(
                new_data, filename=filename, split_at_dot=split_at_dot
            )
        elif format == "html":
            notebook = is_notebook()
            from edsl.utilities.interface import print_list_of_dicts_as_html_table

            html_source = print_list_of_dicts_as_html_table(
                new_data, interactive=interactive
            )
            if iframe:
                import html

                height = iframe_height
                width = iframe_width
                escaped_output = html.escape(html_source)
                # escaped_output = html_source
                iframe = f""""
                <iframe srcdoc="{ escaped_output }" style="width: {width}px; height: {height}px;"></iframe>
                """
                display(HTML(iframe))
            elif notebook:
                display(HTML(html_source))
            else:
                from edsl.utilities.interface import view_html

                view_html(html_source)

        elif format == "markdown":
            from edsl.utilities.interface import print_list_of_dicts_as_markdown_table

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

        >>> r.select('how_feeling').to_csv(pretty_labels = {'answer.how_feeling': "How are you feeling"})
        'How are you feeling\\r\\nOK\\r\\nGreat\\r\\nTerrible\\r\\nOK\\r\\n'

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

    def to_pandas(self, remove_prefix: bool = False) -> "pd.DataFrame":
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
        import pandas as pd

        csv_string = self.to_csv(remove_prefix=remove_prefix)
        csv_buffer = io.StringIO(csv_string)
        df = pd.read_csv(csv_buffer)
        df_sorted = df.sort_index(axis=1)  # Sort columns alphabetically
        return df_sorted

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
        """Convert the results to a list of dictionaries, one per agent.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_agent_list()
        AgentList([Agent(traits = {'how_feeling': 'OK'}), Agent(traits = {'how_feeling': 'Great'}), Agent(traits = {'how_feeling': 'Terrible'}), Agent(traits = {'how_feeling': 'OK'})])
        """
        from edsl import AgentList, Agent

        list_of_dicts = self.to_dicts(remove_prefix=remove_prefix)
        return AgentList([Agent(d) for d in list_of_dicts])

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

        list_of_dicts = []
        for entries in zip(*list_of_values):
            list_of_dicts.append(dict(zip(list_of_keys, entries)))

        return list_of_dicts

    def to_list(self, flatten=False, remove_none=False) -> list[list]:
        """Convert the results to a list of lists.

        :param flatten: Whether to flatten the list of lists.
        :param remove_none: Whether to remove None values from the list.

        >>> from edsl.results import Results
        >>> Results.example().select('how_feeling', 'how_feeling_yesterday')
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}, {'answer.how_feeling_yesterday': ['Great', 'Good', 'OK', 'Terrible']}])

        >>> Results.example().select('how_feeling', 'how_feeling_yesterday').to_list()
        [('OK', 'Great'), ('Great', 'Good'), ('Terrible', 'OK'), ('OK', 'Terrible')]

        >>> r = Results.example()
        >>> r.select('how_feeling').to_list()
        ['OK', 'Great', 'Terrible', 'OK']

        >>> from edsl.results.Dataset import Dataset
        >>> Dataset([{'a.b': [[1, 9], 2, 3, 4]}]).select('a.b').to_list(flatten = True)
        [1, 9, 2, 3, 4]

        >>> from edsl.results.Dataset import Dataset
        >>> Dataset([{'a.b': [[1, 9], 2, 3, 4]}, {'c': [6, 2, 3, 4]}]).select('a.b', 'c').to_list(flatten = True)
        Traceback (most recent call last):
        ...
        ValueError: Cannot flatten a list of lists when there are multiple columns selected.


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

    def html(
        self,
        filename: Optional[str] = None,
        cta: str = "Open in browser",
        return_link: bool = False,
    ):
        import os
        import tempfile
        from edsl.utilities.utilities import is_notebook
        from IPython.display import HTML, display
        from edsl.utilities.utilities import is_notebook

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

        if return_link:
            return filename

    def tally(
        self, *fields: Optional[str], top_n: Optional[int] = None, output="dict"
    ) -> Union[dict, "Dataset"]:
        """Tally the values of a field or perform a cross-tab of multiple fields.

        :param fields: The field(s) to tally, multiple fields for cross-tabulation.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').tally('answer.how_feeling')
        {'OK': 2, 'Great': 1, 'Terrible': 1}
        >>> r.select('how_feeling', 'period').tally('how_feeling', 'period')
        {('OK', 'morning'): 1, ('Great', 'afternoon'): 1, ('Terrible', 'morning'): 1, ('OK', 'afternoon'): 1}
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

        for value in values:
            if isinstance(value, list):
                value = tuple(value)

        tally = dict(Counter(values))
        sorted_tally = dict(sorted(tally.items(), key=lambda item: -item[1]))
        if top_n is not None:
            sorted_tally = dict(list(sorted_tally.items())[:top_n])

        import warnings
        import textwrap
        from edsl.results.Dataset import Dataset

        if output == "dict":
            warnings.warn(
                textwrap.dedent(
                    """\
                        The default output from tally will change to Dataset in the future.
                        Use output='Dataset' to get the Dataset object for now.
                        """
                )
            )
            return sorted_tally
        elif output == "Dataset":
            return Dataset(
                [
                    {"value": list(sorted_tally.keys())},
                    {"count": list(sorted_tally.values())},
                ]
            )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
