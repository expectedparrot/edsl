"""
ScenarioList Vibe Accessor: Provides a namespace for vibe-based scenario list methods.

This module provides the ScenarioListVibeAccessor class that enables the
`scenario_list.vibe.describe()`, `scenario_list.vibe.filter()`, and `scenario_list.vibe.edit()`
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
    >>> sl.vibe.edit("Add a 'country' field to all scenarios")  # doctest: +SKIP
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """
        Initialize the accessor with a scenario list instance.

        Args:
            scenario_list: The ScenarioList instance to operate on
        """
        self._scenario_list = scenario_list

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

            >>> sl = ScenarioList.from_vibes("Customer demographics")  # doctest: +SKIP
            >>> description = sl.vibe.describe(model="gpt-4o-mini")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The title will be a single sentence that captures the scenario list's essence
            - The description will be a paragraph explaining what the data represents
            - Analyzes all unique keys and samples values to understand the data theme
            - If a codebook is present, it will be included in the analysis
        """
        # Import here to avoid circular imports
        from .vibe_describer import VibeDescribe
        from ..scenario import Scenario

        # Return empty scenario if no scenarios
        if not self._scenario_list:
            return Scenario(
                {
                    "proposed_title": "Empty Scenario List",
                    "description": "This scenario list contains no scenarios.",
                }
            )

        # Collect all keys present across all scenarios
        all_keys = set()
        for scenario in self._scenario_list:
            all_keys.update(scenario.keys())
        keys = list(all_keys)

        # Sample values for each key (up to max_sample_values)
        sample_values = {}
        for key in keys:
            values = []
            for scenario in self._scenario_list:
                if key in scenario and len(values) < max_sample_values:
                    value = scenario[key]
                    if value not in values:  # Avoid duplicates
                        values.append(value)
            sample_values[key] = values

        # Check if there's a codebook attribute
        codebook = getattr(self._scenario_list, "_codebook", None)

        # Prepare data for the describer
        scenario_data = {
            "keys": keys,
            "sample_values": sample_values,
            "num_scenarios": len(self._scenario_list),
        }

        if codebook:
            scenario_data["codebook"] = codebook

        # Create describer and generate description
        describer = VibeDescribe(model=model, temperature=temperature)
        result = describer.describe_scenario_list(scenario_data)

        # Return as a Scenario object
        return Scenario(result)

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

    def edit(
        self,
        edit_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
    ) -> "ScenarioList":
        """Edit the scenario list using natural language instructions.

        This method uses an LLM to modify an existing scenario list based on natural language
        instructions. It can modify scenario values, add or remove fields, change field values,
        filter scenarios, or make other modifications as requested.

        Args:
            edit_instructions: Natural language description of the edits to apply.
                Examples:
                - "Make all ages 10 years older"
                - "Add a 'country' field to all scenarios"
                - "Remove scenarios with missing data"
                - "Translate all text fields to Spanish"
                - "Make the data more diverse"
            model: OpenAI model to use for editing (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)

        Returns:
            ScenarioList: A new ScenarioList instance with the edited scenarios

        Examples:
            Basic usage:

            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([  # doctest: +SKIP
            ...     Scenario({"name": "Alice", "age": 30}),  # doctest: +SKIP
            ...     Scenario({"name": "Bob", "age": 25})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> edited = sl.vibe.edit("Make all ages 5 years older")  # doctest: +SKIP

            Add a new field:

            >>> edited = sl.vibe.edit("Add a 'city' field to all scenarios")  # doctest: +SKIP

            Complex edits:

            >>> edited = sl.vibe.edit("Make the data more diverse in terms of demographics")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - Uses structured LLM output to ensure consistent scenario definitions
            - Can add, modify, or remove scenario fields
            - Can filter scenarios based on criteria
            - Maintains scenario structure when possible
            - Returns a completely new ScenarioList instance
        """
        # Import here to avoid circular imports
        from .vibe_editor import ScenarioListVibeEdit
        from ..scenario import Scenario

        # Convert current scenarios to dict format
        current_scenarios = [scenario.to_dict() for scenario in self._scenario_list]

        # Create the editor
        editor = ScenarioListVibeEdit(model=model, temperature=temperature)

        # Edit the scenario list
        edited_data = editor.edit_scenario_list(current_scenarios, edit_instructions)

        # Convert each edited scenario definition to a Scenario object
        scenarios = []
        for scenario_def in edited_data["scenarios"]:
            scenario = Scenario(scenario_def)
            scenarios.append(scenario)

        return self._scenario_list.__class__(scenarios)
