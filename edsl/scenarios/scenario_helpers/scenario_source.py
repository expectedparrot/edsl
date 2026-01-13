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

All source implementations are now organized in the sources/ subdirectory.
"""

from __future__ import annotations
import warnings
from typing import (
    List,
    Literal,
    Optional,
    TYPE_CHECKING,
)

# Import all source classes from the sources package
from .sources import (
    Source,
    URLSource,
    ListSource,
    TuplesSource,
    DirectorySource,
    SQLiteSource,
    LaTeXSource,
    GoogleDocSource,
    PandasSource,
    StataSource,
    WikipediaSource,
    ExcelSource,
    GoogleSheetSource,
    DelimitedFileSource,
    CSVSource,
    TSVSource,
    ParquetSource,
    PDFSource,
    PDFImageSource,
)

# Local imports
from ..scenario import Scenario
from ..exceptions import UnsupportedSourceTypeError, ScenarioError

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


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
        except ValueError:
            # For backward compatibility, try the old method if the source_type isn't in the registry
            method_name = f"_from_{source_type}"
            if hasattr(ScenarioSource, method_name):
                method = getattr(ScenarioSource, method_name)
                return method(*args, **kwargs)
            else:
                raise UnsupportedSourceTypeError(
                    f"Unsupported source type: {source_type}. "
                    f"Valid source types: {Source.get_registered_types()}"
                )

    @staticmethod
    def _from_urls(urls: list[str], field_name: Optional[str] = "text"):
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
        from ..scenario_list import ScenarioList

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
            if not all(length == list_lengths[0] for length in list_lengths):
                raise ScenarioError("All lists must have the same length")

            # Create scenarios
            for i in range(list_lengths[0]):
                scenario_dict = {k: data[k][i] for k in field_names}
                scenarios.append(Scenario(scenario_dict))

            return ScenarioList(scenarios)

    @staticmethod
    def _from_nested_dict(data: dict, id_field: Optional[str] = None):
        """Create a ScenarioList from a nested dictionary."""
        from ..scenario_list import ScenarioList

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


# Re-export all source classes for backward compatibility
__all__ = [
    "ScenarioSource",
    "Source",
    "URLSource",
    "ListSource",
    "TuplesSource",
    "DirectorySource",
    "SQLiteSource",
    "LaTeXSource",
    "GoogleDocSource",
    "PandasSource",
    "StataSource",
    "WikipediaSource",
    "ExcelSource",
    "GoogleSheetSource",
    "DelimitedFileSource",
    "CSVSource",
    "TSVSource",
    "ParquetSource",
    "PDFSource",
    "PDFImageSource",
]
