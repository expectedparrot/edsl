from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class CsvFormat(Enum):
    """Supported CSV layout types."""

    SIMPLE = "simple"
    QUALTRICS_THREE_ROW = "qualtrics_three_row"


@dataclass
class CsvProfile:
    """Detected CSV properties."""

    format: CsvFormat
    header_rows: int = 1
    delimiter: str = ","
    respondent_id_column: Optional[str] = None


def detect_csv_profile(path: Path, sample_size: int = 8) -> CsvProfile:
    """
    Inspect the CSV file and return a profile describing its layout.

    Parameters
    ----------
    path: Path
        CSV path
    sample_size: int
        Number of rows to inspect for detection
    """
    sample_lines = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for _, line in zip(range(sample_size), f):
            sample_lines.append(line.rstrip("\n"))

    delimiter = _infer_delimiter(sample_lines)

    # Heuristic detection for Qualtrics multi-header exports
    import_id_rows = sum(1 for line in sample_lines if '{"ImportId"' in line)
    column_pattern_rows = sum(1 for line in sample_lines if line.startswith("Column"))

    if import_id_rows:
        header_rows = 4 if column_pattern_rows else 3
        return CsvProfile(
            format=CsvFormat.QUALTRICS_THREE_ROW,
            header_rows=header_rows,
            delimiter=delimiter,
        )

    if column_pattern_rows:
        return CsvProfile(
            format=CsvFormat.QUALTRICS_THREE_ROW,
            header_rows=4,
            delimiter=delimiter,
        )

    return CsvProfile(format=CsvFormat.SIMPLE, header_rows=1, delimiter=delimiter)


def _infer_delimiter(lines: list[str]) -> str:
    """
    Infer the delimiter using csv.Sniffer while falling back to comma.
    """
    joined = "\n".join(lines[:5])
    try:
        dialect = csv.Sniffer().sniff(joined, delimiters=[",", "\t", ";", "|"])
        return dialect.delimiter
    except Exception:
        return ","
