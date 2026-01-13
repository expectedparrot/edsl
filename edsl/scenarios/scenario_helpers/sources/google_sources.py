"""Google Docs and Google Sheets sources for ScenarioList creation."""

from __future__ import annotations
import tempfile
from typing import List, Optional, TYPE_CHECKING

from .base import Source
from ...scenario import Scenario
from ...exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class GoogleDocSource(Source):
    """Create ScenarioList from Google Docs by paragraphs."""

    source_type = "google_doc"

    def __init__(self, url: str):
        """
        Initialize a GoogleDocSource with a Google Doc URL.

        Args:
            url: The URL to the Google Doc.
        """
        self.url = url

    @classmethod
    def example(cls) -> "GoogleDocSource":
        """Return an example GoogleDocSource instance."""
        # Create a mock instance that doesn't actually fetch a Google Doc
        instance = cls(
            url="https://docs.google.com/document/d/1234567890abcdefghijklmnopqrstuvwxyz/edit"
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from ...scenario_list import ScenarioList

            # Create a simple mock ScenarioList with a few paragraphs
            scenarios = [
                Scenario({"text": "This is paragraph 1 from a sample Google Doc."}),
                Scenario({"text": "This is paragraph 2 with some more content."}),
                Scenario({"text": "This is the final paragraph with a conclusion."}),
            ]
            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Google Doc."""
        from ...scenario_list import ScenarioList
        import requests

        # Extract the document ID from the URL
        if "/edit" in self.url:
            doc_id = self.url.split("/d/")[1].split("/edit")[0]
        else:
            raise ScenarioError("Invalid Google Doc URL format.")

        # Create the export URL to download as DOCX
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=docx"

        try:
            # Download the Google Doc as a Word file (.docx)
            response = requests.get(export_url)
            response.raise_for_status()  # Ensure the request was successful

            # Save the Word file to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_filename = temp_file.name

            # Use python-docx to process the temporary file
            try:
                from docx import Document
            except ImportError:
                raise ScenarioError(
                    "python-docx is required for Google Doc processing. "
                    "Install with: pip install python-docx"
                )

            # Create a scenario from the DOCX file
            doc = Document(temp_filename)
            scenarios = [
                Scenario({"text": paragraph.text})
                for paragraph in doc.paragraphs
                if paragraph.text.strip()  # Skip empty paragraphs
            ]

            return ScenarioList(scenarios)

        except requests.RequestException as e:
            raise ScenarioError(f"Failed to fetch Google Doc: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"Error processing Google Doc: {str(e)}")


class GoogleSheetSource(Source):
    """Create ScenarioList from Google Sheets."""

    source_type = "google_sheet"

    def __init__(
        self,
        url: str,
        sheet_name: Optional[str] = None,
        column_names: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        Initialize a GoogleSheetSource with a URL to a Google Sheet.

        Args:
            url: The URL of the Google Sheet.
            sheet_name: The name of the sheet to load. If None, the first sheet will be used.
            column_names: If provided, use these names for the columns instead
                         of the default column names from the sheet.
            **kwargs: Additional parameters to pass to pandas.read_excel.
        """
        self.url = url
        self.sheet_name = sheet_name
        self.column_names = column_names
        self.kwargs = kwargs

    @classmethod
    def example(cls) -> "GoogleSheetSource":
        """Return an example GoogleSheetSource instance."""
        # Use a mock instance since we can't create a real Google Sheet for testing
        instance = cls(
            url="https://docs.google.com/spreadsheets/d/1234567890abcdefg/edit",
            sheet_name="Sheet1",
        )

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

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Google Sheet."""
        from ...scenario_list import ScenarioList
        from .excel_source import ExcelSource
        import requests

        # Extract the sheet ID from the URL
        if "/edit" in self.url:
            sheet_id = self.url.split("/d/")[1].split("/edit")[0]
        else:
            raise ScenarioError("Invalid Google Sheet URL format.")

        # Create the export URL for XLSX format
        export_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        )

        try:
            # Download the Google Sheet as an Excel file
            response = requests.get(export_url)
            response.raise_for_status()  # Ensure the request was successful

            # Save the Excel file to a temporary file
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temp_file:
                temp_file.write(response.content)
                temp_filename = temp_file.name

            # Use ExcelSource to create the initial ScenarioList
            excel_source = ExcelSource(
                file_path=temp_filename, sheet_name=self.sheet_name, **self.kwargs
            )
            scenario_list = excel_source.to_scenario_list()

            # Apply column renaming if specified
            if self.column_names is not None and scenario_list:
                if len(self.column_names) != len(scenario_list[0].keys()):
                    raise ScenarioError(
                        f"Number of provided column names ({len(self.column_names)}) "
                        f"does not match number of columns in sheet ({len(scenario_list[0].keys())})"
                    )

                # Create a mapping from original keys to new names
                original_keys = list(scenario_list[0].keys())
                column_mapping = dict(zip(original_keys, self.column_names))

                # Create a new ScenarioList with renamed columns
                renamed_scenarios = []
                for scenario in scenario_list:
                    renamed_scenario = {
                        column_mapping.get(k, k): v for k, v in scenario.items()
                    }
                    renamed_scenarios.append(Scenario(renamed_scenario))

                return ScenarioList(renamed_scenarios)

            return scenario_list

        except requests.exceptions.RequestException as e:
            raise ScenarioError(f"Error fetching the Google Sheet: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"Error processing Google Sheet: {str(e)}")
