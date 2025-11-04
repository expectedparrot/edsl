"""Wikipedia table source for ScenarioList creation."""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class WikipediaSource(Source):
    """Create ScenarioList from tables in Wikipedia pages."""

    source_type = "wikipedia"

    def __init__(self, url: str, table_index: int = 0, header: bool = True):
        """
        Initialize a WikipediaSource with a URL to a Wikipedia page.

        Args:
            url: The URL of the Wikipedia page.
            table_index: The index of the table to extract (default is 0).
            header: Whether the table has a header row (default is True).
        """
        self.url = url
        self.table_index = table_index
        self.header = header

    @classmethod
    def example(cls) -> "WikipediaSource":
        """Return an example WikipediaSource instance."""
        # Use a real Wikipedia URL for the example, but we'll override the to_scenario_list method
        instance = cls(
            url="https://en.wikipedia.org/wiki/List_of_countries_by_GDP_(nominal)",
            table_index=0,
            header=True,
        )

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from ..scenario_list import ScenarioList

            # Create a simple mock ScenarioList with GDP data
            scenarios = [
                Scenario(
                    {
                        "Rank": 1,
                        "Country": "United States",
                        "GDP (millions of USD)": 25460000,
                    }
                ),
                Scenario(
                    {"Rank": 2, "Country": "China", "GDP (millions of USD)": 17963000}
                ),
                Scenario(
                    {"Rank": 3, "Country": "Japan", "GDP (millions of USD)": 4231000}
                ),
                Scenario(
                    {"Rank": 4, "Country": "Germany", "GDP (millions of USD)": 4430000}
                ),
                Scenario(
                    {"Rank": 5, "Country": "India", "GDP (millions of USD)": 3737000}
                ),
            ]

            return ScenarioList(scenarios)

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a table on a Wikipedia page."""
        from ..scenario_list import ScenarioList
        import requests

        try:
            # Try to import pandas
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Wikipedia tables")

        try:
            # Check if the URL is reachable
            response = requests.get(self.url)
            response.raise_for_status()  # Raises HTTPError for bad responses

            # Extract tables from the Wikipedia page
            tables = pd.read_html(self.url, header=0 if self.header else None)

            # Ensure the requested table index is within the range of available tables
            if self.table_index >= len(tables) or self.table_index < 0:
                raise ScenarioError(
                    f"Table index {self.table_index} is out of range. This page has {len(tables)} table(s)."
                )

            # Get the requested table
            df = tables[self.table_index]

            # Convert DataFrame to ScenarioList
            scenarios = []
            for _, row in df.iterrows():
                scenario_dict = row.to_dict()
                scenarios.append(Scenario(scenario_dict))

            return ScenarioList(scenarios)

        except requests.exceptions.RequestException as e:
            raise ScenarioError(f"Error fetching the URL: {str(e)}")
        except ValueError as e:
            raise ScenarioError(f"Error parsing tables: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"An unexpected error occurred: {str(e)}")
