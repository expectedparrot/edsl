"""
ScenarioSource provides factory methods for creating ScenarioList objects from external sources.

This module contains the ScenarioSource class, which serves as a factory for creating
ScenarioList objects from various external data sources like files, directories, and URLs.
It centralizes all the file/external-source creation logic that was previously scattered
across different classmethods in the ScenarioList class.

Key features include:
- A unified from_source method that dispatches to appropriate source-specific methods
- Support for various data sources (CSV, Excel, PDF, directories, URLs, etc.)
- Deprecation decorators for backward compatibility with ScenarioList class methods
"""

from __future__ import annotations
import functools
import warnings
import fnmatch
from collections import defaultdict
import warnings
from typing import (
    Any,
    Callable,
    List,
    Literal,
    Optional,
    Type,
    TypeVar,
    Union,
    TYPE_CHECKING,
    cast,
    Any,
)

T = TypeVar("T")


def deprecated_classmethod(
    alternative: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that marks a class method as deprecated.

    Args:
        alternative: The suggested alternative to use instead

    Returns:
        A decorator function that wraps the original method with a deprecation warning
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            warnings.warn(
                f"{func.__qualname__} is deprecated. Use {alternative} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator


import os
import csv
import json
import warnings
from io import StringIO
from urllib.parse import urlparse

if TYPE_CHECKING:
    import pandas as pd
    from urllib.parse import ParseResult
    from .scenario_list import ScenarioList

# Local imports
from .scenario import Scenario
from .directory_scanner import DirectoryScanner
from .exceptions import ScenarioError

from abc import ABC, abstractmethod


class Source(ABC):
    # Registry to store child classes and their source types
    _registry: dict[str, Type["Source"]] = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses with their source_type."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "source_type"):
            Source._registry[cls.source_type] = cls

    @classmethod
    @abstractmethod
    def example(cls) -> "Source":
        """
        Return an example instance of this Source type.

        This method should return a valid instance of the Source subclass
        that can be used for testing. The instance should be created with
        reasonable default values that will produce a valid ScenarioList
        when to_scenario_list() is called.

        Returns:
            An instance of the Source subclass
        """
        pass

    @abstractmethod
    def to_scenario_list(self):
        """
        Convert the source to a ScenarioList.

        Returns:
            A ScenarioList containing the data from this source
        """
        pass

    @classmethod
    def get_source_class(cls, source_type: str) -> Type["Source"]:
        """Get the Source subclass for a given source_type."""
        if source_type not in cls._registry:
            raise ValueError(f"No Source subclass found for source_type: {source_type}")
        return cls._registry[source_type]

    @classmethod
    def get_registered_types(cls) -> list[str]:
        """Get a list of all registered source types."""
        return list(cls._registry.keys())

    @classmethod
    def test_all_sources(cls) -> dict[str, bool]:
        """
        Test all registered source types by creating an example instance
        and calling to_scenario_list() on it.

        Returns:
            A dictionary mapping source types to boolean success values
        """
        from .scenario_list import ScenarioList

        results = {}
        for source_type, source_class in cls._registry.items():
            try:
                # Create example instance
                example_instance = source_class.example()
                # Convert to scenario list
                scenario_list = example_instance.to_scenario_list()
                # Basic validation
                if not isinstance(scenario_list, ScenarioList):
                    results[source_type] = False
                    print(
                        f"Source {source_type} returned {type(scenario_list)} instead of ScenarioList"
                    )
                else:
                    results[source_type] = True
            except Exception as e:
                results[source_type] = False
                print(f"Source {source_type} exception: {e}")
        return results


class URLSource(Source):
    source_type = "urls"

    def __init__(self, urls: list[str], field_name: str):
        self.urls = urls
        self.field_name = field_name

    @classmethod
    def example(cls) -> "URLSource":
        """Return an example URLSource instance."""
        return cls(urls=["http://www.example.com"], field_name="text")

    def to_scenario_list(self):
        """Create a ScenarioList from a list of URLs."""
        import requests

        from .scenario_list import ScenarioList

        result = ScenarioList()
        for url in self.urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                scenario = Scenario({self.field_name: response.text})
                result.append(scenario)
            except requests.RequestException as e:
                warnings.warn(f"Failed to fetch URL {url}: {str(e)}")
                continue

        return result


class ListSource(Source):
    source_type = "list"

    def __init__(self, field_name: str, values: list, use_indexes: bool = False):
        self.field_name = field_name
        self.values = values
        self.use_indexes = use_indexes

    @classmethod
    def example(cls) -> "ListSource":
        """Return an example ListSource instance."""
        return cls(
            field_name="text",
            values=["example1", "example2", "example3"],
            use_indexes=True,
        )

    def to_scenario_list(self):
        """Create a ScenarioList from a list of values with a specified field name."""
        from .scenario_list import ScenarioList

        scenarios = []

        for i, value in enumerate(self.values):
            scenario_dict = {self.field_name: value}
            if self.use_indexes:
                scenario_dict["idx"] = i
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)


class DirectorySource(Source):
    source_type = "directory"

    def __init__(
        self,
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
        metadata: bool = True,
        ignore_dirs: List[str] = None,
        ignore_files: List[str] = None,
    ):
        self.directory = directory
        self.pattern = pattern
        self.recursive = recursive
        self.metadata = metadata
        self.ignore_dirs = ignore_dirs or []
        self.ignore_files = ignore_files or []

    @classmethod
    def example(cls) -> "DirectorySource":
        """Return an example DirectorySource instance."""
        import tempfile
        import os

        # Create a temporary directory for the example
        temp_dir = tempfile.mkdtemp(prefix="edsl_test_")

        # Create some sample files in the directory
        with open(os.path.join(temp_dir, "test1.txt"), "w") as f:
            f.write("Sample content 1")

        with open(os.path.join(temp_dir, "test2.txt"), "w") as f:
            f.write("Sample content 2")

        # Create a subdirectory with a file
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, "test3.txt"), "w") as f:
            f.write("Sample content 3")

        return cls(
            directory=temp_dir,
            pattern="*.txt",
            recursive=True,
            metadata=True,
            ignore_dirs=["__pycache__"],
            ignore_files=["*.pyc"],
        )

    def to_scenario_list(self):
        """Create a ScenarioList from files in a directory."""
        import os
        import glob

        from .scenario_list import ScenarioList

        # Set default recursive value
        recursive = self.recursive

        # Handle paths with wildcards properly
        if "*" in self.directory:
            # Handle "**/*.py" patterns (recursive wildcard)
            if "**" in self.directory:
                parts = self.directory.split("**")
                directory = parts[0].rstrip("/\\")
                if not directory:
                    directory = os.getcwd()
                pattern = f"**{parts[1]}" if len(parts) > 1 else "**/*"
                # Force recursive=True for ** patterns
                recursive = True
            # Handle "*.txt" patterns (just wildcard with no directory)
            elif os.path.dirname(self.directory) == "":
                directory = os.getcwd()
                pattern = self.directory
            # Handle "/path/to/dir/*.py" patterns
            else:
                directory = os.path.dirname(self.directory)
                pattern = os.path.basename(self.directory)
        else:
            directory = self.directory
            pattern = self.pattern

        # Check if directory exists
        if not os.path.isdir(directory):
            from .exceptions import FileNotFoundScenarioError

            raise FileNotFoundScenarioError(f"Directory not found: {directory}")

        # Use glob directly for ** patterns to prevent duplicates
        if "**" in pattern:
            from .scenario_list import ScenarioList
            from .file_store import FileStore

            # Handle the pattern directly with glob
            full_pattern = os.path.join(directory, pattern)
            file_paths = glob.glob(full_pattern, recursive=True)

            # Remove duplicates (by converting to a set and back)
            file_paths = list(set(file_paths))

            # Create scenarios
            scenarios = []
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    # Check if file should be ignored
                    file_name = os.path.basename(file_path)
                    if any(
                        fnmatch.fnmatch(file_name, ignore_pattern)
                        for ignore_pattern in self.ignore_files or []
                    ):
                        continue

                    # Create FileStore object
                    file_store = FileStore(file_path)

                    # Create scenario
                    scenario_data = {"file": file_store}

                    # Add metadata if requested
                    if self.metadata:
                        file_stat = os.stat(file_path)
                        scenario_data.update(
                            {
                                "file_path": file_path,
                                "file_name": file_name,
                                "file_size": file_stat.st_size,
                                "file_created": file_stat.st_ctime,
                                "file_modified": file_stat.st_mtime,
                            }
                        )

                    scenarios.append(Scenario(scenario_data))

            return ScenarioList(scenarios)
        else:
            # Use the standard scanning method for non-** patterns
            return DirectoryScanner.scan_directory(
                directory=directory,
                pattern=pattern,
                recursive=recursive,
                metadata=self.metadata,
                ignore_dirs=self.ignore_dirs,
                ignore_files=self.ignore_files,
            )


class TuplesSource(Source):
    source_type = "list_of_tuples"

    def __init__(
        self, field_names: list[str], values: list[tuple], use_indexes: bool = False
    ):
        self.field_names = field_names
        self.values = values
        self.use_indexes = use_indexes

        # Validate inputs
        if not all(isinstance(v, (tuple, list)) for v in values):
            raise ScenarioError("All values must be tuples or lists")

    @classmethod
    def example(cls) -> "TuplesSource":
        """Return an example TuplesSource instance."""
        return cls(
            field_names=["name", "age", "city"],
            values=[
                ("Alice", 30, "New York"),
                ("Bob", 25, "San Francisco"),
                ("Charlie", 35, "Boston"),
            ],
            use_indexes=True,
        )

    def to_scenario_list(self):
        """Create a ScenarioList from a list of tuples with specified field names."""
        from .scenario_list import ScenarioList

        scenarios = []

        for i, value_tuple in enumerate(self.values):
            if len(value_tuple) != len(self.field_names):
                raise ScenarioError(
                    f"Tuple {i} has {len(value_tuple)} elements, but {len(self.field_names)} field names were provided."
                )

            scenario_dict = dict(zip(self.field_names, value_tuple))
            if self.use_indexes:
                scenario_dict["idx"] = i
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)


class SQLiteSource(Source):
    source_type = "sqlite"

    def __init__(self, db_path: str, table: str, fields: Optional[list] = None):
        self.db_path = db_path
        self.table = table
        self.fields = fields

    @classmethod
    def example(cls) -> "SQLiteSource":
        """Return an example SQLiteSource instance."""
        import sqlite3
        import tempfile
        import os

        # Create a temporary SQLite database for the example
        fd, temp_path = tempfile.mkstemp(suffix=".db", prefix="edsl_test_")
        os.close(fd)  # Close the file descriptor

        # Connect to the database and create a sample table
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()

        # Create a simple table
        cursor.execute(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)"
        )

        # Insert sample data
        sample_data = [(1, "Alpha", 100), (2, "Beta", 200), (3, "Gamma", 300)]
        cursor.executemany("INSERT INTO test_table VALUES (?, ?, ?)", sample_data)

        conn.commit()
        conn.close()

        return cls(
            db_path=temp_path, table="test_table", fields=["id", "name", "value"]
        )

    def to_scenario_list(self):
        """Create a ScenarioList from a SQLite database."""
        from .scenario_list import ScenarioList
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # If fields weren't provided, get all fields from the table
        fields = self.fields
        if fields is None:
            cursor.execute(f"PRAGMA table_info({self.table})")
            fields = [row[1] for row in cursor.fetchall()]

        # Query the data
        field_placeholders = ", ".join(fields)
        cursor.execute(f"SELECT {field_placeholders} FROM {self.table}")
        rows = cursor.fetchall()

        # Create scenarios
        scenarios = []
        for row in rows:
            scenario_dict = dict(zip(fields, row))
            scenarios.append(Scenario(scenario_dict))

        conn.close()
        return ScenarioList(scenarios)


class LaTeXSource(Source):
    source_type = "latex"

    def __init__(self, file_path: str, table_index: int = 0, has_header: bool = True):
        """
        Initialize a LaTeXSource with a LaTeX file path.

        Args:
            file_path: The path to the LaTeX file.
            table_index: The index of the table to extract (if multiple tables exist).
                Default is 0 (first table).
            has_header: Whether the table has a header row. Default is True.
        """
        self.file_path = file_path
        self.table_index = table_index
        self.has_header = has_header

    @classmethod
    def example(cls) -> "LaTeXSource":
        """Return an example LaTeXSource instance."""
        import tempfile
        import os

        # Create a temporary LaTeX file with a sample table
        fd, temp_path = tempfile.mkstemp(suffix=".tex", prefix="edsl_test_")
        os.close(fd)  # Close the file descriptor

        # Write a sample LaTeX table to the file
        sample_latex = r"""
\documentclass{article}
\begin{document}
This is a sample document with a table:

\begin{tabular}{lrr}
\textbf{Name} & \textbf{Age} & \textbf{Score} \\
Alice & 30 & 95 \\
Bob & 25 & 87 \\
Charlie & 35 & 92 \\
\end{tabular}

\end{document}
"""
        with open(temp_path, "w") as f:
            f.write(sample_latex)

        return cls(file_path=temp_path, table_index=0, has_header=True)

    def to_scenario_list(self):
        """Create a ScenarioList from a LaTeX file."""
        from .scenario_list import ScenarioList
        import re

        with open(self.file_path, "r") as f:
            content = f.read()

        # Find all tabular environments
        tabular_pattern = r"\\begin{tabular}(.*?)\\end{tabular}"
        tables = re.findall(tabular_pattern, content, re.DOTALL)

        if not tables or self.table_index >= len(tables):
            raise ScenarioError(f"No table found at index {self.table_index}")

        table_content = tables[self.table_index]

        # Extract rows
        rows = table_content.split("\\\\")
        rows = [row.strip() for row in rows if row.strip()]

        if not rows:
            return ScenarioList()

        # Process header if available
        if self.has_header:
            header_row = rows[0]
            header_cells = re.findall(r"\\textbf{(.*?)}", header_row)
            if not header_cells:
                header_cells = header_row.split("&")
                header_cells = [h.strip() for h in header_cells]

            data_rows = rows[1:]
        else:
            # Auto-generate column names
            header_cells = [f"col{i}" for i in range(rows[0].count("&") + 1)]
            data_rows = rows

        # Process data rows
        scenarios = []
        for row in data_rows:
            cells = row.split("&")
            cells = [cell.strip() for cell in cells]

            if len(cells) != len(header_cells):
                continue  # Skip malformed rows

            scenario_dict = dict(zip(header_cells, cells))
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)


class GoogleDocSource(Source):
    source_type = "google_doc"

    def __init__(self, url: str):
        """
        Initialize a GoogleDocSource with a Google Doc URL.

        Args:
            url: The URL to the Google Doc.
        """
        self.url = url

    @classmethod
    def example(cls) -> "GoogleDocSource":
        """Return an example GoogleDocSource instance."""
        # Create a mock instance that doesn't actually fetch a Google Doc
        instance = cls(
            url="https://docs.google.com/document/d/1234567890abcdefghijklmnopqrstuvwxyz/edit"
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from .scenario_list import ScenarioList

            # Create a simple mock ScenarioList with a few paragraphs
            scenarios = [
                Scenario({"text": "This is paragraph 1 from a sample Google Doc."}),
                Scenario({"text": "This is paragraph 2 with some more content."}),
                Scenario({"text": "This is the final paragraph with a conclusion."}),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Google Doc."""
        from .scenario_list import ScenarioList
        import tempfile
        import requests

        # Extract the document ID from the URL
        if "/edit" in self.url:
            doc_id = self.url.split("/d/")[1].split("/edit")[0]
        else:
            raise ScenarioError("Invalid Google Doc URL format.")

        # Create the export URL to download as DOCX
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"

        try:
            # Download the Google Doc as a Word file (.docx)
            response = requests.get(export_url)
            response.raise_for_status()  # Ensure the request was successful

            # Save the Word file to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_filename = temp_file.name

            # Use the DocxScenario class to process the temporary file
            from .scenario_list import ScenarioList
            from .DocxScenario import DocxScenario

            # Create a scenario from the DOCX file
            docx_scenario = DocxScenario(temp_filename)
            scenarios = [
                Scenario({"text": paragraph.text}) for paragraph in docx_scenario.doc.paragraphs
            ]

            return ScenarioList(scenarios)

        except requests.RequestException as e:
            raise ScenarioError(f"Failed to fetch Google Doc: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"Error processing Google Doc: {str(e)}")


class PandasSource(Source):
    source_type = "pandas"

    def __init__(self, df):
        """
        Initialize a PandasSource with a pandas DataFrame.

        Args:
            df: A pandas DataFrame.
        """
        try:
            import pandas as pd

            if not isinstance(df, pd.DataFrame):
                raise ScenarioError("Input must be a pandas DataFrame")
            self.df = df
        except ImportError:
            raise ImportError("pandas is required for PandasSource")

    @classmethod
    def example(cls) -> "PandasSource":
        """Return an example PandasSource instance."""
        try:
            import pandas as pd

            # Create a sample DataFrame for the example
            sample_data = {
                "name": ["Alice", "Bob", "Charlie", "David"],
                "age": [30, 25, 35, 28],
                "city": ["New York", "San Francisco", "Boston", "Seattle"],
            }
            df = pd.DataFrame(sample_data)

            return cls(df)
        except ImportError:
            # Create a mock instance that doesn't actually need pandas
            instance = cls.__new__(cls)

            # Override the to_scenario_list method just for the example
            def mock_to_scenario_list(self):
                from .scenario_list import ScenarioList

                # Create a simple mock ScenarioList
                scenarios = [
                    Scenario({"name": "Alice", "age": 30, "city": "New York"}),
                    Scenario({"name": "Bob", "age": 25, "city": "San Francisco"}),
                    Scenario({"name": "Charlie", "age": 35, "city": "Boston"}),
                    Scenario({"name": "David", "age": 28, "city": "Seattle"}),
                ]
                return ScenarioList(scenarios)

            # Replace the method on this instance only
            import types

            instance.to_scenario_list = types.MethodType(
                mock_to_scenario_list, instance
            )

            return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a pandas DataFrame."""
        from .scenario_list import ScenarioList

        # Convert DataFrame records to scenarios
        scenarios = []
        for _, row in self.df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)


class StataSource(Source):
    source_type = "dta"

    def __init__(self, file_path: str, include_metadata: bool = True):
        """
        Initialize a StataSource with a path to a Stata data file.

        Args:
            file_path: Path to the Stata (.dta) file.
            include_metadata: If True, extract and preserve variable labels and value labels
                            as additional metadata in the ScenarioList.
        """
        self.file_path = file_path
        self.include_metadata = include_metadata

    @classmethod
    def example(cls) -> "StataSource":
        """Return an example StataSource instance."""
        import tempfile
        import os

        # Since we can't easily create a real Stata file for testing,
        # we'll create a mock instance with an override
        instance = cls(file_path="/path/to/nonexistent/file.dta")

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from .scenario_list import ScenarioList

            # Create a simple mock ScenarioList with Stata-like data
            scenarios = [
                Scenario({"id": 1, "gender": 1, "income": 50000, "education": 2}),
                Scenario({"id": 2, "gender": 2, "income": 45000, "education": 3}),
                Scenario({"id": 3, "gender": 1, "income": 60000, "education": 4}),
            ]

            result = ScenarioList(scenarios)

            # Add metadata similar to what would be in a Stata file
            if self.include_metadata:
                result.codebook = {
                    "variable_labels": {
                        "gender": "Gender (1=Male, 2=Female)",
                        "income": "Annual income in USD",
                        "education": "Education level (1-4)",
                    },
                    "value_labels": {
                        "gender": {1: "Male", 2: "Female"},
                        "education": {
                            1: "High School",
                            2: "Associate",
                            3: "Bachelor",
                            4: "Graduate",
                        },
                    },
                }

            return result

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Stata data file."""
        from .scenario_list import ScenarioList

        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Stata files")

        # Read the Stata file with pandas
        df = pd.read_stata(self.file_path)

        # Create scenarios
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        # Create the basic ScenarioList
        result = ScenarioList(scenarios)

        # Extract and preserve metadata if requested
        if self.include_metadata:
            # Get variable labels (if any)
            variable_labels = {}
            if hasattr(df, "variable_labels") and df.variable_labels:
                variable_labels = df.variable_labels

            # Get value labels (if any)
            value_labels = {}
            if hasattr(df, "value_labels") and df.value_labels:
                value_labels = df.value_labels

            # Store the metadata in the ScenarioList's codebook
            if variable_labels or value_labels:
                result.codebook = {
                    "variable_labels": variable_labels,
                    "value_labels": value_labels,
                }

        return result


class WikipediaSource(Source):
    source_type = "wikipedia"

    def __init__(self, url: str, table_index: int = 0, header: bool = True):
        """
        Initialize a WikipediaSource with a URL to a Wikipedia page.

        Args:
            url: The URL of the Wikipedia page.
            table_index: The index of the table to extract (default is 0).
            header: Whether the table has a header row (default is True).
        """
        self.url = url
        self.table_index = table_index
        self.header = header

    @classmethod
    def example(cls) -> "WikipediaSource":
        """Return an example WikipediaSource instance."""
        # Use a real Wikipedia URL for the example, but we'll override the to_scenario_list method
        instance = cls(
            url="https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)",
            table_index=0,
            header=True,
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from .scenario_list import ScenarioList

            # Create a simple mock ScenarioList with GDP data
            scenarios = [
                Scenario(
                    {
                        "Rank": 1,
                        "Country": "United States",
                        "GDP (millions of USD)": 25460000,
                    }
                ),
                Scenario(
                    {"Rank": 2, "Country": "China", "GDP (millions of USD)": 17963000}
                ),
                Scenario(
                    {"Rank": 3, "Country": "Japan", "GDP (millions of USD)": 4231000}
                ),
                Scenario(
                    {"Rank": 4, "Country": "Germany", "GDP (millions of USD)": 4430000}
                ),
                Scenario(
                    {"Rank": 5, "Country": "India", "GDP (millions of USD)": 3737000}
                ),
            ]

            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a table on a Wikipedia page."""
        from .scenario_list import ScenarioList
        import requests

        try:
            # Try to import pandas
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Wikipedia tables")

        try:
            # Check if the URL is reachable
            response = requests.get(self.url)
            response.raise_for_status()  # Raises HTTPError for bad responses

            # Extract tables from the Wikipedia page
            tables = pd.read_html(self.url, header=0 if self.header else None)

            # Ensure the requested table index is within the range of available tables
            if self.table_index >= len(tables) or self.table_index < 0:
                raise ScenarioError(
                    f"Table index {self.table_index} is out of range. This page has {len(tables)} table(s)."
                )

            # Get the requested table
            df = tables[self.table_index]

            # Convert DataFrame to ScenarioList
            scenarios = []
            for _, row in df.iterrows():
                scenario_dict = row.to_dict()
                scenarios.append(Scenario(scenario_dict))

            return ScenarioList(scenarios)

        except requests.exceptions.RequestException as e:
            raise ScenarioError(f"Error fetching the URL: {str(e)}")
        except ValueError as e:
            raise ScenarioError(f"Error parsing tables: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"An unexpected error occurred: {str(e)}")


class ExcelSource(Source):
    source_type = "excel"

    def __init__(
        self,
        file_path: str,
        sheet_name: Optional[str] = None,
        skip_rows: Optional[List[int]] = None,
        use_codebook: bool = False,
        **kwargs,
    ):
        """
        Initialize an ExcelSource with a path to an Excel file.

        Args:
            file_path: Path to the Excel file.
            sheet_name: Name of the sheet to load. If None and multiple sheets exist,
                        will raise an error listing available sheets.
            skip_rows: List of row indices to skip (0-based). If None, all rows are included.
            use_codebook: If True, rename columns to standard format and store original names in codebook.
            **kwargs: Additional parameters to pass to pandas.read_excel.
        """
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.skip_rows = skip_rows
        self.use_codebook = use_codebook
        self.kwargs = kwargs

    @classmethod
    def example(cls) -> "ExcelSource":
        """Return an example ExcelSource instance."""
        import tempfile
        import os

        try:
            import pandas as pd

            # Create a temporary Excel file with sample data
            fd, temp_path = tempfile.mkstemp(suffix=".xlsx", prefix="edsl_test_")
            os.close(fd)  # Close the file descriptor

            # Create sample data
            df1 = pd.DataFrame(
                {
                    "name": ["Alice", "Bob", "Charlie"],
                    "age": [30, 25, 35],
                    "city": ["New York", "San Francisco", "Boston"],
                }
            )

            df2 = pd.DataFrame(
                {
                    "name": ["David", "Eve"],
                    "age": [40, 45],
                    "city": ["Seattle", "Chicago"],
                }
            )

            # Write to Excel file with multiple sheets
            with pd.ExcelWriter(temp_path) as writer:
                df1.to_excel(writer, sheet_name="Sheet1", index=False)
                df2.to_excel(writer, sheet_name="Sheet2", index=False)

            return cls(file_path=temp_path, sheet_name="Sheet1")

        except ImportError:
            # Create a mock instance with an override if pandas is not available
            instance = cls(file_path="/path/to/nonexistent/file.xlsx")

            # Override the to_scenario_list method just for the example
            def mock_to_scenario_list(self):
                from .scenario_list import ScenarioList

                # Create a simple mock ScenarioList with sample data
                scenarios = [
                    Scenario({"name": "Alice", "age": 30, "city": "New York"}),
                    Scenario({"name": "Bob", "age": 25, "city": "San Francisco"}),
                    Scenario({"name": "Charlie", "age": 35, "city": "Boston"}),
                ]
                return ScenarioList(scenarios)

            # Replace the method on this instance only
            import types

            instance.to_scenario_list = types.MethodType(
                mock_to_scenario_list, instance
            )

            return instance

    def to_scenario_list(self):
        """Create a ScenarioList from an Excel file."""
        from .scenario_list import ScenarioList

        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Excel files")

        # Get all sheets
        all_sheets = pd.read_excel(self.file_path, sheet_name=None)

        # If no sheet_name is provided and there is more than one sheet, print available sheets
        sheet_name = self.sheet_name
        if sheet_name is None:
            if len(all_sheets) > 1:
                sheet_names = list(all_sheets.keys())
                available_sheets = ", ".join([f"'{name}'" for name in sheet_names])
                raise ScenarioError(
                    f"The Excel file contains multiple sheets: {available_sheets}. "
                    "Please provide a sheet_name parameter."
                )
            else:
                # If there is only one sheet, use it
                sheet_name = list(all_sheets.keys())[0]

        # Load the specified or determined sheet
        df = pd.read_excel(self.file_path, sheet_name=sheet_name, **self.kwargs)

        # Skip specified rows if any
        if self.skip_rows:
            df = df.drop(self.skip_rows)
            # Reset index to ensure continuous indexing
            df = df.reset_index(drop=True)

        # Handle codebook if requested
        if self.use_codebook:
            codebook = {f"col_{i}": col for i, col in enumerate(df.columns)}
            koobedoc = {col: f"col_{i}" for i, col in enumerate(df.columns)}

            # Create scenarios with renamed columns
            scenarios = []
            for _, row in df.iterrows():
                scenario_dict = {koobedoc.get(k): v for k, v in row.to_dict().items()}
                scenarios.append(Scenario(scenario_dict))

            result = ScenarioList(scenarios)
            result.codebook = codebook
            return result
        else:
            # Create scenarios with original column names
            scenarios = []
            for _, row in df.iterrows():
                scenario_dict = row.to_dict()
                scenarios.append(Scenario(scenario_dict))

            return ScenarioList(scenarios)


class GoogleSheetSource(Source):
    source_type = "google_sheet"

    def __init__(
        self,
        url: str,
        sheet_name: Optional[str] = None,
        column_names: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Initialize a GoogleSheetSource with a URL to a Google Sheet.

        Args:
            url: The URL of the Google Sheet.
            sheet_name: The name of the sheet to load. If None, the first sheet will be used.
            column_names: If provided, use these names for the columns instead
                         of the default column names from the sheet.
            **kwargs: Additional parameters to pass to pandas.read_excel.
        """
        self.url = url
        self.sheet_name = sheet_name
        self.column_names = column_names
        self.kwargs = kwargs

    @classmethod
    def example(cls) -> "GoogleSheetSource":
        """Return an example GoogleSheetSource instance."""
        # Use a mock instance since we can't create a real Google Sheet for testing
        instance = cls(
            url="https://docs.google.com/spreadsheets/d/1234567890abcdefg/edit",
            sheet_name="Sheet1",
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from .scenario_list import ScenarioList

            # Create a simple mock ScenarioList with sample data
            scenarios = [
                Scenario({"name": "Alice", "age": 30, "city": "New York"}),
                Scenario({"name": "Bob", "age": 25, "city": "San Francisco"}),
                Scenario({"name": "Charlie", "age": 35, "city": "Boston"}),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Google Sheet."""
        from .scenario_list import ScenarioList
        import tempfile
        import requests

        # Extract the sheet ID from the URL
        if "/edit" in self.url:
            sheet_id = self.url.split("/d/")[1].split("/edit")[0]
        else:
            raise ScenarioError("Invalid Google Sheet URL format.")

        # Create the export URL for XLSX format
        export_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        )

        try:
            # Download the Google Sheet as an Excel file
            response = requests.get(export_url)
            response.raise_for_status()  # Ensure the request was successful

            # Save the Excel file to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_filename = temp_file.name

            # Use ExcelSource to create the initial ScenarioList
            excel_source = ExcelSource(
                file_path=temp_filename, sheet_name=self.sheet_name, **self.kwargs
            )
            scenario_list = excel_source.to_scenario_list()

            # Apply column renaming if specified
            if self.column_names is not None and scenario_list:
                if len(self.column_names) != len(scenario_list[0].keys()):
                    raise ScenarioError(
                        f"Number of provided column names ({len(self.column_names)}) "
                        f"does not match number of columns in sheet ({len(scenario_list[0].keys())})"
                    )

                # Create a mapping from original keys to new names
                original_keys = list(scenario_list[0].keys())
                column_mapping = dict(zip(original_keys, self.column_names))

                # Create a new ScenarioList with renamed columns
                renamed_scenarios = []
                for scenario in scenario_list:
                    renamed_scenario = {
                        column_mapping.get(k, k): v for k, v in scenario.items()
                    }
                    renamed_scenarios.append(Scenario(renamed_scenario))

                return ScenarioList(renamed_scenarios)

            return scenario_list

        except requests.exceptions.RequestException as e:
            raise ScenarioError(f"Error fetching the Google Sheet: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"Error processing Google Sheet: {str(e)}")


class DelimitedFileSource(Source):
    source_type = "delimited_file"

    def __init__(
        self,
        file_or_url: str,
        delimiter: str = ",",
        has_header: bool = True,
        encoding: str = "utf-8",
        **kwargs,
    ):
        """
        Initialize a DelimitedFileSource with a path to a delimited file or URL.

        Args:
            file_or_url: Path to a local file or URL to a remote file.
            delimiter: The delimiter character used in the file (default is ',').
            has_header: Whether the file has a header row (default is True).
            encoding: The file encoding to use (default is 'utf-8').
            **kwargs: Additional parameters for csv reader.
        """
        self.file_or_url = file_or_url
        self.delimiter = delimiter
        self.has_header = has_header
        self.encoding = encoding
        self.kwargs = kwargs

    @classmethod
    def example(cls) -> "DelimitedFileSource":
        """Return an example DelimitedFileSource instance."""
        import tempfile
        import os

        # Create a temporary CSV file with sample data
        fd, temp_path = tempfile.mkstemp(suffix=".csv", prefix="edsl_test_")
        os.close(fd)  # Close the file descriptor

        # Write sample data to the file
        with open(temp_path, "w", newline="") as f:
            f.write("name,age,city\n")
            f.write("Alice,30,New York\n")
            f.write("Bob,25,San Francisco\n")
            f.write("Charlie,35,Boston\n")

        return cls(file_or_url=temp_path, delimiter=",", has_header=True)

    def to_scenario_list(self):
        """Create a ScenarioList from a delimited file or URL."""
        from .scenario_list import ScenarioList
        import requests

        # Check if the input is a URL
        parsed_url = urlparse(self.file_or_url)
        if parsed_url.scheme in ("http", "https"):
            try:
                headers = {
                    "Accept": "text/csv,application/csv,text/plain",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                response = requests.get(self.file_or_url, headers=headers)
                response.raise_for_status()
                content = response.text
            except requests.RequestException as e:
                raise ScenarioError(f"Failed to fetch URL: {str(e)}")
        else:
            # Assume it's a file path
            try:
                with open(self.file_or_url, "r", encoding=self.encoding) as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try different encoding if specified encoding fails
                encodings_to_try = ["latin-1", "cp1252", "ISO-8859-1"]
                if self.encoding in encodings_to_try:
                    encodings_to_try.remove(self.encoding)

                for encoding in encodings_to_try:
                    try:
                        with open(self.file_or_url, "r", encoding=encoding) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ScenarioError(
                        f"Failed to decode file with any of the attempted encodings"
                    )
            except Exception as e:
                raise ScenarioError(f"Failed to read file: {str(e)}")

        # Parse the content
        csv_reader = csv.reader(
            StringIO(content), delimiter=self.delimiter, **self.kwargs
        )
        rows = list(csv_reader)

        if not rows:
            return ScenarioList()

        # Handle header row
        if self.has_header:
            header = rows[0]
            data_rows = rows[1:]
        else:
            # Auto-generate column names
            header = [f"col{i}" for i in range(len(rows[0]))]
            data_rows = rows

        header_counts = defaultdict(lambda: 0)
        new_header = []
        for h in header:
            if header_counts[h] >= 1:
                new_header.append(f"{h}_{header_counts[h]}")
                warnings.warn(
                    f"Duplicate header found: {h}. Renamed to {h}_{header_counts[h]}"
                )
            else:
                new_header.append(h)
            header_counts[h] += 1

        assert len(new_header) == len(set(new_header))

        # Create scenarios
        scenarios = []
        for row in data_rows:
            if len(row) != len(new_header):
                warnings.warn(
                    f"Skipping row with {len(row)} values (expected {len(header)})"
                )
                continue

            scenario_dict = dict(zip(new_header, row))
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)


class CSVSource(DelimitedFileSource):
    source_type = "csv"

    def __init__(
        self,
        file_or_url: str,
        has_header: bool = True,
        encoding: str = "utf-8",
        **kwargs,
    ):
        """
        Initialize a CSVSource with a path to a CSV file or URL.

        Args:
            file_or_url: Path to a local file or URL to a remote file.
            has_header: Whether the file has a header row (default is True).
            encoding: The file encoding to use (default is 'utf-8').
            **kwargs: Additional parameters for csv reader.
        """
        super().__init__(
            file_or_url=file_or_url,
            delimiter=",",
            has_header=has_header,
            encoding=encoding,
            **kwargs,
        )

    @classmethod
    def example(cls) -> "CSVSource":
        """Return an example CSVSource instance."""
        import tempfile
        import os

        # Create a temporary CSV file with sample data
        fd, temp_path = tempfile.mkstemp(suffix=".csv", prefix="edsl_test_")
        os.close(fd)  # Close the file descriptor

        # Write sample data to the file
        with open(temp_path, "w", newline="") as f:
            f.write("name,age,city\n")
            f.write("Alice,30,New York\n")
            f.write("Bob,25,San Francisco\n")
            f.write("Charlie,35,Boston\n")

        return cls(file_or_url=temp_path, has_header=True)


class TSVSource(DelimitedFileSource):
    source_type = "tsv"

    def __init__(
        self,
        file_or_url: str,
        has_header: bool = True,
        encoding: str = "utf-8",
        **kwargs,
    ):
        """
        Initialize a TSVSource with a path to a TSV file or URL.

        Args:
            file_or_url: Path to a local file or URL to a remote file.
            has_header: Whether the file has a header row (default is True).
            encoding: The file encoding to use (default is 'utf-8').
            **kwargs: Additional parameters for csv reader.
        """
        super().__init__(
            file_or_url=file_or_url,
            delimiter="\t",
            has_header=has_header,
            encoding=encoding,
            **kwargs,
        )

    @classmethod
    def example(cls) -> "TSVSource":
        """Return an example TSVSource instance."""
        import tempfile
        import os

        # Create a temporary TSV file with sample data
        fd, temp_path = tempfile.mkstemp(suffix=".tsv", prefix="edsl_test_")
        os.close(fd)  # Close the file descriptor

        # Write sample data to the file
        with open(temp_path, "w", newline="") as f:
            f.write("name\tage\tcity\n")
            f.write("Alice\t30\tNew York\n")
            f.write("Bob\t25\tSan Francisco\n")
            f.write("Charlie\t35\tBoston\n")

        return cls(file_or_url=temp_path, has_header=True)


class ParquetSource(Source):
    source_type = "parquet"

    def __init__(self, file_path: str):
        """
        Initialize a ParquetSource with a path to a Parquet file.

        Args:
            file_path: Path to the Parquet file.
        """
        self.file_path = file_path

    @classmethod
    def example(cls) -> "ParquetSource":
        """Return an example ParquetSource instance."""
        import tempfile
        import os

        try:
            import pandas as pd
            import pyarrow as pa
            import pyarrow.parquet as pq

            # Create a temporary Parquet file with sample data
            fd, temp_path = tempfile.mkstemp(suffix=".parquet", prefix="edsl_test_")
            os.close(fd)  # Close the file descriptor

            # Create sample data
            df = pd.DataFrame(
                {
                    "name": ["Alice", "Bob", "Charlie"],
                    "age": [30, 25, 35],
                    "city": ["New York", "San Francisco", "Boston"],
                }
            )

            # Write to Parquet file
            df.to_parquet(temp_path)

            return cls(file_path=temp_path)

        except ImportError:
            # Create a mock instance with an override if pandas or pyarrow is not available
            instance = cls(file_path="/path/to/nonexistent/file.parquet")

            # Override the to_scenario_list method just for the example
            def mock_to_scenario_list(self):
                from .scenario_list import ScenarioList

                # Create a simple mock ScenarioList with sample data
                scenarios = [
                    Scenario({"name": "Alice", "age": 30, "city": "New York"}),
                    Scenario({"name": "Bob", "age": 25, "city": "San Francisco"}),
                    Scenario({"name": "Charlie", "age": 35, "city": "Boston"}),
                ]
                return ScenarioList(scenarios)

            # Replace the method on this instance only
            import types

            instance.to_scenario_list = types.MethodType(
                mock_to_scenario_list, instance
            )

            return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Parquet file."""
        from .scenario_list import ScenarioList

        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Parquet files")

        try:
            import pyarrow
        except ImportError:
            raise ImportError("pyarrow is required to read Parquet files")

        # Read the Parquet file
        df = pd.read_parquet(self.file_path)

        # Convert DataFrame to ScenarioList
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)


class PDFSource(Source):
    source_type = "pdf"

    def __init__(
        self,
        file_path: str,
        chunk_type: Literal["page", "text"] = "page",
        chunk_size: int = 1,
        chunk_overlap: int = 0,
    ):
        """
        Initialize a PDFSource with a path to a PDF file.

        Args:
            file_path: Path to the PDF file or URL to a PDF.
            chunk_type: Type of chunking to use ("page" or "text").
            chunk_size: Size of chunks to create.
            chunk_overlap: Number of overlapping chunks.
        """
        self.file_path = file_path
        self.chunk_type = chunk_type
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @classmethod
    def example(cls) -> "PDFSource":
        """Return an example PDFSource instance."""
        # Skip actual file creation and just use a mock instance
        instance = cls(
            file_path="/path/to/nonexistent/file.pdf",
            chunk_type="page",
            chunk_size=1,
            chunk_overlap=0,
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from .scenario_list import ScenarioList

            # Create a simple mock ScenarioList with sample PDF data
            scenarios = [
                Scenario(
                    {
                        "filename": "example.pdf",
                        "page": 1,
                        "text": "This is page 1 content",
                    }
                ),
                Scenario(
                    {
                        "filename": "example.pdf",
                        "page": 2,
                        "text": "This is page 2 content",
                    }
                ),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a PDF file."""
        from .scenario_list import ScenarioList
        from .scenario_list_pdf_tools import PdfTools

        try:
            # Check if it's a URL
            if PdfTools.is_url(self.file_path):
                # Download the PDF file
                if "drive.google.com" in self.file_path:
                    # It's a Google Drive URL
                    local_path = PdfTools.GoogleDriveDownloader.fetch_from_drive(
                        self.file_path, "temp_pdf.pdf"
                    )
                else:
                    # It's a regular URL
                    local_path = PdfTools.fetch_and_save_pdf(
                        self.file_path, "temp_pdf.pdf"
                    )
            else:
                # It's a local file path
                local_path = self.file_path

            # Extract scenarios from the PDF
            scenarios = list(PdfTools.extract_text_from_pdf(local_path))

            # Handle chunking based on the specified parameters
            if self.chunk_type == "page":
                # Default behavior - one scenario per page
                return ScenarioList(scenarios)
            elif self.chunk_type == "text":
                # Combine all text
                combined_text = ""
                for scenario in scenarios:
                    combined_text += scenario["text"]

                # Create a single scenario with all text
                base_scenario = scenarios[0].copy()
                base_scenario["text"] = combined_text
                return ScenarioList([base_scenario])
            else:
                raise ValueError(
                    f"Invalid chunk_type: {self.chunk_type}. Must be 'page' or 'text'."
                )

        except Exception as e:
            from .exceptions import ScenarioError

            raise ScenarioError(f"Error processing PDF: {str(e)}")


class PDFImageSource(Source):
    source_type = "pdf_to_image"

    def __init__(
        self, file_path: str, base_width: int = 2000, include_text: bool = True
    ):
        """
        Initialize a PDFImageSource with a path to a PDF file.

        Args:
            file_path: Path to the PDF file.
            base_width: Width to use for the generated images.
            include_text: Whether to include extracted text with the images.
        """
        self.file_path = file_path
        self.base_width = base_width
        self.include_text = include_text

    @classmethod
    def example(cls) -> "PDFImageSource":
        """Return an example PDFImageSource instance."""
        # Skip actual file creation and just use a mock instance
        instance = cls(
            file_path="/path/to/nonexistent/file.pdf",
            base_width=2000,
            include_text=True,
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from .scenario_list import ScenarioList

            # Create a simple mock ScenarioList with sample PDF image data
            scenarios = [
                Scenario(
                    {
                        "filepath": "/tmp/page_1.jpeg",
                        "page": 0,
                        "text": "This is page 1 content",
                    }
                ),
                Scenario(
                    {
                        "filepath": "/tmp/page_2.jpeg",
                        "page": 1,
                        "text": "This is page 2 content",
                    }
                ),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a PDF file, converting pages to images."""
        from .scenario_list import ScenarioList
        from .scenario_list_pdf_tools import PdfTools

        try:
            # Import pdf2image library
            try:
                from pdf2image import convert_from_path
            except ImportError:
                raise ImportError(
                    "pdf2image is required to convert PDF to images. Install it with 'pip install pdf2image'."
                )

            # Convert PDF pages to images
            scenarios = PdfTools.from_pdf_to_image(self.file_path, image_format="jpeg")
            return ScenarioList(scenarios)

        except Exception as e:
            from .exceptions import ScenarioError

            raise ScenarioError(f"Error converting PDF to images: {str(e)}")


class ScenarioSource:
    """
    Factory class for creating ScenarioList objects from various sources.

    This class provides static methods for creating ScenarioList objects from different
    data sources, centralizing the creation logic that was previously scattered across
    different classmethods in the ScenarioList class.

    The main entry point is the from_source method, which dispatches to appropriate
    source-specific methods based on the source_type parameter.
    """

    @staticmethod
    def from_source(source_type: str, *args, **kwargs):
        """
        Create a ScenarioList from a specified source type.

        This method serves as the main entry point for creating ScenarioList objects,
        dispatching to the appropriate source-specific method based on the source_type.

        Args:
            source_type: The type of source to create a ScenarioList from.
                         Valid values include: 'urls', 'directory', 'list', 'list_of_tuples',
                         'sqlite', 'latex', 'google_doc', 'pandas', 'dta', 'wikipedia',
                         'excel', 'google_sheet', 'delimited_file', 'csv', 'tsv', 'dict',
                         'nested_dict', 'parquet', 'pdf', 'pdf_to_image'.
            *args: Positional arguments to pass to the source-specific method.
            **kwargs: Keyword arguments to pass to the source-specific method.

        Returns:
            A ScenarioList object created from the specified source.

        Raises:
            ValueError: If the source_type is not recognized.
        """
        try:
            source_class = Source.get_source_class(source_type)
            source_instance = source_class(*args, **kwargs)
            return source_instance.to_scenario_list()
        except ValueError as e:
            # For backward compatibility, try the old method if the source_type isn't in the registry
            method_name = f"_from_{source_type}"
            if hasattr(ScenarioSource, method_name):
                method = getattr(ScenarioSource, method_name)
                return method(*args, **kwargs)
            else:
                raise ValueError(f"Unsupported source type: {source_type}")

    @staticmethod
    def _from_urls(urls: list[str], field_name: Optional[str] = "text"):
        """Create a ScenarioList from a list of URLs."""
        from .scenario_list import ScenarioList

        import requests

        result = ScenarioList()
        for url in urls:
            try:
                response = requests.get(url)
                response.raise_for_status()
                scenario = Scenario({field_name: response.text})
                result.append(scenario)
            except requests.RequestException as e:
                warnings.warn(f"Failed to fetch URL {url}: {str(e)}")
                continue

        return result

    @staticmethod
    def _from_directory(
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
        metadata: bool = True,
        ignore_dirs: List[str] = None,
        ignore_files: List[str] = None,
    ):
        """Create a ScenarioList from files in a directory."""
        warnings.warn(
            "_from_directory is deprecated. Use DirectorySource directly or ScenarioSource.from_source('directory', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = DirectorySource(
            directory=directory,
            pattern=pattern,
            recursive=recursive,
            metadata=metadata,
            ignore_dirs=ignore_dirs,
            ignore_files=ignore_files,
        )
        return source.to_scenario_list()

    @staticmethod
    def _from_list(field_name: str, values: list, use_indexes: bool = False):
        """Create a ScenarioList from a list of values with a specified field name."""
        warnings.warn(
            "_from_list is deprecated. Use ListSource directly or ScenarioSource.from_source('list', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = ListSource(field_name, values, use_indexes)
        return source.to_scenario_list()

    @staticmethod
    def _from_list_of_tuples(
        field_names: list[str], values: list[tuple], use_indexes: bool = False
    ):
        """Create a ScenarioList from a list of tuples with specified field names."""
        warnings.warn(
            "_from_list_of_tuples is deprecated. Use TuplesSource directly or ScenarioSource.from_source('list_of_tuples', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = TuplesSource(field_names, values, use_indexes)
        return source.to_scenario_list()

    @staticmethod
    def _from_sqlite(db_path: str, table: str, fields: Optional[list] = None):
        """Create a ScenarioList from a SQLite database."""
        warnings.warn(
            "_from_sqlite is deprecated. Use SQLiteSource directly or ScenarioSource.from_source('sqlite', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = SQLiteSource(db_path, table, fields)
        return source.to_scenario_list()

    @staticmethod
    def _from_latex(file_path: str, table_index: int = 0, has_header: bool = True):
        """Create a ScenarioList from a LaTeX file."""
        warnings.warn(
            "_from_latex is deprecated. Use LaTeXSource directly or ScenarioSource.from_source('latex', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = LaTeXSource(file_path, table_index, has_header)
        return source.to_scenario_list()

    @staticmethod
    def _from_google_doc(url: str):
        """Create a ScenarioList from a Google Doc."""
        warnings.warn(
            "_from_google_doc is deprecated. Use GoogleDocSource directly or ScenarioSource.from_source('google_doc', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = GoogleDocSource(url)
        return source.to_scenario_list()

    @staticmethod
    def _from_pandas(df):
        """Create a ScenarioList from a pandas DataFrame."""
        warnings.warn(
            "_from_pandas is deprecated. Use PandasSource directly or ScenarioSource.from_source('pandas', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = PandasSource(df)
        return source.to_scenario_list()

    @staticmethod
    def _from_dta(file_path: str, include_metadata: bool = True):
        """Create a ScenarioList from a Stata data file."""
        warnings.warn(
            "_from_dta is deprecated. Use StataSource directly or ScenarioSource.from_source('dta', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = StataSource(file_path, include_metadata)
        return source.to_scenario_list()

    @staticmethod
    def _from_wikipedia(url: str, table_index: int = 0, header: bool = True):
        """Create a ScenarioList from a table on a Wikipedia page."""
        warnings.warn(
            "_from_wikipedia is deprecated. Use WikipediaSource directly or ScenarioSource.from_source('wikipedia', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = WikipediaSource(url, table_index, header)
        return source.to_scenario_list()

    @staticmethod
    def _from_excel(file_path: str, sheet_name: Optional[str] = None, **kwargs):
        """Create a ScenarioList from an Excel file."""
        warnings.warn(
            "_from_excel is deprecated. Use ExcelSource directly or ScenarioSource.from_source('excel', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = ExcelSource(file_path, sheet_name=sheet_name, **kwargs)
        return source.to_scenario_list()

    @staticmethod
    def _from_google_sheet(
        url: str,
        sheet_name: Optional[str] = None,
        column_names: Optional[List[str]] = None,
        **kwargs,
    ):
        """Create a ScenarioList from a Google Sheet."""
        warnings.warn(
            "_from_google_sheet is deprecated. Use GoogleSheetSource directly or ScenarioSource.from_source('google_sheet', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = GoogleSheetSource(
            url, sheet_name=sheet_name, column_names=column_names, **kwargs
        )
        return source.to_scenario_list()

    @staticmethod
    def _from_delimited_file(
        file_or_url: str,
        delimiter: str = ",",
        has_header: bool = True,
        encoding: str = "utf-8",
        **kwargs,
    ):
        """Create a ScenarioList from a delimited file or URL."""
        warnings.warn(
            "_from_delimited_file is deprecated. Use DelimitedFileSource directly or ScenarioSource.from_source('delimited_file', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = DelimitedFileSource(
            file_or_url=file_or_url,
            delimiter=delimiter,
            has_header=has_header,
            encoding=encoding,
            **kwargs,
        )
        return source.to_scenario_list()

    @staticmethod
    def _from_csv(file_or_url: str, **kwargs):
        """Create a ScenarioList from a CSV file or URL."""
        warnings.warn(
            "_from_csv is deprecated. Use CSVSource directly or ScenarioSource.from_source('csv', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = CSVSource(file_or_url=file_or_url, **kwargs)
        return source.to_scenario_list()

    @staticmethod
    def _from_tsv(file_or_url: str, **kwargs):
        """Create a ScenarioList from a TSV file or URL."""
        warnings.warn(
            "_from_tsv is deprecated. Use TSVSource directly or ScenarioSource.from_source('tsv', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = TSVSource(file_or_url=file_or_url, **kwargs)
        return source.to_scenario_list()

    @staticmethod
    def _from_dict(data: dict):
        """Create a ScenarioList from a dictionary."""
        from .scenario_list import ScenarioList

        if "scenarios" in data:
            scenarios = [Scenario(s) for s in data["scenarios"]]
            codebook = data.get("codebook", {})
            return ScenarioList(scenarios, codebook)
        else:
            scenarios = []
            # Assume the dict maps field names to lists of values
            field_names = list(data.keys())
            if not all(isinstance(v, list) for v in data.values()):
                raise ScenarioError("All values in the dictionary must be lists")

            # Check all lists have the same length
            list_lengths = [len(v) for v in data.values()]
            if not all(l == list_lengths[0] for l in list_lengths):
                raise ScenarioError("All lists must have the same length")

            # Create scenarios
            for i in range(list_lengths[0]):
                scenario_dict = {k: data[k][i] for k in field_names}
                scenarios.append(Scenario(scenario_dict))

            return ScenarioList(scenarios)

    @staticmethod
    def _from_nested_dict(data: dict, id_field: Optional[str] = None):
        """Create a ScenarioList from a nested dictionary."""
        from .scenario_list import ScenarioList

        scenarios = []

        for key, value in data.items():
            if not isinstance(value, dict):
                raise ScenarioError(f"Value for key {key} is not a dictionary")

            scenario_dict = value.copy()
            if id_field:
                scenario_dict[id_field] = key
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)

    @staticmethod
    def _from_parquet(file_path: str):
        """Create a ScenarioList from a Parquet file."""
        warnings.warn(
            "_from_parquet is deprecated. Use ParquetSource directly or ScenarioSource.from_source('parquet', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = ParquetSource(file_path)
        return source.to_scenario_list()

    @staticmethod
    def _from_pdf(
        file_path: str,
        chunk_type: Literal["page", "text"] = "page",
        chunk_size: int = 1,
        chunk_overlap: int = 0,
    ):
        """Create a ScenarioList from a PDF file."""
        warnings.warn(
            "_from_pdf is deprecated. Use PDFSource directly or ScenarioSource.from_source('pdf', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = PDFSource(
            file_path=file_path,
            chunk_type=chunk_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return source.to_scenario_list()

    @staticmethod
    def _from_pdf_to_image(
        file_path: str,
        base_width: int = 2000,
        include_text: bool = True,
    ):
        """Create a ScenarioList containing images extracted from a PDF file."""
        warnings.warn(
            "_from_pdf_to_image is deprecated. Use PDFImageSource directly or ScenarioSource.from_source('pdf_to_image', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        source = PDFImageSource(
            file_path=file_path, base_width=base_width, include_text=include_text
        )
        return source.to_scenario_list()
