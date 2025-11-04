"""
ScenarioSourceInferrer provides automatic source type detection for creating ScenarioList objects.

This module contains the ScenarioSourceInferrer class, which automatically detects the type
of data source passed to it and dispatches to the appropriate source handler. It uses
heuristics and try/except blocks to determine the correct source type without requiring
explicit specification.

Key features include:
- Automatic detection of common data formats (CSV, Excel, PDF, Parquet, etc.)
- URL detection and handling
- Support for pandas DataFrames, lists, dictionaries, and file paths
- Directory and SQLite database detection
- Graceful fallback mechanisms

This module simplifies ScenarioList creation by allowing users to pass data without
specifying the source type explicitly.
"""

from __future__ import annotations
import os
import warnings
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .scenario_list import ScenarioList

from .scenario_source import ScenarioSource
from .exceptions import ScenarioError


class ScenarioSourceInferrer:
    """
    Infers the source type of input data and creates ScenarioList objects automatically.
    
    This class examines input data and uses heuristics to determine what type of source
    it represents, then dispatches to the appropriate ScenarioSource method to create
    a ScenarioList.
    """

    @staticmethod
    def infer_and_create(
        source: Any,
        field_name: Optional[str] = None,
        verbose: bool = False,
        **kwargs
    ) -> "ScenarioList":
        """
        Infer the source type and create a ScenarioList from the provided data.
        
        This method examines the input and uses various heuristics to determine the
        appropriate source type, then creates a ScenarioList accordingly.
        
        Args:
            source: The data source to create a ScenarioList from. Can be:
                    - A file path (str or Path)
                    - A URL (str)
                    - A pandas DataFrame
                    - A list or list of tuples
                    - A dictionary
                    - A directory path
            field_name: Optional field name to use for certain source types (e.g., list)
            verbose: If True, print the detected source type (default: False)
            **kwargs: Additional keyword arguments to pass to the specific source handler
        
        Returns:
            A ScenarioList object created from the inferred source.
        
        Raises:
            ScenarioError: If the source type cannot be inferred or the source is invalid.
        
        Examples:
            >>> # From CSV file
            >>> sl = ScenarioSourceInferrer.infer_and_create("data.csv")  # doctest: +SKIP

            >>> # From pandas DataFrame
            >>> import pandas as pd
            >>> df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
            >>> sl = ScenarioSourceInferrer.infer_and_create(df)

            >>> # From dictionary
            >>> data = {"product": ["coffee", "tea"], "price": [4.99, 3.99]}
            >>> sl = ScenarioSourceInferrer.infer_and_create(data)
        """
        # Check for pandas DataFrame
        if ScenarioSourceInferrer._is_pandas_dataframe(source):
            if verbose:
                print("Detected source type: pandas DataFrame")
            return ScenarioSource.from_source("pandas", source, **kwargs)
        
        # Check for dictionary
        if isinstance(source, dict):
            if verbose:
                if "scenarios" in source:
                    print("Detected source type: serialized ScenarioList dictionary")
                elif all(isinstance(v, dict) for v in source.values()):
                    print("Detected source type: nested dictionary")
                else:
                    print("Detected source type: dictionary")
            return ScenarioSourceInferrer._handle_dict(source, **kwargs)
        
        # Check for list
        if isinstance(source, list):
            if verbose:
                if source and isinstance(source[0], tuple):
                    print("Detected source type: list of tuples")
                else:
                    print("Detected source type: list")
            return ScenarioSourceInferrer._handle_list(source, field_name, **kwargs)
        
        # Check for string (could be URL, file path, or directory)
        if isinstance(source, (str, Path)):
            return ScenarioSourceInferrer._handle_string_or_path(source, field_name, verbose, **kwargs)
        
        # If we get here, we couldn't infer the type
        raise ScenarioError(
            f"Unable to infer source type from input of type {type(source).__name__}. "
            "Please specify the source type explicitly using ScenarioSource.from_source()."
        )
    
    @staticmethod
    def _is_pandas_dataframe(source: Any) -> bool:
        """Check if the source is a pandas DataFrame."""
        try:
            import pandas as pd
            return isinstance(source, pd.DataFrame)
        except ImportError:
            return False
    
    @staticmethod
    def _handle_dict(source: dict, **kwargs) -> "ScenarioList":
        """Handle dictionary sources by checking structure and dispatching appropriately."""
        # Check if it's a serialized ScenarioList with "scenarios" key
        if "scenarios" in source:
            return ScenarioSource._from_dict(source)
        
        # Check if all values are dictionaries (nested dict structure)
        if all(isinstance(v, dict) for v in source.values()):
            id_field = kwargs.pop("id_field", None)
            return ScenarioSource._from_nested_dict(source, id_field=id_field)
        
        # Otherwise, assume it's a simple dict with field names mapping to lists
        return ScenarioSource._from_dict(source)
    
    @staticmethod
    def _handle_list(
        source: list,
        field_name: Optional[str] = None,
        **kwargs
    ) -> "ScenarioList":
        """Handle list sources by checking if it's a list of values or tuples."""
        if not source:
            # Empty list
            from .scenario_list import ScenarioList
            return ScenarioList()
        
        # Check if it's a list of tuples
        if isinstance(source[0], tuple):
            field_names = kwargs.pop("field_names", None)
            if field_names is None:
                raise ScenarioError(
                    "For a list of tuples, you must provide 'field_names' parameter."
                )
            use_indexes = kwargs.pop("use_indexes", False)
            return ScenarioSource.from_source(
                "list_of_tuples", field_names, source, use_indexes, **kwargs
            )
        
        # It's a simple list of values
        if field_name is None:
            field_name = "value"
            warnings.warn(
                f"No field_name provided for list source. Using default: '{field_name}'",
                UserWarning,
                stacklevel=3
            )
        
        use_indexes = kwargs.pop("use_indexes", False)
        return ScenarioSource.from_source("list", field_name, source, use_indexes, **kwargs)
    
    @staticmethod
    def _handle_string_or_path(
        source: Union[str, Path],
        field_name: Optional[str] = None,
        verbose: bool = False,
        **kwargs
    ) -> "ScenarioList":
        """Handle string or Path sources (URLs, file paths, or directories)."""
        source_str = str(source)
        
        # Check if it's a URL
        if ScenarioSourceInferrer._is_url(source_str):
            return ScenarioSourceInferrer._handle_url(source_str, verbose, **kwargs)
        
        # Check if it's a file or directory
        if os.path.exists(source_str):
            if os.path.isdir(source_str):
                return ScenarioSourceInferrer._handle_directory(source_str, verbose, **kwargs)
            elif os.path.isfile(source_str):
                return ScenarioSourceInferrer._handle_file(source_str, verbose, **kwargs)
        
        # If file doesn't exist, raise an error
        raise ScenarioError(
            f"File or directory not found: {source_str}"
        )
    
    @staticmethod
    def _is_url(source: str) -> bool:
        """Check if a string is a URL."""
        try:
            result = urlparse(source)
            return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
        except Exception:
            return False
    
    @staticmethod
    def _handle_url(url: str, verbose: bool = False, **kwargs) -> "ScenarioList":
        """Handle URL sources by checking the URL type."""
        url_lower = url.lower()
        
        # Check for Wikipedia
        if "wikipedia.org" in url_lower:
            if verbose:
                print(f"Detected source type: Wikipedia table at {url}")
            table_index = kwargs.pop("table_index", 0)
            header = kwargs.pop("header", True)
            return ScenarioSource.from_source("wikipedia", url, table_index, header, **kwargs)
        
        # Check for Google Sheets
        if "docs.google.com/spreadsheets" in url_lower or "sheets.google.com" in url_lower:
            if verbose:
                print(f"Detected source type: Google Sheet at {url}")
            sheet_name = kwargs.pop("sheet_name", None)
            column_names = kwargs.pop("column_names", None)
            return ScenarioSource.from_source(
                "google_sheet", url, sheet_name=sheet_name, column_names=column_names, **kwargs
            )
        
        # Check for Google Docs
        if "docs.google.com/document" in url_lower:
            if verbose:
                print(f"Detected source type: Google Doc at {url}")
            return ScenarioSource.from_source("google_doc", url, **kwargs)
        
        # Check for file extensions in URL
        if url_lower.endswith(".csv"):
            if verbose:
                print(f"Detected source type: CSV file at {url}")
            return ScenarioSource.from_source("csv", url, **kwargs)
        elif url_lower.endswith(".tsv"):
            if verbose:
                print(f"Detected source type: TSV file at {url}")
            return ScenarioSource.from_source("tsv", url, **kwargs)
        elif url_lower.endswith((".xls", ".xlsx")):
            if verbose:
                print(f"Detected source type: Excel file at {url}")
            sheet_name = kwargs.pop("sheet_name", None)
            return ScenarioSource.from_source("excel", url, sheet_name=sheet_name, **kwargs)
        elif url_lower.endswith(".pdf"):
            if verbose:
                print(f"Detected source type: PDF file at {url}")
            chunk_type = kwargs.pop("chunk_type", "page")
            chunk_size = kwargs.pop("chunk_size", 1)
            chunk_overlap = kwargs.pop("chunk_overlap", 0)
            return ScenarioSource.from_source(
                "pdf", url, chunk_type=chunk_type, 
                chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs
            )
        elif url_lower.endswith(".parquet"):
            if verbose:
                print(f"Detected source type: Parquet file at {url}")
            return ScenarioSource.from_source("parquet", url, **kwargs)
        
        # For other URLs, treat as generic URL source
        if verbose:
            print(f"Detected source type: generic URL at {url}")
        field_name = kwargs.pop("field_name", "text")
        return ScenarioSource._from_urls([url], field_name=field_name)
    
    @staticmethod
    def _handle_directory(directory: str, verbose: bool = False, **kwargs) -> "ScenarioList":
        """Handle directory sources."""
        if verbose:
            print(f"Detected source type: directory at {directory}")
        
        pattern = kwargs.pop("pattern", "*")
        recursive = kwargs.pop("recursive", False)
        metadata = kwargs.pop("metadata", True)
        ignore_dirs = kwargs.pop("ignore_dirs", None)
        ignore_files = kwargs.pop("ignore_files", None)
        
        return ScenarioSource.from_source(
            "directory", directory, pattern=pattern, recursive=recursive,
            metadata=metadata, ignore_dirs=ignore_dirs, ignore_files=ignore_files, **kwargs
        )
    
    @staticmethod
    def _handle_file(file_path: str, verbose: bool = False, **kwargs) -> "ScenarioList":
        """Handle file sources by examining the file extension."""
        file_lower = file_path.lower()
        
        # CSV files
        if file_lower.endswith(".csv"):
            if verbose:
                print(f"Detected source type: CSV file at {file_path}")
            return ScenarioSource.from_source("csv", file_path, **kwargs)
        
        # TSV files
        elif file_lower.endswith(".tsv"):
            if verbose:
                print(f"Detected source type: TSV file at {file_path}")
            return ScenarioSource.from_source("tsv", file_path, **kwargs)
        
        # Excel files
        elif file_lower.endswith((".xls", ".xlsx", ".xlsm")):
            if verbose:
                print(f"Detected source type: Excel file at {file_path}")
            sheet_name = kwargs.pop("sheet_name", None)
            return ScenarioSource.from_source("excel", file_path, sheet_name=sheet_name, **kwargs)
        
        # Parquet files
        elif file_lower.endswith(".parquet"):
            if verbose:
                print(f"Detected source type: Parquet file at {file_path}")
            return ScenarioSource.from_source("parquet", file_path, **kwargs)
        
        # PDF files
        elif file_lower.endswith(".pdf"):
            # Try to infer if user wants image extraction
            if kwargs.get("as_image", False) or kwargs.get("to_image", False):
                if verbose:
                    print(f"Detected source type: PDF file (as images) at {file_path}")
                base_width = kwargs.pop("base_width", 2000)
                include_text = kwargs.pop("include_text", True)
                return ScenarioSource.from_source(
                    "pdf_to_image", file_path, base_width=base_width, 
                    include_text=include_text, **kwargs
                )
            else:
                if verbose:
                    print(f"Detected source type: PDF file at {file_path}")
                chunk_type = kwargs.pop("chunk_type", "page")
                chunk_size = kwargs.pop("chunk_size", 1)
                chunk_overlap = kwargs.pop("chunk_overlap", 0)
                return ScenarioSource.from_source(
                    "pdf", file_path, chunk_type=chunk_type,
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap, **kwargs
                )
        
        # SQLite database
        elif file_lower.endswith((".db", ".sqlite", ".sqlite3")):
            if verbose:
                print(f"Detected source type: SQLite database at {file_path}")
            table = kwargs.pop("table", None)
            if table is None:
                raise ScenarioError(
                    "For SQLite database files, you must provide a 'table' parameter."
                )
            fields = kwargs.pop("fields", None)
            return ScenarioSource.from_source("sqlite", file_path, table, fields, **kwargs)
        
        # Stata files
        elif file_lower.endswith(".dta"):
            if verbose:
                print(f"Detected source type: Stata (.dta) file at {file_path}")
            include_metadata = kwargs.pop("include_metadata", True)
            return ScenarioSource.from_source("dta", file_path, include_metadata, **kwargs)
        
        # LaTeX files
        elif file_lower.endswith((".tex", ".latex")):
            if verbose:
                print(f"Detected source type: LaTeX file at {file_path}")
            table_index = kwargs.pop("table_index", 0)
            has_header = kwargs.pop("has_header", True)
            return ScenarioSource.from_source("latex", file_path, table_index, has_header, **kwargs)
        
        # Try generic delimited file for other text files
        elif file_lower.endswith((".txt", ".dat")):
            if verbose:
                print(f"Detected source type: delimited text file at {file_path}")
            delimiter = kwargs.pop("delimiter", ",")
            has_header = kwargs.pop("has_header", True)
            encoding = kwargs.pop("encoding", "utf-8")
            return ScenarioSource.from_source(
                "delimited_file", file_path, delimiter=delimiter,
                has_header=has_header, encoding=encoding, **kwargs
            )
        
        # Unknown file type
        else:
            raise ScenarioError(
                f"Unable to infer source type from file extension: {file_path}. "
                "Supported extensions: .csv, .tsv, .xls, .xlsx, .xlsm, .parquet, "
                ".pdf, .db, .sqlite, .sqlite3, .dta, .tex, .latex, .txt, .dat"
            )


# Convenience function for easier use
def from_any(source: Any, **kwargs) -> "ScenarioList":
    """
    Convenience function to create a ScenarioList from any supported source.
    
    This function automatically detects the source type and creates an appropriate
    ScenarioList object. It's a shorthand for ScenarioSourceInferrer.infer_and_create().
    
    Args:
        source: The data source to create a ScenarioList from
        **kwargs: Additional keyword arguments to pass to the specific source handler
    
    Returns:
        A ScenarioList object created from the source.
    
    Examples:
        >>> from edsl.scenarios import from_any
        >>> sl = from_any("data.csv")  # doctest: +SKIP
        >>> sl = from_any({"a": [1, 2], "b": [3, 4]})
    """
    return ScenarioSourceInferrer.infer_and_create(source, **kwargs)


__all__ = ["ScenarioSourceInferrer", "from_any"]

