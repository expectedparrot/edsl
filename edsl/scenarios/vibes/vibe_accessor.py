"""
ScenarioList Vibe Accessor: Provides a namespace for vibe-based scenario list methods.

This module provides the ScenarioListVibeAccessor class that enables the
`scenario_list.vibe.extract()`, `scenario_list.vibe.describe()`, and `scenario_list.vibe.filter()`
interface pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList
    from ..scenario import Scenario


class ScenarioListVibeAccessor:
    """
    Accessor class for vibe-based scenario list methods.

    This class provides a namespace for all vibe-related scenario list methods,
    enabling the `scenario_list.vibe.*` interface pattern.

    Examples
    --------
    >>> from edsl.scenarios import ScenarioList
    >>> sl = ScenarioList.example()  # doctest: +SKIP
    >>> sl.vibe.describe()  # doctest: +SKIP
    >>> sl.vibe.filter("Keep only people over 30")  # doctest: +SKIP
    >>> new_sl = ScenarioList.vibe.extract("<table>...</table>")  # doctest: +SKIP
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """
        Initialize the accessor with a scenario list instance.

        Args:
            scenario_list: The ScenarioList instance to operate on
        """
        self._scenario_list = scenario_list

    @classmethod
    def extract(
        cls,
        html_source: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        instructions: str = "",
        max_rows: Optional[int] = None,
    ) -> "ScenarioList":
        """Create a ScenarioList by extracting table data from HTML using LLM.

        Uses an LLM to analyze HTML content containing tables and extract
        structured data to create scenarios.

        Args:
            html_source: Either HTML string content or path to an HTML file
            model: OpenAI model to use for extraction (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.0 for consistency)
            instructions: Additional extraction instructions (optional)
            max_rows: Maximum number of rows to extract (None = all rows)

        Returns:
            ScenarioList: The extracted scenarios

        Examples:
            From HTML string:

            >>> html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"  # doctest: +SKIP
            >>> sl = ScenarioList.vibe.extract(html)  # doctest: +SKIP
            >>> len(sl)  # doctest: +SKIP
            1
            >>> sl[0]["name"]  # doctest: +SKIP
            'Alice'

            From file:

            >>> sl = ScenarioList.vibe.extract("data.html")  # doctest: +SKIP

            With custom instructions:

            >>> sl = ScenarioList.vibe.extract(  # doctest: +SKIP
            ...     html,
            ...     instructions="Focus on demographic data",
            ...     max_rows=100
            ... )
        """
        import os

        # Import here to avoid circular imports
        from ..scenario_list import ScenarioList
        from . import extract_from_html_with_vibes

        # Check if html_source is a file path
        if os.path.exists(html_source) and os.path.isfile(html_source):
            # Read the file
            with open(html_source, "r", encoding="utf-8") as f:
                html_content = f.read()
        else:
            # Treat as HTML content string
            html_content = html_source

        scenario_list, metadata = extract_from_html_with_vibes(
            html_content,
            model=model,
            temperature=temperature,
            instructions=instructions,
            max_rows=max_rows,
        )

        # Store metadata as an attribute on the ScenarioList for reference
        scenario_list._extraction_metadata = metadata

        return scenario_list

    @classmethod
    def from_vibes(cls, description: str) -> "ScenarioList":
        """Create a ScenarioList from a vibe description.

        Args:
            description: A description of the vibe.

        Returns:
            ScenarioList: New scenario list generated from the description

        Examples:
            >>> sl = ScenarioList.vibe.from_vibes("Customer demographics")  # doctest: +SKIP
            >>> sl = ScenarioList.vibe.from_vibes("Software engineers with experience levels")  # doctest: +SKIP
        """
        # Import here to avoid circular imports
        from ..scenario_list import ScenarioList

        return ScenarioList.from_vibes(description)

    def describe(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_sample_values: int = 5,
    ) -> "Scenario":
        """Generate a title and description for the scenario list.

        This method uses an LLM to analyze the scenario list and generate
        a descriptive title and detailed description of what the scenario list represents.

        Args:
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            max_sample_values: Maximum number of sample values to include per key (default: 5)

        Returns:
            Scenario: Scenario with keys:
                - "proposed_title": A single sentence title for the scenario list
                - "description": A paragraph-length description of the scenario list

        Examples:
            Basic usage:

            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([  # doctest: +SKIP
            ...     Scenario({"name": "Alice", "age": 30, "city": "NYC"}),  # doctest: +SKIP
            ...     Scenario({"name": "Bob", "age": 25, "city": "SF"})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> description = sl.vibe.describe()  # doctest: +SKIP
            >>> print(description["proposed_title"])  # doctest: +SKIP
            >>> print(description["description"])  # doctest: +SKIP

            Using a different model:

            >>> sl = ScenarioList.vibe.from_vibes("Customer demographics")  # doctest: +SKIP
            >>> description = sl.vibe.describe(model="gpt-4o-mini")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The title will be a single sentence that captures the scenario list's essence
            - The description will be a paragraph explaining what the data represents
            - Analyzes all unique keys and samples values to understand the data theme
            - If a codebook is present, it will be included in the analysis
        """
        return self._scenario_list.vibe_describe(
            model=model,
            temperature=temperature,
            max_sample_values=max_sample_values,
        )

    def filter(
        self,
        criteria: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        show_expression: bool = False,
    ) -> "ScenarioList":
        """Filter the scenario list using natural language criteria.

        This method uses an LLM to generate a filter expression based on
        natural language criteria, then applies it using the scenario list's filter method.

        Args:
            criteria: Natural language description of the filtering criteria.
                Examples:
                - "Keep only people over 30"
                - "Remove scenarios with missing data"
                - "Only include scenarios from the US"
            model: OpenAI model to use for generating the filter (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.1 for consistency)
            show_expression: If True, prints the generated filter expression

        Returns:
            ScenarioList: A new filtered scenario list

        Examples:
            Basic filtering:

            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([  # doctest: +SKIP
            ...     Scenario({"name": "Alice", "age": 30, "city": "NYC"}),  # doctest: +SKIP
            ...     Scenario({"name": "Bob", "age": 25, "city": "SF"})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> filtered = sl.vibe.filter("Keep only people over 25")  # doctest: +SKIP
            >>> len(filtered)  # doctest: +SKIP
            2

            With expression display:

            >>> filtered = sl.vibe.filter(  # doctest: +SKIP
            ...     "Keep only people from NYC",
            ...     show_expression=True
            ... )

            Complex criteria:

            >>> filtered = sl.vibe.filter("Keep people aged 25-35 from major cities")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - Uses LLM to generate Python expressions with operators: ==, !=, >, <, >=, <=, in, and, or, not
            - The generated expression is applied using the scenario list's built-in filter() method
            - Supports complex boolean logic and range operations
        """
        # Import here to avoid circular imports
        from .vibe_filter import VibeFilter

        # Get scenario keys and sample data
        if not self._scenario_list:
            return self._scenario_list

        # Collect all keys present across all scenarios
        all_keys = set()
        for scenario in self._scenario_list:
            all_keys.update(scenario.keys())
        keys = list(all_keys)
        sample_scenarios = [scenario.to_dict() for scenario in self._scenario_list[:3]]

        # Create vibe filter and generate expression
        vibe_filter = VibeFilter(model=model, temperature=temperature)
        filter_expression = vibe_filter.create_filter(keys, sample_scenarios, criteria)

        if show_expression:
            print(f"Generated filter expression: {filter_expression}")

        # Use the scenario list's filter method with the generated expression
        return self._scenario_list.filter(filter_expression)