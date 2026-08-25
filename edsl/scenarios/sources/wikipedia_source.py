"""Wikipedia table source for ScenarioList creation."""

from __future__ import annotations
from io import StringIO
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlparse

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class WikipediaSource(Source):
    """Create ScenarioList from tables in Wikipedia pages."""

    source_type = "wikipedia"

    MAX_RESPONSE_BYTES = 10 * 1024 * 1024
    MAX_REDIRECTS = 5

    def __init__(
        self,
        url: str,
        table_index: int = 0,
        header: bool = True,
        timeout: float = 30.0,
    ):
        """
        Initialize a WikipediaSource with a URL to a Wikipedia page.

        Args:
            url: The URL of the Wikipedia page.
            table_index: The index of the table to extract (default is 0).
            header: Whether the table has a header row (default is True).
        """
        from ..network import validate_request_timeout

        self._validate_url(url)
        self.url = url
        self.table_index = table_index
        self.header = header
        self.timeout = validate_request_timeout(timeout)

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not (hostname == "wikipedia.org" or hostname.endswith(".wikipedia.org"))
            or parsed.port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ScenarioError(
                "Wikipedia URLs must use HTTPS on a wikipedia.org host and the default port."
            )

    def _fetch_html(self, requests) -> str:
        current_url = self.url
        visited = set()
        for _ in range(self.MAX_REDIRECTS + 1):
            self._validate_url(current_url)
            if current_url in visited:
                raise ScenarioError("Wikipedia redirect loop detected.")
            visited.add(current_url)
            response = requests.get(
                current_url,
                stream=True,
                allow_redirects=False,
                timeout=self.timeout,
            )
            try:
                response.raise_for_status()
                if 300 <= response.status_code < 400:
                    location = response.headers.get("Location")
                    if not location:
                        raise ScenarioError("Wikipedia redirect omitted its Location header.")
                    current_url = urljoin(current_url, location)
                    continue
                content_type = response.headers.get("Content-Type", "")
                if not content_type.lower().startswith("text/html"):
                    raise ScenarioError("Wikipedia response is not HTML.")
                chunks = []
                size = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.MAX_RESPONSE_BYTES:
                        raise ScenarioError("Wikipedia response exceeds the size limit.")
                    chunks.append(chunk)
                encoding = response.encoding or "utf-8"
                return b"".join(chunks).decode(encoding, errors="replace")
            finally:
                response.close()
        raise ScenarioError("Wikipedia URL exceeded the redirect limit.")

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
            html = self._fetch_html(requests)
            tables = pd.read_html(StringIO(html), header=0 if self.header else None)

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
        except ScenarioError:
            raise
        except ValueError as e:
            raise ScenarioError(f"Error parsing tables: {str(e)}")
        except Exception as e:
            raise ScenarioError(f"An unexpected error occurred: {str(e)}")
