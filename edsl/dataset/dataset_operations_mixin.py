"""Mixin class for exporting results."""

from abc import ABC, abstractmethod
import io
import warnings
import textwrap
from typing import Optional, Tuple, Union, List, TYPE_CHECKING
from .r.ggplot import GGPlotMethod

if TYPE_CHECKING:
    from docx import Document
    from .dataset import Dataset

class DataOperationsBase:
    """Mixin class for exporting Dataset objects."""


    def ggplot2(
        self,
        ggplot_code: str,
        shape="wide",
        sql: str = None,
        remove_prefix: bool = True,
        debug: bool = False,
        height=4,
        width=6,
        factor_orders: Optional[dict] = None,
    ):
        return GGPlotMethod(self).ggplot2(ggplot_code, shape, sql, remove_prefix, debug, height, width, factor_orders)


    def relevant_columns(
        self, data_type: Optional[str] = None, remove_prefix:bool=False
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
                        f"The number of observations is not consistent across columns. "
                        f"Column '{key}' has {len(values)} observations, but previous columns had {_num_observations} observations."
                    )

        return _num_observations

    def make_tabular(
        self, remove_prefix: bool, pretty_labels: Optional[dict] = None
    ) -> tuple[list, List[list]]:
        """Turn the results into a tabular format.

        :param remove_prefix: Whether to remove the prefix from the column names.

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r.select('how_feeling').make_tabular(remove_prefix = True)
        (['how_feeling'], [['OK'], ['Great'], ['Terrible'], ['OK']])

        >>> r.select('how_feeling').make_tabular(remove_prefix = True, pretty_labels = {'how_feeling': "How are you feeling"})
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

    def get_tabular_data(
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

        return self.make_tabular(
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
        from .file_exports import CSVExport

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
        from .file_exports import  ExcelExport

        exporter = ExcelExport(
            data=self,
            filename=filename,
            remove_prefix=remove_prefix,
            pretty_labels=pretty_labels,
            sheet_name=sheet_name,
        )
        return exporter.export()

    def _db(
        self, remove_prefix: bool = True, shape: str = "wide"
    ) -> "sqlalchemy.engine.Engine":
        """Create a SQLite database in memory and return the connection.

        Args:
            remove_prefix: Whether to remove the prefix from the column names
            shape: The shape of the data in the database ("wide" or "long")

        Returns:
            A database connection
        >>> from sqlalchemy import text
        >>> from edsl import Results
        >>> engine = Results.example()._db()
        >>> len(engine.execute(text("SELECT * FROM self")).fetchall())
        4
        >>> engine = Results.example()._db(shape = "long")
        >>> len(engine.execute(text("SELECT * FROM self")).fetchall())
        172
        """
        from sqlalchemy import create_engine, text

        engine = create_engine("sqlite:///:memory:")
        if remove_prefix and shape == "wide":
            df = self.remove_prefix().to_pandas(lists_as_strings=True)
        else:
            df = self.to_pandas(lists_as_strings=True)

        if shape == "long":
            # Melt the dataframe to convert it to long format
            df = df.melt(var_name="key", value_name="value")
            # Add a row number column for reference
            df.insert(0, "row_number", range(1, len(df) + 1))

            # Split the key into data_type and key
            df["data_type"] = df["key"].apply(
                lambda x: x.split(".")[0] if "." in x else None
            )
            df["key"] = df["key"].apply(
                lambda x: ".".join(x.split(".")[1:]) if "." in x else x
            )

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
        shape: str = "wide",
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

        Examples:
            >>> from edsl import Results
            >>> r = Results.example();
            >>> len(r.sql("SELECT * FROM self", shape = "wide"))
            4
            >>> len(r.sql("SELECT * FROM self", shape = "long"))
            172
        """
        import pandas as pd

        conn = self._db(remove_prefix=remove_prefix, shape=shape)
        df = pd.read_sql_query(query, conn)

        # Transpose the DataFrame if transpose is True
        if transpose or transpose_by:
            df = pd.DataFrame(df)
            if transpose_by:
                df = df.set_index(transpose_by)
            else:
                df = df.set_index(df.columns[0])
            df = df.transpose()
        from .dataset import Dataset

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
        from edsl.scenarios import ScenarioList, Scenario

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
        from edsl.agents import Agent, AgentList

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

        #return PrettyList(list_to_return)
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
        
    def _prepare_report_data(self, *fields: Optional[str], top_n: Optional[int] = None, 
                            header_fields: Optional[List[str]] = None) -> tuple:
        """Prepares data for report generation in various formats.
        
        Args:
            *fields: The fields to include in the report. If none provided, all fields are used.
            top_n: Optional limit on the number of observations to include.
            header_fields: Optional list of fields to include in the main header instead of as sections.
            
        Returns:
            A tuple containing (field_data, num_obs, fields, header_fields)
        """
        # If no fields specified, use all columns
        if not fields:
            fields = self.relevant_columns()
        
        # Initialize header_fields if not provided
        if header_fields is None:
            header_fields = []
        
        # Validate all fields
        all_fields = list(fields) + [f for f in header_fields if f not in fields]
        for field in all_fields:
            if field not in self.relevant_columns():
                raise ValueError(f"Field '{field}' not found in dataset")
        
        # Get data for each field
        field_data = {}
        for field in all_fields:
            for entry in self:
                if field in entry:
                    field_data[field] = entry[field]
                    break
        
        # Number of observations to process
        num_obs = self.num_observations()
        if top_n is not None:
            num_obs = min(num_obs, top_n)
            
        return field_data, num_obs, fields, header_fields

    def _report_markdown(self, field_data, num_obs, fields, header_fields, divider: bool = True) -> str:
        """Generates a markdown report from the prepared data.
        
        Args:
            field_data: Dictionary mapping field names to their values
            num_obs: Number of observations to include
            fields: Fields to include as sections
            header_fields: Fields to include in the observation header
            divider: If True, adds a horizontal rule between observations
            
        Returns:
            A string containing the markdown report
        """
        report_lines = []
        for i in range(num_obs):
            # Create header with observation number and any header fields
            header = f"# Observation: {i+1}"
            if header_fields:
                header_parts = []
                for field in header_fields:
                    value = field_data[field][i]
                    # Get the field name without prefix for cleaner display
                    display_name = field.split('.')[-1] if '.' in field else field
                    # Format with backticks for monospace
                    header_parts.append(f"`{display_name}`: {value}")
                if header_parts:
                    header += f" ({', '.join(header_parts)})"
            report_lines.append(header)
            
            # Add the remaining fields
            for field in fields:
                if field not in header_fields:
                    report_lines.append(f"## {field}")
                    value = field_data[field][i]
                    if isinstance(value, list) or isinstance(value, dict):
                        import json
                        report_lines.append(f"```\n{json.dumps(value, indent=2)}\n```")
                    else:
                        report_lines.append(str(value))
            
            # Add divider between observations if requested
            if divider and i < num_obs - 1:
                report_lines.append("\n---\n")
            else:
                report_lines.append("")  # Empty line between observations
        
        return "\n".join(report_lines)

    def _report_docx(self, field_data, num_obs, fields, header_fields) -> "Document":
        """Generates a Word document report from the prepared data.
        
        Args:
            field_data: Dictionary mapping field names to their values
            num_obs: Number of observations to include
            fields: Fields to include as sections
            header_fields: Fields to include in the observation header
            
        Returns:
            A docx.Document object containing the report
        """
        try:
            from docx import Document
            from docx.shared import Pt
            import json
        except ImportError:
            raise ImportError("The python-docx package is required for DOCX export. Install it with 'pip install python-docx'.")
        
        doc = Document()
        
        for i in range(num_obs):
            # Create header with observation number and any header fields
            header_text = f"Observation: {i+1}"
            if header_fields:
                header_parts = []
                for field in header_fields:
                    value = field_data[field][i]
                    # Get the field name without prefix for cleaner display
                    display_name = field.split('.')[-1] if '.' in field else field
                    header_parts.append(f"{display_name}: {value}")
                if header_parts:
                    header_text += f" ({', '.join(header_parts)})"
            
            heading = doc.add_heading(header_text, level=1)
            
            # Add the remaining fields
            for field in fields:
                if field not in header_fields:
                    doc.add_heading(field, level=2)
                    value = field_data[field][i]
                    
                    if isinstance(value, (list, dict)):
                        # Format structured data with indentation
                        formatted_value = json.dumps(value, indent=2)
                        p = doc.add_paragraph()
                        p.add_run(formatted_value).font.name = 'Courier New'
                        p.add_run().font.size = Pt(10)
                    else:
                        doc.add_paragraph(str(value))
            
            # Add page break between observations except for the last one
            if i < num_obs - 1:
                doc.add_page_break()
        
        return doc
        
    def report(self, *fields: Optional[str], top_n: Optional[int] = None, 
               header_fields: Optional[List[str]] = None, divider: bool = True,
               return_string: bool = False, format: str = "markdown",
               filename: Optional[str] = None) -> Optional[Union[str, "docx.Document"]]:
        """Generates a report of the results by iterating through rows.
        
        Args:
            *fields: The fields to include in the report. If none provided, all fields are used.
            top_n: Optional limit on the number of observations to include.
            header_fields: Optional list of fields to include in the main header instead of as sections.
            divider: If True, adds a horizontal rule between observations (markdown only).
            return_string: If True, returns the markdown string. If False (default in notebooks),
                          only displays the markdown without returning.
            format: Output format - either "markdown" or "docx".
            filename: If provided and format is "docx", saves the document to this file.
            
        Returns:
            Depending on format and return_string:
            - For markdown: A string if return_string is True, otherwise None (displays in notebook)
            - For docx: A docx.Document object, or None if filename is provided (saves to file)
            
        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> report = r.select('how_feeling').report(return_string=True)
            >>> "# Observation: 1" in report
            True
            >>> doc = r.select('how_feeling').report(format="docx")
            >>> isinstance(doc, object)
            True
        """
        from edsl.utilities.utilities import is_notebook
        
        # Prepare the data for the report
        field_data, num_obs, fields, header_fields = self._prepare_report_data(
            *fields, top_n=top_n, header_fields=header_fields
        )
        
        # Generate the report in the requested format
        if format.lower() == "markdown":
            report_text = self._report_markdown(
                field_data, num_obs, fields, header_fields, divider
            )
            
            # In notebooks, display as markdown
            is_nb = is_notebook()
            if is_nb and not return_string:
                from IPython.display import Markdown, display
                display(Markdown(report_text))
                return None
            
            # Return the string if requested or if not in a notebook
            return report_text
            
        elif format.lower() == "docx":
            doc = self._report_docx(field_data, num_obs, fields, header_fields)
            
            # Save to file if filename is provided
            if filename:
                doc.save(filename)
                print(f"Report saved to {filename}")
                return None
                
            return doc
            
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'markdown' or 'docx'.")

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
            raise ValueError("One or more specified fields are not in the dataset."
                             f"The available fields are: {self.relevant_columns()}"
                             )

        if len(fields) == 1:
            field = fields[0]
            values = self._key_to_value(field)
        else:
            values = list(zip(*(self._key_to_value(field) for field in fields)))

        for value in values:
            if isinstance(value, list):
                value = tuple(value)
        try:
            tally = dict(Counter(values))
        except TypeError:
            tally = dict(Counter([str(v) for v in values]))
        except Exception as e:
            raise ValueError(f"Error tallying values: {e}")
        
        sorted_tally = dict(sorted(tally.items(), key=lambda item: -item[1]))
        if top_n is not None:
            sorted_tally = dict(list(sorted_tally.items())[:top_n])

        from ..dataset import Dataset

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

    def flatten(self, field:str, keep_original=False):
        """
        Flatten a field containing a list of dictionaries into separate fields.

        >>> from edsl.results.Dataset import Dataset
        >>> Dataset([{'a': [{'a': 1, 'b': 2}]}, {'c': [5] }]).flatten('a')
        Dataset([{'c': [5]}, {'a.a': [1]}, {'a.b': [2]}])


        >>> Dataset([{'answer.example': [{'a': 1, 'b': 2}]}, {'c': [5] }]).flatten('answer.example')
        Dataset([{'c': [5]}, {'answer.example.a': [1]}, {'answer.example.b': [2]}])


        Args:
            field: The field to flatten
            keep_original: If True, keeps the original field in the dataset

        Returns:
            A new dataset with the flattened fields
        """
        from edsl.results.Dataset import Dataset

        # Ensure the dataset isn't empty
        if not self.data:
            return self.copy()
        
        # Find all columns that contain the field
        matching_entries = []
        for entry in self.data:
            col_name = next(iter(entry.keys()))
            if field == col_name or (
                '.' in col_name and 
                (col_name.endswith('.' + field) or col_name.startswith(field + '.'))
            ):
                matching_entries.append(entry)
        
        # Check if the field is ambiguous
        if len(matching_entries) > 1:
            matching_cols = [next(iter(entry.keys())) for entry in matching_entries]
            raise ValueError(
                f"Ambiguous field name '{field}'. It matches multiple columns: {matching_cols}. "
                f"Please specify the full column name to flatten."
            )

        # Get the number of observations
        num_observations = self.num_observations()

        # Find the column to flatten
        field_entry = None
        for entry in self.data:
            if field in entry:
                field_entry = entry
                break

        if field_entry is None:
            warnings.warn(
                f"Field '{field}' not found in dataset, returning original dataset"
            )
            return self.copy()

        # Create new dictionary for flattened data
        flattened_data = []

        # Copy all existing columns except the one we're flattening (if keep_original is False)
        for entry in self.data:
            col_name = next(iter(entry.keys()))
            if col_name != field or keep_original:
                flattened_data.append(entry.copy())

        # Get field data and make sure it's valid
        field_values = field_entry[field]
        if not all(isinstance(item, dict) for item in field_values if item is not None):
            warnings.warn(
                f"Field '{field}' contains non-dictionary values that cannot be flattened"
            )
            return self.copy()

        # Collect all unique keys across all dictionaries
        all_keys = set()
        for item in field_values:
            if isinstance(item, dict):
                all_keys.update(item.keys())

        # Create new columns for each key
        for key in sorted(all_keys):  # Sort for consistent output
            new_values = []
            for i in range(num_observations):
                value = None
                if i < len(field_values) and isinstance(field_values[i], dict):
                    value = field_values[i].get(key, None)
                new_values.append(value)

            # Add this as a new column
            flattened_data.append({f"{field}.{key}": new_values})

        # Return a new Dataset with the flattened data
        return Dataset(flattened_data)

    def unpack_list(
        self,
        field: str,
        new_names: Optional[List[str]] = None,
        keep_original: bool = True,
    ) -> "Dataset":
        """Unpack list columns into separate columns with provided names or numeric suffixes.

        For example, if a dataset contains:
        [{'data': [[1, 2, 3], [4, 5, 6]], 'other': ['x', 'y']}]

        After d.unpack_list('data'), it should become:
        [{'other': ['x', 'y'], 'data_1': [1, 4], 'data_2': [2, 5], 'data_3': [3, 6]}]

        Args:
            field: The field containing lists to unpack
            new_names: Optional list of names for the unpacked fields. If None, uses numeric suffixes.
            keep_original: If True, keeps the original field in the dataset

        Returns:
            A new Dataset with unpacked columns

        Examples:
            >>> from edsl.results.Dataset import Dataset
            >>> d = Dataset([{'data': [[1, 2, 3], [4, 5, 6]]}])
            >>> d.unpack_list('data')
            Dataset([{'data': [[1, 2, 3], [4, 5, 6]]}, {'data_1': [1, 4]}, {'data_2': [2, 5]}, {'data_3': [3, 6]}])

            >>> d.unpack_list('data', new_names=['first', 'second', 'third'])
            Dataset([{'data': [[1, 2, 3], [4, 5, 6]]}, {'first': [1, 4]}, {'second': [2, 5]}, {'third': [3, 6]}])
        """
        from edsl.results.Dataset import Dataset

        # Create a copy of the dataset
        result = Dataset(self.data.copy())

        # Find the field in the dataset
        field_index = None
        for i, entry in enumerate(result.data):
            if field in entry:
                field_index = i
                break

        if field_index is None:
            raise ValueError(f"Field '{field}' not found in dataset")

        field_data = result.data[field_index][field]

        # Check if values are lists
        if not all(isinstance(v, list) for v in field_data):
            raise ValueError(f"Field '{field}' does not contain lists in all entries")

        # Get the maximum length of lists
        max_len = max(len(v) for v in field_data)

        # Create new fields for each index
        for i in range(max_len):
            if new_names and i < len(new_names):
                new_field = new_names[i]
            else:
                new_field = f"{field}_{i+1}"

            # Extract the i-th element from each list
            new_values = []
            for item in field_data:
                new_values.append(item[i] if i < len(item) else None)

            result.data.append({new_field: new_values})

        # Remove the original field if keep_original is False
        if not keep_original:
            result.data.pop(field_index)

        return result
    
    def drop(self, field_name):
        """
        Returns a new Dataset with the specified field removed.
        
        Args:
            field_name (str): The name of the field to remove.
            
        Returns:
            Dataset: A new Dataset instance without the specified field.
            
        Raises:
            KeyError: If the field_name doesn't exist in the dataset.
            
        Examples:
            >>> from edsl.results.Dataset import Dataset
            >>> d = Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])
            >>> d.drop('a')
            Dataset([{'b': [4, 5, 6]}])
            
            >>> d.drop('c')
            Traceback (most recent call last):
            ...
            KeyError: "Field 'c' not found in dataset"
        """
        from edsl.results.Dataset import Dataset
        
        # Check if field exists in the dataset
        if field_name not in self.relevant_columns():
            raise KeyError(f"Field '{field_name}' not found in dataset")
        
        # Create a new dataset without the specified field
        new_data = [entry for entry in self.data if field_name not in entry]
        return Dataset(new_data)

    def remove_prefix(self):
        """Returns a new Dataset with the prefix removed from all column names.
        
        The prefix is defined as everything before the first dot (.) in the column name.
        If removing prefixes would result in duplicate column names, an exception is raised.
        
        Returns:
            Dataset: A new Dataset with prefixes removed from column names
            
        Raises:
            ValueError: If removing prefixes would result in duplicate column names
            
        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> r.select('how_feeling', 'how_feeling_yesterday').relevant_columns()
            ['answer.how_feeling', 'answer.how_feeling_yesterday']
            >>> r.select('how_feeling', 'how_feeling_yesterday').remove_prefix().relevant_columns()
            ['how_feeling', 'how_feeling_yesterday']
            
            >>> from edsl.results.Dataset import Dataset
            >>> d = Dataset([{'a.x': [1, 2, 3]}, {'b.x': [4, 5, 6]}])
            >>> d.remove_prefix()
            Traceback (most recent call last):
            ...
            ValueError: Removing prefixes would result in duplicate column names: ['x']
        """
        from edsl.results.Dataset import Dataset
        
        # Get all column names
        columns = self.relevant_columns()
        
        # Extract the unprefixed names
        unprefixed = {}
        duplicates = set()
        
        for col in columns:
            if '.' in col:
                unprefixed_name = col.split('.', 1)[1]
                if unprefixed_name in unprefixed:
                    duplicates.add(unprefixed_name)
                unprefixed[unprefixed_name] = col
            else:
                # For columns without a prefix, keep them as is
                unprefixed[col] = col
        
        # Check for duplicates
        if duplicates:
            raise ValueError(f"Removing prefixes would result in duplicate column names: {sorted(list(duplicates))}")
        
        # Create a new dataset with unprefixed column names
        new_data = []
        for entry in self.data:
            key, values = list(entry.items())[0]
            if '.' in key:
                new_key = key.split('.', 1)[1]
            else:
                new_key = key
            new_data.append({new_key: values})
        
        return Dataset(new_data)


from functools import wraps

def to_dataset(func):
    """Convert the Results object to a Dataset object before calling the function."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        """Return the function with the Results object converted to a Dataset object."""
        # Convert to Dataset first
        if self.__class__.__name__ == "Results":
            dataset_self = self.select()
        elif self.__class__.__name__ == "AgentList":
            dataset_self = self.to_dataset()
        elif self.__class__.__name__ == "ScenarioList":
            dataset_self = self.to_dataset()
        else:
            dataset_self = self
            
        # Now call the function with the converted self
        return func(dataset_self, *args, **kwargs)

    wrapper._is_wrapped = True
    return wrapper

def decorate_methods_from_mixin(cls, mixin_cls):
    """Decorates all methods from mixin_cls with to_dataset decorator."""
    
    # Get all attributes, including inherited ones
    for attr_name in dir(mixin_cls):
        # Skip magic methods and private methods
        if not attr_name.startswith('_'):
            attr_value = getattr(mixin_cls, attr_name)
            if callable(attr_value):
                setattr(cls, attr_name, to_dataset(attr_value))
    return cls

class DatasetOperationsMixin(DataOperationsBase):
    pass

class ResultsOperationsMixin(DataOperationsBase):
    """Mixin class for exporting Results objects."""
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        decorate_methods_from_mixin(cls, DatasetOperationsMixin)

class ScenarioListOperationsMixin(DataOperationsBase):
    """Mixin class for ScenarioList objects."""
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        decorate_methods_from_mixin(cls, DatasetOperationsMixin)

class AgentListOperationsMixin(DataOperationsBase):
    """Mixin class for AgentList objects."""
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        decorate_methods_from_mixin(cls, DatasetOperationsMixin)

if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
