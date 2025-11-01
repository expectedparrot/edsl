"""LaTeX file source for ScenarioList creation."""

from __future__ import annotations
import os
import re
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class LaTeXSource(Source):
    """Create ScenarioList from tables in LaTeX files."""
    
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
        from ..scenario_list import ScenarioList

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

