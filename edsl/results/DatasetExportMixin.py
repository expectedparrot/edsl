"""Mixin class for exporting results."""

import io
import warnings
import textwrap
from typing import Optional, Tuple, Union, List

from edsl.results.file_exports import CSVExport, ExcelExport, JSONLExport, SQLiteExport


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
        ['model.frequency_penalty', ...]

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

        >>> from edsl.results.Results import Results
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

    def _get_tabular_data(
        self,
        remove_prefix: bool = False,
        pretty_labels: Optional[dict] = None,
    ) -> Tuple[List[str], List[List]]:
        """Internal method to get tabular data in a standard format.

        Args:
            remove_prefix: Whether to remove the prefix from column names
            pretty_labels: Dictionary mapping original column names to pretty labels

        Returns:
            Tuple containing (header_row, data_rows)
        """
        if pretty_labels is None:
            pretty_labels = {}

        return self._make_tabular(
            remove_prefix=remove_prefix, pretty_labels=pretty_labels
        )

    def to_jsonl(self, filename: Optional[str] = None) -> Optional["FileStore"]:
        """Export the results to a FileStore instance containing JSONL data."""
        exporter = JSONLExport(data=self, filename=filename)
        return exporter.export()

    def to_sqlite(
        self,
        filename: Optional[str] = None,
        remove_prefix: bool = False,
        pretty_labels: Optional[dict] = None,
        table_name: str = "results",
        if_exists: str = "replace",
    ) -> Optional["FileStore"]:
        """Export the results to a SQLite database file."""
        exporter = SQLiteExport(
            data=self,
            filename=filename,
            remove_prefix=remove_prefix,
            pretty_labels=pretty_labels,
            table_name=table_name,
            if_exists=if_exists,
        )
        return exporter.export()

    def to_csv(
        self,
        filename: Optional[str] = None,
        remove_prefix: bool = False,
        pretty_labels: Optional[dict] = None,
    ) -> Optional["FileStore"]:
        """Export the results to a FileStore instance containing CSV data."""
        exporter = CSVExport(
            data=self,
            filename=filename,
            remove_prefix=remove_prefix,
            pretty_labels=pretty_labels,
        )
        return exporter.export()

    def to_excel(
        self,
        filename: Optional[str] = None,
        remove_prefix: bool = False,
        pretty_labels: Optional[dict] = None,
        sheet_name: Optional[str] = None,
    ) -> Optional["FileStore"]:
        """Export the results to a FileStore instance containing Excel data."""
        exporter = ExcelExport(
            data=self,
            filename=filename,
            remove_prefix=remove_prefix,
            pretty_labels=pretty_labels,
            sheet_name=sheet_name,
        )
        return exporter.export()

    def _db(self, remove_prefix: bool = True):
        """Create a SQLite database in memory and return the connection.

        Args:
            shape: The shape of the data in the database (wide or long)
            remove_prefix: Whether to remove the prefix from the column names

        Returns:
            A database connection
        """
        from sqlalchemy import create_engine

        engine = create_engine("sqlite:///:memory:")
        if remove_prefix:
            df = self.remove_prefix().to_pandas(lists_as_strings=True)
        else:
            df = self.to_pandas(lists_as_strings=True)
        df.to_sql(
            "self",
            engine,
            index=False,
            if_exists="replace",
        )
        return engine.connect()

    def sql(
        self,
        query: str,
        transpose: bool = None,
        transpose_by: str = None,
        remove_prefix: bool = True,
    ) -> Union["pd.DataFrame", str]:
        """Execute a SQL query and return the results as a DataFrame.

        Args:
            query: The SQL query to execute
            shape: The shape of the data in the database (wide or long)
            remove_prefix: Whether to remove the prefix from the column names
            transpose: Whether to transpose the DataFrame
            transpose_by: The column to use as the index when transposing
            csv: Whether to return the DataFrame as a CSV string
            to_list: Whether to return the results as a list
            to_latex: Whether to return the results as LaTeX
            filename: Optional filename to save the results to

        Returns:
            DataFrame, CSV string, list, or LaTeX string depending on parameters

        """
        import pandas as pd

        conn = self._db(remove_prefix=remove_prefix)
        df = pd.read_sql_query(query, conn)

        # Transpose the DataFrame if transpose is True
        if transpose or transpose_by:
            df = pd.DataFrame(df)
            if transpose_by:
                df = df.set_index(transpose_by)
            else:
                df = df.set_index(df.columns[0])
            df = df.transpose()
        from edsl.results.Dataset import Dataset

        return Dataset.from_pandas_dataframe(df)

    def to_pandas(
        self, remove_prefix: bool = False, lists_as_strings=False
    ) -> "DataFrame":
        """Convert the results to a pandas DataFrame, ensuring that lists remain as lists.

        :param remove_prefix: Whether to remove the prefix from the column names.

        """
        return self._to_pandas_strings(remove_prefix)

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

        csv_string = self.to_csv(remove_prefix=remove_prefix).text
        csv_buffer = io.StringIO(csv_string)
        df = pd.read_csv(csv_buffer)
        # df_sorted = df.sort_index(axis=1)  # Sort columns alphabetically
        return df

    def to_polars(
        self, remove_prefix: bool = False, lists_as_strings=False
    ) -> "pl.DataFrame":
        """Convert the results to a Polars DataFrame.

        :param remove_prefix: Whether to remove the prefix from the column names.
        """
        return self._to_polars_strings(remove_prefix)

    def _to_polars_strings(self, remove_prefix: bool = False) -> "pl.DataFrame":
        """Convert the results to a Polars DataFrame.

        :param remove_prefix: Whether to remove the prefix from the column names.
        """
        import polars as pl

        csv_string = self.to_csv(remove_prefix=remove_prefix).text
        df = pl.read_csv(io.StringIO(csv_string))
        return df

    def to_scenario_list(self, remove_prefix: bool = True) -> list[dict]:
        """Convert the results to a list of dictionaries, one per scenario.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_scenario_list()
        ScenarioList([Scenario({'how_feeling': 'OK'}), Scenario({'how_feeling': 'Great'}), Scenario({'how_feeling': 'Terrible'}), Scenario({'how_feeling': 'OK'})])
        """
        from edsl.scenarios.ScenarioList import ScenarioList
        from edsl.scenarios.Scenario import Scenario

        list_of_dicts = self.to_dicts(remove_prefix=remove_prefix)
        scenarios = []
        for d in list_of_dicts:
            scenarios.append(Scenario(d))
        return ScenarioList(scenarios)

    def to_agent_list(self, remove_prefix: bool = True):
        """Convert the results to a list of dictionaries, one per agent.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').to_agent_list()
        AgentList([Agent(traits = {'how_feeling': 'OK'}), Agent(traits = {'how_feeling': 'Great'}), Agent(traits = {'how_feeling': 'Terrible'}), Agent(traits = {'how_feeling': 'OK'})])
        """
        from edsl.agents import Agent
        from edsl.agents.AgentList import AgentList

        list_of_dicts = self.to_dicts(remove_prefix=remove_prefix)
        agents = []
        for d in list_of_dicts:
            if "name" in d:
                d["agent_name"] = d.pop("name")
                agents.append(Agent(d, name=d["agent_name"]))
            if "agent_parameters" in d:
                agent_parameters = d.pop("agent_parameters")
                agent_name = agent_parameters.get("name", None)
                instruction = agent_parameters.get("instruction", None)
                agents.append(Agent(d, name=agent_name, instruction=instruction))
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

        from edsl.utilities.PrettyList import PrettyList

        return PrettyList(list_to_return)

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
        >>> from edsl.results.Dataset import Dataset
        >>> expected = Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible']}, {'count': [2, 1, 1]}])
        >>> r.select('how_feeling').tally('answer.how_feeling', output = "Dataset") == expected
        True
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
