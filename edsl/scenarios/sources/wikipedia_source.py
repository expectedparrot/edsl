"""Wikipedia table source for ScenarioList creation."""

from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class WikipediaTableCollection:
    """Container for multiple ScenarioLists from Wikipedia tables."""

    def __init__(self, scenario_lists: List, url: str):
        """
        Initialize a collection of ScenarioLists from Wikipedia tables.

        Args:
            scenario_lists: List of ScenarioList objects
            url: The Wikipedia URL these tables came from
        """
        self.scenario_lists = scenario_lists
        self.url = url
        self._table_summaries = None

    def __len__(self) -> int:
        """Return the number of tables."""
        return len(self.scenario_lists)

    def __getitem__(self, index: int):
        """Get a ScenarioList by index."""
        return self.scenario_lists[index]

    def __repr__(self) -> str:
        """Return a string representation of the collection."""
        return f"WikipediaTableCollection({len(self)} tables from {self.url})"

    def get_table_summaries(self) -> List[dict]:
        """
        Get summaries of each table including row count and column names.

        Returns:
            List of dictionaries with table metadata
        """
        if self._table_summaries is None:
            self._table_summaries = []
            for i, scenario_list in enumerate(self.scenario_lists):
                if len(scenario_list) > 0:
                    columns = list(scenario_list[0].keys())
                else:
                    columns = []

                self._table_summaries.append(
                    {
                        "index": i,
                        "rows": len(scenario_list),
                        "columns": columns,
                        "column_count": len(columns),
                    }
                )

        return self._table_summaries

    def print_summary(self):
        """Print a summary of all tables in the collection."""
        print(f"📊 WikipediaTableCollection: Found {len(self)} tables from {self.url}")
        print(
            "💡 Tip: Use tables[index] to get a specific table, or tables.get_largest_table() for the biggest one\n"
        )

        for summary in self.get_table_summaries():
            print(
                f"Table {summary['index']}: {summary['rows']} rows, {summary['column_count']} columns"
            )
            if summary["columns"]:
                columns_display = summary["columns"][:5]  # Show first 5 columns
                if len(summary["columns"]) > 5:
                    columns_display.append("...")
                print(f"  - Columns: {columns_display}")
            print()

    def get_largest_table(self) -> tuple:
        """
        Get the table with the most rows.

        Returns:
            Tuple of (index, ScenarioList) for the largest table
        """
        summaries = self.get_table_summaries()

        # Just return the table with the most rows
        largest_table = max(summaries, key=lambda x: x["rows"])
        return largest_table["index"], self.scenario_lists[largest_table["index"]]


class WikipediaSource(Source):
    """
    Create ScenarioList from tables in Wikipedia pages.

    This source can operate in two modes:
    1. Single table mode: When table_index is specified (default 0), returns a ScenarioList from that specific table.
    2. Multi-table mode: When table_index is None, returns a WikipediaTableCollection
       containing all tables from the page.

    Examples:
        # If multiple tables exist, you'll get a helpful error showing all tables
        try:
            sl = ScenarioList.from_source("wikipedia", "https://en.wikipedia.org/wiki/List_of_current_United_States_senators")
        except ScenarioError as e:
            print(e)  # Shows all available tables with row counts and columns

        # Specify which table you want by index
        senators = ScenarioList.from_source("wikipedia", "https://en.wikipedia.org/wiki/List_of_current_United_States_senators", table_index=5)

        # For advanced multi-table operations
        tables = WikipediaSource.all_tables("https://en.wikipedia.org/wiki/List_of_current_United_States_senators")
        tables.print_summary()  # Shows all available tables
        largest_index, largest_table = tables.get_largest_table()
        specific_table = tables[5]  # Get table 5 directly
    """

    source_type = "wikipedia"

    def __init__(self, url: str, table_index: Optional[int] = 0, header: bool = True):
        """
        Initialize a WikipediaSource with a URL to a Wikipedia page.

        Args:
            url: The URL of the Wikipedia page.
            table_index: The index of the table to extract. If None, all tables are returned
                        in a WikipediaTableCollection (default is 0 for backward compatibility).
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
            table_index=0,  # Explicitly set to 0 for the example
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
        """
        Create a ScenarioList from a table on a Wikipedia page, or WikipediaTableCollection for all tables.

        Returns:
            ScenarioList if table_index is specified, WikipediaTableCollection if table_index is None.
        """
        if self.table_index is None:
            return self.to_table_collection()
        else:
            return self._get_single_table()

    def _get_single_table(self):
        """Get a single table as ScenarioList."""
        from ..scenario_list import ScenarioList

        tables = self._fetch_all_tables()

        # Ensure the requested table index is within the range of available tables
        if self.table_index >= len(tables) or self.table_index < 0:
            raise ScenarioError(
                f"Table index {self.table_index} is out of range. This page has {len(tables)} table(s)."
            )

        # If there are multiple tables and user didn't specify an index (using default 0),
        # show them what's available and ask them to choose
        if len(tables) > 1 and self.table_index == 0:
            # Create temporary scenario lists to get column info
            table_info = []
            for i, df in enumerate(tables):
                if len(df) > 0:
                    columns = list(df.columns)[:3]  # Show first 3 columns
                    if len(df.columns) > 3:
                        columns.append("...")
                else:
                    columns = []
                table_info.append({"index": i, "rows": len(df), "columns": columns})

            # Build helpful error message
            error_msg = f"Multiple tables found ({len(tables)} tables). Please specify which table you want:\n\n"
            for info in table_info:
                error_msg += f"Table {info['index']}: {info['rows']} rows"
                if info["columns"]:
                    error_msg += f" - Columns: {info['columns']}"
                error_msg += "\n"

            error_msg += (
                "\nUsage: ScenarioList.from_source('wikipedia', 'URL', table_index=N)"
            )
            error_msg += (
                "\nExample: ScenarioList.from_source('wikipedia', 'URL', table_index=5)"
            )

            raise ScenarioError(error_msg)

        # Get the requested table
        df = tables[self.table_index]

        # Convert DataFrame to ScenarioList
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        scenario_list = ScenarioList(scenarios)
        print(
            f"📋 Retrieved table {self.table_index} with {len(scenario_list)} rows from Wikipedia"
        )

        return scenario_list

    def to_table_collection(self) -> WikipediaTableCollection:
        """
        Create a WikipediaTableCollection containing all tables from the Wikipedia page.

        Returns:
            WikipediaTableCollection with all tables from the page.
        """
        from ..scenario_list import ScenarioList

        tables = self._fetch_all_tables()

        # Convert all tables to ScenarioLists
        scenario_lists = []
        for df in tables:
            scenarios = []
            for _, row in df.iterrows():
                scenario_dict = row.to_dict()
                scenarios.append(Scenario(scenario_dict))
            scenario_lists.append(ScenarioList(scenarios))

        return WikipediaTableCollection(scenario_lists, self.url)

    @classmethod
    def all_tables(cls, url: str, header: bool = True) -> WikipediaTableCollection:
        """
        Convenience method to get all tables from a Wikipedia page.

        Args:
            url: The URL of the Wikipedia page.
            header: Whether tables have header rows (default is True).

        Returns:
            WikipediaTableCollection with all tables from the page.
        """
        source = cls(url=url, table_index=None, header=header)
        tables = source.to_table_collection()
        print(f"🔍 Retrieved {len(tables)} tables from Wikipedia page")
        print(
            "💡 Use .print_summary() to see all tables, or access specific tables with [index]"
        )
        return tables

    def _fetch_all_tables(self):
        """Fetch all tables from the Wikipedia page."""
        import requests

        try:
            # Try to import pandas
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Wikipedia tables")

        try:
            # Set up headers to avoid 403 errors from Wikipedia
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }

            # Check if the URL is reachable
            response = requests.get(self.url, headers=headers)
            response.raise_for_status()  # Raises HTTPError for bad responses

            # Extract tables from the Wikipedia page
            # Pass the response content to pandas instead of the URL to avoid double request
            tables = pd.read_html(response.content, header=0 if self.header else None)

            return tables

        except requests.exceptions.RequestException as e:
            raise ScenarioError(f"Error fetching the URL: {str(e)}")
        except ValueError as e:
            raise ScenarioError(f"Error parsing tables: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"An unexpected error occurred: {str(e)}")
