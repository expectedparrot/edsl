"""Mixin class for exporting results."""

import base64
import csv
import io
import html
from typing import Optional

from typing import Literal, Optional, Union, List


class DatasetExportMixin:
    """Mixin class for exporting Dataset objects."""

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

        >>> d = Dataset([{'a':[1,2,3,4]}, {'b':[5,6,7,8]}])
        >>> d.relevant_columns()
        ['a', 'b']

        >>> from edsl.results import Results; Results.example().select('how_feeling', 'how_feeling_yesterday').relevant_columns()
        ['answer.how_feeling', 'answer.how_feeling_yesterday']

        >>> from edsl.results import Results
        >>> sorted(Results.example().select().relevant_columns(data_type = "model"))
        ['model.frequency_penalty', 'model.logprobs', 'model.max_tokens', 'model.model', 'model.presence_penalty', 'model.temperature', 'model.top_logprobs', 'model.top_p']

        >>> Results.example().relevant_columns(data_type = "flimflam")
        Traceback (most recent call last):
        ...
        ValueError: No columns found for data type: flimflam. Available data types are: ...
        """
        columns = [list(x.keys())[0] for x in self]
        if remove_prefix:
            columns = [column.split(".")[-1] for column in columns]

        def get_data_type(column):
            if "." in column:
                return column.split(".")[0]
            else:
                return None

        if data_type:
            all_columns = columns[:]
            columns = [
                column for column in columns if get_data_type(column) == data_type
            ]
            if len(columns) == 0:
                all_data_types = sorted(
                    list(set(get_data_type(column) for column in all_columns))
                )
                raise ValueError(
                    f"No columns found for data type: {data_type}. Available data types are: {all_data_types}."
                )

        return columns

    def num_observations(self):
        """Return the number of observations in the dataset.

        >>> from edsl.results import Results
        >>> Results.example().num_observations()
        4
        """
        _num_observations = None
        for entry in self:
            key, values = list(entry.items())[0]
            if _num_observations is None:
                _num_observations = len(values)
            else:
                if len(values) != _num_observations:
                    raise ValueError(
                        "The number of observations is not consistent across columns."
                    )

        return _num_observations

    def _make_tabular(
        self, remove_prefix: bool, pretty_labels: Optional[dict] = None
    ) -> tuple[list, List[list]]:
        """Turn the results into a tabular format.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling')._make_tabular(remove_prefix = True)
        (['how_feeling'], [['OK'], ['Great'], ['Terrible'], ['OK']])

        >>> r.select('how_feeling')._make_tabular(remove_prefix = True, pretty_labels = {'how_feeling': "How are you feeling"})
        (['How are you feeling'], [['OK'], ['Great'], ['Terrible'], ['OK']])
        """

        def create_dict_from_list_of_dicts(list_of_dicts):
            for entry in list_of_dicts:
                key, list_of_values = list(entry.items())[0]
                yield key, list_of_values

        tabular_repr = dict(create_dict_from_list_of_dicts(self.data))

        full_header = [list(x.keys())[0] for x in self]

        rows = []
        for i in range(self.num_observations()):
            row = [tabular_repr[h][i] for h in full_header]
            rows.append(row)

        if remove_prefix:
            header = [h.split(".")[-1] for h in full_header]
        else:
            header = full_header

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

    # def print(
    #     self,
    #     pretty_labels: Optional[dict] = None,
    #     filename: Optional[str] = None,
    #     format: Optional[Literal["rich", "html", "markdown", "latex"]] = None,
    #     interactive: bool = False,
    #     split_at_dot: bool = True,
    #     max_rows=None,
    #     tee=False,
    #     iframe=False,
    #     iframe_height: int = 200,
    #     iframe_width: int = 600,
    #     web=False,
    #     return_string: bool = False,
    # ) -> Union[None, str, "Results"]:
    #     """Print the results in a pretty format.

    #     :param pretty_labels: A dictionary of pretty labels for the columns.
    #     :param filename: The filename to save the results to.
    #     :param format: The format to print the results in. Options are 'rich', 'html', 'markdown', or 'latex'.
    #     :param interactive: Whether to print the results interactively in a Jupyter notebook.
    #     :param split_at_dot: Whether to split the column names at the last dot w/ a newline.
    #     :param max_rows: The maximum number of rows to print.
    #     :param tee: Whether to return the dataset.
    #     :param iframe: Whether to display the table in an iframe.
    #     :param iframe_height: The height of the iframe.
    #     :param iframe_width: The width of the iframe.
    #     :param web: Whether to display the table in a web browser.
    #     :param return_string: Whether to return the output as a string instead of printing.

    #     :return: None if tee is False and return_string is False, the dataset if tee is True, or a string if return_string is True.

    #     Example: Print in rich format at the terminal

    #     >>> from edsl.results import Results
    #     >>> r = Results.example()
    #     >>> r.select('how_feeling').print(format = "rich")
    #     ┏━━━━━━━━━━━━━━┓
    #     ┃ answer       ┃
    #     ┃ .how_feeling ┃
    #     ┡━━━━━━━━━━━━━━┩
    #     │ OK           │
    #     ├──────────────┤
    #     │ Great        │
    #     ├──────────────┤
    #     │ Terrible     │
    #     ├──────────────┤
    #     │ OK           │
    #     └──────────────┘

    #     >>> r = Results.example()
    #     >>> r2 = r.select("how_feeling").print(format = "rich", tee = True, max_rows = 2)
    #     ┏━━━━━━━━━━━━━━┓
    #     ┃ answer       ┃
    #     ┃ .how_feeling ┃
    #     ┡━━━━━━━━━━━━━━┩
    #     │ OK           │
    #     ├──────────────┤
    #     │ Great        │
    #     └──────────────┘
    #     >>> r2
    #     Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}])

    #     >>> r.select('how_feeling').print(format = "rich", max_rows = 2)
    #     ┏━━━━━━━━━━━━━━┓
    #     ┃ answer       ┃
    #     ┃ .how_feeling ┃
    #     ┡━━━━━━━━━━━━━━┩
    #     │ OK           │
    #     ├──────────────┤
    #     │ Great        │
    #     └──────────────┘

    #     >>> r.select('how_feeling').print(format = "rich", split_at_dot = False)
    #     ┏━━━━━━━━━━━━━━━━━━━━┓
    #     ┃ answer.how_feeling ┃
    #     ┡━━━━━━━━━━━━━━━━━━━━┩
    #     │ OK                 │
    #     ├────────────────────┤
    #     │ Great              │
    #     ├────────────────────┤
    #     │ Terrible           │
    #     ├────────────────────┤
    #     │ OK                 │
    #     └────────────────────┘

    #     Example: using the pretty_labels parameter

    #     >>> r.select('how_feeling').print(format="rich", pretty_labels = {'answer.how_feeling': "How are you feeling"})
    #     ┏━━━━━━━━━━━━━━━━━━━━━┓
    #     ┃ How are you feeling ┃
    #     ┡━━━━━━━━━━━━━━━━━━━━━┩
    #     │ OK                  │
    #     ├─────────────────────┤
    #     │ Great               │
    #     ├─────────────────────┤
    #     │ Terrible            │
    #     ├─────────────────────┤
    #     │ OK                  │
    #     └─────────────────────┘

    #     Example: printing in markdown format

    #     >>> r.select('how_feeling').print(format='markdown')
    #     | answer.how_feeling |
    #     |--|
    #     | OK |
    #     | Great |
    #     | Terrible |
    #     | OK |
    #     ...

    #     >>> r.select('how_feeling').print(format='latex')
    #     \\begin{tabular}{l}
    #     ...
    #     \\end{tabular}
    #     <BLANKLINE>
    #     """
    #     from IPython.display import HTML, display
    #     from edsl.utilities.utilities import is_notebook
    #     import io
    #     import sys

    #     def _determine_format(format):
    #         if format is None:
    #             if is_notebook():
    #                 format = "html"
    #             else:
    #                 format = "rich"
    #         if format not in ["rich", "html", "markdown", "latex"]:
    #             raise ValueError(
    #                 "format must be one of 'rich', 'html', 'markdown', or 'latex'."
    #             )

    #         return format

    #     format = _determine_format(format)

    #     if pretty_labels is None:
    #         pretty_labels = {}

    #     if pretty_labels != {}:  # only split at dot if there are no pretty labels
    #         split_at_dot = False

    #     def _create_data():
    #         for index, entry in enumerate(self):
    #             key, list_of_values = list(entry.items())[0]
    #             yield {pretty_labels.get(key, key): list_of_values[:max_rows]}

    #     new_data = list(_create_data())

    #     # Capture output if return_string is True
    #     if return_string:
    #         old_stdout = sys.stdout
    #         sys.stdout = io.StringIO()

    #     output = None

    #     if format == "rich":
    #         from edsl.utilities.interface import print_dataset_with_rich

    #         output = print_dataset_with_rich(
    #             new_data, filename=filename, split_at_dot=split_at_dot
    #         )
    #     elif format == "markdown":
    #         from edsl.utilities.interface import print_list_of_dicts_as_markdown_table

    #         output = print_list_of_dicts_as_markdown_table(new_data, filename=filename)
    #     elif format == "latex":
    #         df = self.to_pandas()
    #         df.columns = [col.replace("_", " ") for col in df.columns]
    #         latex_string = df.to_latex(index=False)

    #         if filename is not None:
    #             with open(filename, "w") as f:
    #                 f.write(latex_string)
    #         else:
    #             print(latex_string)
    #             output = latex_string
    #     elif format == "html":
    #         from edsl.utilities.interface import print_list_of_dicts_as_html_table

    #         html_source = print_list_of_dicts_as_html_table(
    #             new_data, interactive=interactive
    #         )

    #         if iframe:
    #             iframe = f""""
    #             <iframe srcdoc="{ html.escape(html_source) }" style="width: {iframe_width}px; height: {iframe_height}px;"></iframe>
    #             """
    #             display(HTML(iframe))
    #         elif is_notebook():
    #             display(HTML(html_source))
    #         else:
    #             from edsl.utilities.interface import view_html

    #             view_html(html_source)

    #         output = html_source

    #     # Restore stdout and get captured output if return_string is True
    #     if return_string:
    #         captured_output = sys.stdout.getvalue()
    #         sys.stdout = old_stdout
    #         return captured_output or output

    #     if tee:
    #         return self

    #     return None

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

        >>> import tempfile
        >>> filename = tempfile.NamedTemporaryFile(delete=False).name
        >>> r.select('how_feeling').to_csv(filename = filename)
        >>> import os
        >>> import csv
        >>> with open(filename, newline='') as f:
        ...     reader = csv.reader(f)
        ...     for row in reader:
        ...         print(row)
        ['answer.how_feeling']
        ['OK']
        ['Great']
        ['Terrible']
        ['OK']

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
            # print(f"Saved to {filename}")
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(header)
            writer.writerows(rows)

            if download_link:
                from IPython.display import HTML, display

                csv_file = output.getvalue()
                b64 = base64.b64encode(csv_file.encode()).decode()
                download_link = f'<a href="data:file/csv;base64,{b64}" download="my_data.csv">Download CSV file</a>'
                display(HTML(download_link))
            else:
                return output.getvalue()

    def download_link(self, pretty_labels: Optional[dict] = None) -> str:
        """Return a download link for the results.

        :param pretty_labels: A dictionary of pretty labels for the columns.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').download_link()
        '<a href="data:file/csv;base64,YW5zd2VyLmhvd19mZWVsaW5nDQpPSw0KR3JlYXQNClRlcnJpYmxlDQpPSw0K" download="my_data.csv">Download CSV file</a>'
        """
        import base64

        csv_string = self.to_csv(pretty_labels=pretty_labels)
        b64 = base64.b64encode(csv_string.encode()).decode()
        return f'<a href="data:file/csv;base64,{b64}" download="my_data.csv">Download CSV file</a>'

    def to_pandas(
        self, remove_prefix: bool = False, lists_as_strings=False
    ) -> "DataFrame":
        """Convert the results to a pandas DataFrame, ensuring that lists remain as lists.

        :param remove_prefix: Whether to remove the prefix from the column names.

        """
        return self._to_pandas_strings(remove_prefix)
        # if lists_as_strings:
        #     return self._to_pandas_strings(remove_prefix=remove_prefix)

        # import pandas as pd

        # df = pd.DataFrame(self.data)

        # if remove_prefix:
        #     # Optionally remove prefixes from column names
        #     df.columns = [col.split(".")[-1] for col in df.columns]

        # df_sorted = df.sort_index(axis=1)  # Sort columns alphabetically
        # return df_sorted

    def _to_pandas_strings(self, remove_prefix: bool = False) -> "pd.DataFrame":
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
        # df_sorted = df.sort_index(axis=1)  # Sort columns alphabetically
        return df

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
        scenarios = []
        for d in list_of_dicts:
            scenarios.append(Scenario(d))
        return ScenarioList(scenarios)
        # return ScenarioList([Scenario(d) for d in list_of_dicts])

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
        agents = []
        for d in list_of_dicts:
            if "name" in d:
                d["agent_name"] = d.pop("name")
                agents.append(Agent(d, name=d["agent_name"]))
            else:
                agents.append(Agent(d))
        return AgentList(agents)

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

    def to_list(self, flatten=False, remove_none=False, unzipped=False) -> list[list]:
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
        self, *fields: Optional[str], top_n: Optional[int] = None, output="Dataset"
    ) -> Union[dict, "Dataset"]:
        """Tally the values of a field or perform a cross-tab of multiple fields.

        :param fields: The field(s) to tally, multiple fields for cross-tabulation.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').tally('answer.how_feeling', output = "dict")
        {'OK': 2, 'Great': 1, 'Terrible': 1}
        >>> r.select('how_feeling').tally('answer.how_feeling', output = "Dataset")
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible']}, {'count': [2, 1, 1]}])
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
            # why did I do this?
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
            dataset = Dataset(
                [
                    {"value": list(sorted_tally.keys())},
                    {"count": list(sorted_tally.values())},
                ]
            )
            # return dataset
            sl = dataset.to_scenario_list().unpack(
                "value",
                new_names=[fields] if isinstance(fields, str) else fields,
                keep_original=False,
            )
            keys = list(sl[0].keys())
            keys.remove("count")
            keys.append("count")
            return sl.reorder_keys(keys).to_dataset()


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
