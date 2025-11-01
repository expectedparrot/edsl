"""
Sources package for ScenarioList creation.

This package contains modular source implementations for creating ScenarioList
objects from various external data sources like files, directories, URLs, and databases.
Each source type is implemented in its own module for better maintainability.
"""

# Base classes and utilities
from .base import Source, deprecated_classmethod

# Individual source implementations
from .url_source import URLSource
from .list_source import ListSource
from .tuples_source import TuplesSource
from .directory_source import DirectorySource
from .sqlite_source import SQLiteSource
from .latex_source import LaTeXSource
from .pandas_source import PandasSource
from .csv_source import DelimitedFileSource, CSVSource, TSVSource
from .excel_source import ExcelSource
from .google_sources import GoogleDocSource, GoogleSheetSource
from .wikipedia_source import WikipediaSource
from .stata_source import StataSource
from .parquet_source import ParquetSource
from .pdf_sources import PDFSource, PDFImageSource

__all__ = [
    # Base
    "Source",
    "deprecated_classmethod",
    # Sources
    "URLSource",
    "ListSource",
    "TuplesSource",
    "DirectorySource",
    "SQLiteSource",
    "LaTeXSource",
    "PandasSource",
    "DelimitedFileSource",
    "CSVSource",
    "TSVSource",
    "ExcelSource",
    "GoogleDocSource",
    "GoogleSheetSource",
    "WikipediaSource",
    "StataSource",
    "ParquetSource",
    "PDFSource",
    "PDFImageSource",
]

