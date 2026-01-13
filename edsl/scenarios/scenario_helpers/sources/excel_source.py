"""Excel file source for ScenarioList creation."""

from __future__ import annotations
import os
from typing import List, Optional, TYPE_CHECKING

from .base import Source
from ...scenario import Scenario
from ...exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class ExcelSource(Source):
    """Create ScenarioList from Excel (.xlsx) files."""

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
                from ...scenario_list import ScenarioList

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
        from ...scenario_list import ScenarioList

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

        # Handle sheet name matching with case-insensitive fallback
        if sheet_name is not None:
            available_sheets = list(all_sheets.keys())

            # First try exact match
            if sheet_name not in available_sheets:
                # Try case-insensitive match
                sheet_name_lower = sheet_name.lower()
                matching_sheets = [
                    s for s in available_sheets if s.lower() == sheet_name_lower
                ]

                if matching_sheets:
                    sheet_name = matching_sheets[0]  # Use the first match
                else:
                    # No match found, provide helpful error
                    available_sheets_str = ", ".join(
                        [f"'{name}'" for name in available_sheets]
                    )
                    raise ScenarioError(
                        f"Worksheet named '{sheet_name}' not found. "
                        f"Available sheets: {available_sheets_str}"
                    )

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
