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
from typing import Any, Callable, List, Literal, Optional, Type, TypeVar, Union, TYPE_CHECKING, cast

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

# Local imports
from .scenario import Scenario
from .scenario_list import ScenarioList
from .directory_scanner import DirectoryScanner
from .exceptions import ScenarioError


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
    def from_source(source_type: str, *args, **kwargs) -> ScenarioList:
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
        method_name = f"_from_{source_type}"
        if hasattr(ScenarioSource, method_name):
            method = getattr(ScenarioSource, method_name)
            return method(*args, **kwargs)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
    
    @staticmethod
    def _from_urls(urls: list[str], field_name: Optional[str] = "text") -> ScenarioList:
        """Create a ScenarioList from a list of URLs."""
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
    ) -> ScenarioList:
        """Create a ScenarioList from files in a directory."""
        return DirectoryScanner.scan_directory(
            directory=directory,
            pattern=pattern,
            recursive=recursive,
            metadata=metadata,
            ignore_dirs=ignore_dirs or [],
            ignore_files=ignore_files or [],
        )
    
    @staticmethod
    def _from_list(
        field_name: str, values: list, use_indexes: bool = False
    ) -> ScenarioList:
        """Create a ScenarioList from a list of values with a specified field name."""
        scenarios = []
        
        for i, value in enumerate(values):
            scenario_dict = {field_name: value}
            if use_indexes:
                scenario_dict["idx"] = i
            scenarios.append(Scenario(scenario_dict))
            
        return ScenarioList(scenarios)
    
    @staticmethod
    def _from_list_of_tuples(
        field_names: list[str], values: list[tuple], use_indexes: bool = False
    ) -> ScenarioList:
        """Create a ScenarioList from a list of tuples with specified field names."""
        scenarios = []
        
        for i, value_tuple in enumerate(values):
            if len(value_tuple) != len(field_names):
                raise ScenarioError(
                    f"Tuple {i} has {len(value_tuple)} elements, but {len(field_names)} field names were provided."
                )
                
            scenario_dict = dict(zip(field_names, value_tuple))
            if use_indexes:
                scenario_dict["idx"] = i
            scenarios.append(Scenario(scenario_dict))
            
        return ScenarioList(scenarios)
    
    @staticmethod
    def _from_sqlite(
        db_path: str, table: str, fields: Optional[list] = None
    ) -> ScenarioList:
        """Create a ScenarioList from a SQLite database."""
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if fields is None:
            cursor.execute(f"PRAGMA table_info({table})")
            fields = [row[1] for row in cursor.fetchall()]
            
        field_placeholders = ", ".join(fields)
        cursor.execute(f"SELECT {field_placeholders} FROM {table}")
        rows = cursor.fetchall()
        
        scenarios = []
        for row in rows:
            scenario_dict = dict(zip(fields, row))
            scenarios.append(Scenario(scenario_dict))
            
        conn.close()
        return ScenarioList(scenarios)
    
    @staticmethod
    def _from_latex(
        file_path: str, table_index: int = 0, has_header: bool = True
    ) -> ScenarioList:
        """Create a ScenarioList from a LaTeX file."""
        with open(file_path, "r") as f:
            content = f.read()
            
        return ScenarioSource._parse_latex_table(content, table_index, has_header)
    
    @staticmethod
    def _parse_latex_table(
        content: str, table_index: int = 0, has_header: bool = True
    ) -> ScenarioList:
        """Parse LaTeX table content and create a ScenarioList."""
        import re
        
        # Find all tabular environments
        tabular_pattern = r"\\begin{tabular}(.*?)\\end{tabular}"
        tables = re.findall(tabular_pattern, content, re.DOTALL)
        
        if not tables or table_index >= len(tables):
            raise ScenarioError(f"No table found at index {table_index}")
            
        table_content = tables[table_index]
        
        # Extract rows
        rows = table_content.split("\\\\")
        rows = [row.strip() for row in rows if row.strip()]
        
        if not rows:
            return ScenarioList()
            
        # Process header if available
        if has_header:
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
    
    @staticmethod
    def _from_google_doc(doc_id: str, table_index: int = 0) -> ScenarioList:
        """Create a ScenarioList from a Google Doc."""
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
    def _from_pandas(df) -> ScenarioList:
        """Create a ScenarioList from a pandas DataFrame."""
        import pandas as pd
        
        if not isinstance(df, pd.DataFrame):
            raise ScenarioError("Input must be a pandas DataFrame")
            
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))
            
        return ScenarioList(scenarios)
    
    @staticmethod
    def _from_dta(file_path: str) -> ScenarioList:
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
    ) -> ScenarioList:
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
    ) -> ScenarioList:
        """Create a ScenarioList from an Excel file."""
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Excel files")
            
        df = pd.read_excel(file_path, sheet_name=sheet_name, **kwargs)
        return ScenarioSource._from_pandas(df)
    
    @staticmethod
    def _from_google_sheet(sheet_id: str, sheet_name: Optional[str] = None) -> ScenarioList:
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
    ) -> ScenarioList:
        """Create a ScenarioList from a delimited file or URL."""
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
    def _from_csv(file_or_url: str, **kwargs) -> ScenarioList:
        """Create a ScenarioList from a CSV file or URL."""
        return ScenarioSource._from_delimited_file(file_or_url, delimiter=",", **kwargs)
    
    @staticmethod
    def _from_tsv(file_or_url: str, **kwargs) -> ScenarioList:
        """Create a ScenarioList from a TSV file or URL."""
        return ScenarioSource._from_delimited_file(file_or_url, delimiter="\t", **kwargs)
    
    @staticmethod
    def _from_dict(data: dict) -> ScenarioList:
        """Create a ScenarioList from a dictionary."""
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
    def _from_nested_dict(data: dict, id_field: Optional[str] = None) -> ScenarioList:
        """Create a ScenarioList from a nested dictionary."""
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
    def _from_parquet(file_path: str) -> ScenarioList:
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
    ) -> ScenarioList:
        """Create a ScenarioList from a PDF file."""
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
    ) -> ScenarioList:
        """Create a ScenarioList containing images extracted from a PDF file."""
        from .scenario_list_pdf_tools import PdfTools
        
        return PdfTools.pdf_to_images(
            file_path=file_path,
            base_width=base_width,
            include_text=include_text,
        )