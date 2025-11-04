"""CSV and delimited file sources for ScenarioList creation."""

from __future__ import annotations
import csv
import warnings
from io import StringIO
from urllib.parse import urlparse
from collections import defaultdict
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class DelimitedFileSource(Source):
    """Create ScenarioList from delimited text files (CSV, TSV, etc.)."""

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
        from ..scenario_list import ScenarioList
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
                        "Failed to decode file with any of the attempted encodings"
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
    """Create ScenarioList from CSV files."""

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
    """Create ScenarioList from TSV (tab-separated values) files."""

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
