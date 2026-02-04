"""CSV reader for Qualtrics exports."""

import csv
from dataclasses import dataclass
from typing import List

from .data_classes import Column


@dataclass
class QualtricsCSVData:
    """Structured data from a Qualtrics CSV file."""

    short_labels: List[str]  # Row 1: Short labels (Q1, Q2_1, etc.)
    question_texts: List[str]  # Row 2: Question text
    import_ids: List[str]  # Row 3: Import IDs (JSON with QID)
    columns: List[Column]  # Data columns with values


class QualtricsCSVReader:
    """Read and parse Qualtrics CSV/TSV files.

    Handles:
    - Delimiter detection (comma vs tab)
    - Parsing the 3 header rows
    - Extracting data columns
    """

    def __init__(self, csv_file: str, verbose: bool = False):
        """
        Initialize the CSV reader.

        Args:
            csv_file: Path to the Qualtrics CSV/TSV file
            verbose: Print detailed processing information
        """
        self.csv_file = csv_file
        self.verbose = verbose

    def _detect_delimiter(self) -> str:
        """Detect the delimiter based on file extension and content."""
        if self.csv_file.endswith((".tab", ".tsv")):
            return "\t"

        # Auto-detect delimiter by checking first line
        with open(self.csv_file, "r", encoding="utf-8") as f:
            first_line = f.readline()
            if first_line.count("\t") > first_line.count(","):
                return "\t"

        return ","

    def read(self) -> QualtricsCSVData:
        """Read and parse the Qualtrics CSV file.

        Returns:
            QualtricsCSVData containing headers and data columns

        Raises:
            ValueError: If the file has fewer than 4 rows
        """
        if self.verbose:
            print(f"Reading CSV file: {self.csv_file}")

        delimiter = self._detect_delimiter()

        with open(self.csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=delimiter)
            rows = list(reader)

        if len(rows) < 4:
            raise ValueError(
                "Qualtrics CSV must have at least 4 rows: 3 header rows + 1 data row"
            )

        # Extract the three header rows
        short_labels = rows[0]
        question_texts = rows[1]
        import_ids = rows[2]
        data_rows = rows[3:]

        # Create columns from data
        columns = []
        for col_idx, short_label in enumerate(short_labels):
            values = [row[col_idx] if col_idx < len(row) else "" for row in data_rows]
            columns.append(Column(name=short_label, _values=values))

        if self.verbose:
            print(f"Loaded {len(columns)} columns, {len(data_rows)} responses")

        return QualtricsCSVData(
            short_labels=short_labels,
            question_texts=question_texts,
            import_ids=import_ids,
            columns=columns,
        )
