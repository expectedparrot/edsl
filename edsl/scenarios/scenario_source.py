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
from typing import Any, Callable, List, Literal, Optional, Type, TypeVar, Union, TYPE_CHECKING, cast, Any

T = TypeVar('T')

def deprecated_classmethod(alternative: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
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
                stacklevel=2
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
    _registry: dict[str, Type['Source']] = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses with their source_type."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'source_type'):
            Source._registry[cls.source_type] = cls

    @classmethod
    @abstractmethod
    def example(cls) -> 'Source':
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
    def get_source_class(cls, source_type: str) -> Type['Source']:
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
                    print(f"Source {source_type} returned {type(scenario_list)} instead of ScenarioList")
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
    def example(cls) -> 'URLSource':
        """Return an example URLSource instance."""
        return cls(
            urls=['http://www.example.com'],
            field_name="text"
        )
    
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
    def example(cls) -> 'ListSource':
        """Return an example ListSource instance."""
        return cls(
            field_name="text",
            values=["example1", "example2", "example3"],
            use_indexes=True
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
    def example(cls) -> 'DirectorySource':
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
            ignore_files=["*.pyc"]
        )
    
    def to_scenario_list(self):
        """Create a ScenarioList from files in a directory."""
        import os
        import glob
        
        from .scenario_list import ScenarioList
        
        # Set default recursive value
        recursive = self.recursive
        
        # Handle paths with wildcards properly
        if '*' in self.directory:
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
                    if any(fnmatch.fnmatch(file_name, ignore_pattern) for ignore_pattern in self.ignore_files or []):
                        continue
                    
                    # Create FileStore object
                    file_store = FileStore(file_path)
                    
                    # Create scenario
                    scenario_data = {"file": file_store}
                    
                    # Add metadata if requested
                    if self.metadata:
                        file_stat = os.stat(file_path)
                        scenario_data.update({
                            "file_path": file_path,
                            "file_name": file_name,
                            "file_size": file_stat.st_size,
                            "file_created": file_stat.st_ctime,
                            "file_modified": file_stat.st_mtime,
                        })
                    
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
    
    def __init__(self, field_names: list[str], values: list[tuple], use_indexes: bool = False):
        self.field_names = field_names
        self.values = values
        self.use_indexes = use_indexes
        
        # Validate inputs
        if not all(isinstance(v, (tuple, list)) for v in values):
            raise ScenarioError("All values must be tuples or lists")
    
    @classmethod
    def example(cls) -> 'TuplesSource':
        """Return an example TuplesSource instance."""
        return cls(
            field_names=["name", "age", "city"],
            values=[
                ("Alice", 30, "New York"),
                ("Bob", 25, "San Francisco"),
                ("Charlie", 35, "Boston")
            ],
            use_indexes=True
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
    def example(cls) -> 'SQLiteSource':
        """Return an example SQLiteSource instance."""
        import sqlite3
        import tempfile
        import os
        
        # Create a temporary SQLite database for the example
        fd, temp_path = tempfile.mkstemp(suffix='.db', prefix='edsl_test_')
        os.close(fd)  # Close the file descriptor
        
        # Connect to the database and create a sample table
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()
        
        # Create a simple table
        cursor.execute('CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)')
        
        # Insert sample data
        sample_data = [
            (1, 'Alpha', 100),
            (2, 'Beta', 200),
            (3, 'Gamma', 300)
        ]
        cursor.executemany('INSERT INTO test_table VALUES (?, ?, ?)', sample_data)
        
        conn.commit()
        conn.close()
        
        return cls(
            db_path=temp_path,
            table='test_table',
            fields=['id', 'name', 'value']
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
    def example(cls) -> 'LaTeXSource':
        """Return an example LaTeXSource instance."""
        import tempfile
        import os
        
        # Create a temporary LaTeX file with a sample table
        fd, temp_path = tempfile.mkstemp(suffix='.tex', prefix='edsl_test_')
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
        with open(temp_path, 'w') as f:
            f.write(sample_latex)
        
        return cls(
            file_path=temp_path,
            table_index=0,
            has_header=True
        )
    
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
            stacklevel=2
        )
        source = DirectorySource(
            directory=directory,
            pattern=pattern,
            recursive=recursive,
            metadata=metadata,
            ignore_dirs=ignore_dirs,
            ignore_files=ignore_files
        )
        return source.to_scenario_list()
    
    @staticmethod
    def _from_list(
        field_name: str, values: list, use_indexes: bool = False
    ):
        """Create a ScenarioList from a list of values with a specified field name."""
        warnings.warn(
            "_from_list is deprecated. Use ListSource directly or ScenarioSource.from_source('list', ...) instead.",
            DeprecationWarning,
            stacklevel=2
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
            stacklevel=2
        )
        source = TuplesSource(field_names, values, use_indexes)
        return source.to_scenario_list()
    
    @staticmethod
    def _from_sqlite(
        db_path: str, table: str, fields: Optional[list] = None
    ):
        """Create a ScenarioList from a SQLite database."""
        warnings.warn(
            "_from_sqlite is deprecated. Use SQLiteSource directly or ScenarioSource.from_source('sqlite', ...) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        source = SQLiteSource(db_path, table, fields)
        return source.to_scenario_list()
    
    @staticmethod
    def _from_latex(
        file_path: str, table_index: int = 0, has_header: bool = True
    ):
        """Create a ScenarioList from a LaTeX file."""
        warnings.warn(
            "_from_latex is deprecated. Use LaTeXSource directly or ScenarioSource.from_source('latex', ...) instead.",
            DeprecationWarning,
            stacklevel=2
        )
        source = LaTeXSource(file_path, table_index, has_header)
        return source.to_scenario_list()
    
    @staticmethod
    def _from_google_doc(doc_id: str, table_index: int = 0):
        """Create a ScenarioList from a Google Doc."""
        from .scenario_list import ScenarioList
        
        try:
            from googleapiclient.discovery import build
            from google.oauth2 import service_account
        except ImportError:
            raise ImportError(
                "The Google API Client is not installed. Please install it with `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`"
            )
            
        # Implement Google Doc API interaction here
        # For now, returning an empty ScenarioList as placeholder
        warnings.warn("from_google_doc is not fully implemented yet")
        return ScenarioList()
    
    @staticmethod
    def _from_pandas(df):
        """Create a ScenarioList from a pandas DataFrame."""
        from .scenario_list import ScenarioList
        
        import pandas as pd
        
        if not isinstance(df, pd.DataFrame):
            raise ScenarioError("Input must be a pandas DataFrame")
            
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))
            
        return ScenarioList(scenarios)
    
    @staticmethod
    def _from_dta(file_path: str):
        """Create a ScenarioList from a Stata data file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Stata files")
            
        df = pd.read_stata(file_path)
        return ScenarioSource._from_pandas(df)
    
    @staticmethod
    def _from_wikipedia(
        url: str, table_index: int = 0, header: bool = True
    ):
        """Create a ScenarioList from a table on a Wikipedia page."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Wikipedia tables")
            
        tables = pd.read_html(url, header=0 if header else None)
        
        if not tables or table_index >= len(tables):
            raise ScenarioError(f"No table found at index {table_index}")
            
        return ScenarioSource._from_pandas(tables[table_index])
    
    @staticmethod
    def _from_excel(
        file_path: str, sheet_name: Optional[str] = None, **kwargs
    ):
        """Create a ScenarioList from an Excel file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Excel files")
            
        df = pd.read_excel(file_path, sheet_name=sheet_name, **kwargs)
        return ScenarioSource._from_pandas(df)
    
    @staticmethod
    def _from_google_sheet(sheet_id: str, sheet_name: Optional[str] = None):
        """Create a ScenarioList from a Google Sheet."""
        try:
            import pandas as pd
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
        except ImportError:
            raise ImportError(
                "Required packages not installed. Please install gspread, oauth2client, and pandas."
            )
            
        # Implement Google Sheets API interaction here
        # For now, returning an empty ScenarioList as placeholder
        warnings.warn("from_google_sheet is not fully implemented yet")
        return ScenarioList()
    
    @staticmethod
    def _from_delimited_file(
        file_or_url: str,
        delimiter: str = ",",
        has_header: bool = True,
        encoding: str = "utf-8",
        **kwargs,
    ):
        """Create a ScenarioList from a delimited file or URL."""
        from .scenario_list import ScenarioList
        
        # Check if the input is a URL
        parsed_url = urlparse(file_or_url)
        if parsed_url.scheme in ("http", "https"):
            import requests
            
            try:
                response = requests.get(file_or_url)
                response.raise_for_status()
                content = response.text
            except requests.RequestException as e:
                raise ScenarioError(f"Failed to fetch URL: {str(e)}")
        else:
            # Assume it's a file path
            try:
                with open(file_or_url, "r", encoding=encoding) as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Try different encoding if UTF-8 fails
                try:
                    with open(file_or_url, "r", encoding="latin-1") as f:
                        content = f.read()
                except Exception as e:
                    raise ScenarioError(f"Failed to read file: {str(e)}")
            except Exception as e:
                raise ScenarioError(f"Failed to read file: {str(e)}")
                
        # Parse the content
        csv_reader = csv.reader(StringIO(content), delimiter=delimiter)
        rows = list(csv_reader)
        
        if not rows:
            return ScenarioList()
            
        if has_header:
            header = rows[0]
            data_rows = rows[1:]
        else:
            # Auto-generate column names
            header = [f"col{i}" for i in range(len(rows[0]))]
            data_rows = rows
            
        # Create scenarios
        scenarios = []
        for row in data_rows:
            if len(row) != len(header):
                warnings.warn(f"Skipping row with {len(row)} values (expected {len(header)})")
                continue
                
            scenario_dict = dict(zip(header, row))
            scenarios.append(Scenario(scenario_dict))
            
        return ScenarioList(scenarios)
    
    @staticmethod
    def _from_csv(file_or_url: str, **kwargs):
        """Create a ScenarioList from a CSV file or URL."""
        return ScenarioSource._from_delimited_file(file_or_url, delimiter=",", **kwargs)
    
    @staticmethod
    def _from_tsv(file_or_url: str, **kwargs):
        """Create a ScenarioList from a TSV file or URL."""
        return ScenarioSource._from_delimited_file(file_or_url, delimiter="\t", **kwargs)
    
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
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Parquet files")
            
        try:
            import pyarrow
        except ImportError:
            raise ImportError("pyarrow is required to read Parquet files")
            
        df = pd.read_parquet(file_path)
        return ScenarioSource._from_pandas(df)
    
    @staticmethod
    def _from_pdf(
        file_path: str,
        chunk_type: Literal["page", "text"] = "page",
        chunk_size: int = 1,
        chunk_overlap: int = 0,
    ):
        """Create a ScenarioList from a PDF file."""
        from .scenario_list import ScenarioList
        from .scenario_list_pdf_tools import PdfTools
        
        return PdfTools.pdf_to_scenariolist(
            file_path=file_path,
            chunk_type=chunk_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    
    @staticmethod
    def _from_pdf_to_image(
        file_path: str,
        base_width: int = 2000,
        include_text: bool = True,
    ):
        """Create a ScenarioList containing images extracted from a PDF file."""
        from .scenario_list import ScenarioList
        from .scenario_list_pdf_tools import PdfTools
        
        return PdfTools.pdf_to_images(
            file_path=file_path,
            base_width=base_width,
            include_text=include_text,
        )