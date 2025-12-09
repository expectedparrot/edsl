"""
AgentListBuilder provides factory methods for creating AgentList objects from external sources.

This module contains the AgentListBuilder class, which serves as a factory for creating
AgentList objects from various external data sources. It leverages the existing ScenarioList
functionality and provides a unified interface for creating agents with optional instructions
and codebooks.

Key features include:
- A unified from_source method that dispatches to ScenarioList.from_source
- Support for applying instructions to all created agents
- Support for codebooks and name fields
- Backward compatibility with existing from_csv functionality
"""

from __future__ import annotations
import warnings
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_list import AgentList


class AgentListBuilder:
    """
    Factory class for creating AgentList objects from various sources.

    This class provides static methods for creating AgentList objects from different
    data sources, leveraging the existing ScenarioList functionality and adding
    agent-specific features like instructions.
    """

    @staticmethod
    def from_source(
        source_type_or_data,
        *args,
        instructions: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        name_field: Optional[str] = None,
        **kwargs,
    ) -> "AgentList":
        """
        Create an AgentList from a specified source type or infer it automatically.

        This method serves as the main entry point for creating AgentList objects,
        providing a unified interface for various data sources while adding support
        for agent-specific parameters like instructions.

        **Two modes of operation:**

        1. **Explicit source type** (2+ arguments): Specify the source type explicitly
           Example: AgentList.from_source('csv', 'data.csv')

        2. **Auto-detect source** (1 argument): Pass only the data and let it infer the type
           Example: AgentList.from_source('data.csv') or AgentList.from_source({'key': [1,2,3]})

        Args:
            source_type_or_data: Either:
                - A string specifying the source type ('csv', 'excel', 'pdf', etc.)
                  when using explicit mode with additional args
                - The actual data source (file path, URL, dict, DataFrame, etc.)
                  when using auto-detect mode
            *args: Positional arguments to pass to the source-specific method
                   (only used in explicit mode).
            instructions: Optional instructions to apply to all created agents.
            codebook: Optional dictionary mapping trait names to descriptions, or a path to a CSV file.
                     If a CSV file is provided, it should have 2 columns: original keys and descriptions.
                     Keys will be automatically converted to pythonic names.
            name_field: The name of the field to use as the agent name (for CSV/Excel sources).
            **kwargs: Additional keyword arguments to pass to the source-specific method.

        Returns:
            An AgentList object created from the specified source.

        Examples:
            >>> # Explicit source type (original behavior)
            >>> agents = AgentListBuilder.from_source(  # doctest: +SKIP
            ...     'csv', 'agents.csv',
            ...     instructions="Answer as if you were the person described"
            ... )

            >>> # Auto-detect source type (new behavior)
            >>> agents = AgentListBuilder.from_source(  # doctest: +SKIP
            ...     'agents.csv',
            ...     instructions="Answer as if you were the person described"
            ... )

            >>> # Auto-detect from dictionary
            >>> agents = AgentListBuilder.from_source(  # doctest: +SKIP
            ...     {'age': [25, 30], 'name': ['Alice', 'Bob']},
            ...     instructions="You are this person"
            ... )
        """
        from ..scenarios import ScenarioList
        from .agent_list import AgentList

        # Create ScenarioList from the source (it handles auto-detection)
        scenario_list = ScenarioList.from_source(source_type_or_data, *args, **kwargs)

        # Convert to AgentList
        agent_list = AgentList.from_scenario_list(scenario_list)

        # Apply name field if specified (for CSV-like sources)
        if name_field and hasattr(agent_list, "data") and len(agent_list.data) > 0:
            new_agents = []
            for agent in agent_list.data:
                if name_field in agent.traits:
                    agent_name = agent.traits.pop(name_field)
                    agent.name = agent_name
                new_agents.append(agent)
            agent_list.data = new_agents

        # Apply instructions if specified
        if instructions:
            agent_list.set_instruction(instructions)

        # Apply codebook if specified
        if codebook:
            # Check if codebook is a CSV file path
            if isinstance(codebook, str) and codebook.lower().endswith(".csv"):
                codebook = AgentListBuilder._load_codebook_from_csv(codebook)
            agent_list.set_codebook(codebook)

        return agent_list

    @staticmethod
    def from_csv(
        file_path: str,
        name_field: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ) -> "AgentList":
        """
        Load AgentList from a CSV file.

        .. deprecated::
            Use `AgentListBuilder.from_source('csv', ...)` instead.

        Args:
            file_path: The path to the CSV file.
            name_field: The name of the field to use as the agent name.
            codebook: Optional dictionary mapping trait names to descriptions.
            instructions: Optional instructions to apply to all created agents.

        Returns:
            An AgentList object created from the CSV file.

        Examples:
            >>> # Basic usage
            >>> agents = AgentListBuilder.from_csv('agents.csv')  # doctest: +SKIP

            >>> # With instructions and name field
            >>> agents = AgentListBuilder.from_csv(  # doctest: +SKIP
            ...     'agents.csv',
            ...     name_field='name',
            ...     instructions='Answer as if you were this person'
            ... )
        """
        warnings.warn(
            "AgentListBuilder.from_csv is deprecated. Use AgentListBuilder.from_source('csv', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        return AgentListBuilder.from_source(
            "csv",
            file_path,
            name_field=name_field,
            codebook=codebook,
            instructions=instructions,
        )

    @staticmethod
    def _load_codebook_from_csv(csv_path: str) -> dict[str, str]:
        """
        Load a codebook from a CSV file and convert keys to pythonic names.

        The CSV should have exactly 2 columns: the first column contains the original keys,
        and the second column contains the descriptions/values.

        Args:
            csv_path: Path to the CSV file containing the codebook

        Returns:
            A dictionary mapping pythonic keys to descriptions

        Examples:
            >>> # CSV content:
            >>> # "Original Key", "Description"
            >>> # "Age in years", "The person's age in years"
            >>> # "Job title", "Current job position"
            >>> #
            >>> # Result:
            >>> # {'age_in_years': 'The person\'s age in years', 'job_title': 'Current job position'}
        """
        import csv
        import os
        from ..utilities.naming_utilities import sanitize_string
        from ..utilities.is_valid_variable_name import is_valid_variable_name

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Codebook CSV file not found: {csv_path}")

        codebook = {}

        with open(csv_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file)

            # Skip header row if it exists
            first_row = next(reader)
            if len(first_row) != 2:
                raise ValueError(
                    f"CSV must have exactly 2 columns, found {len(first_row)}"
                )

            # Check if first row is a header (contains non-descriptive text)
            if any(
                header.lower() in ["key", "field", "column", "name", "trait"]
                for header in first_row
            ):
                # This is a header row, skip it
                pass
            else:
                # First row is data, process it
                original_key, description = first_row
                pythonic_key = sanitize_string(original_key)
                if not is_valid_variable_name(pythonic_key):
                    pythonic_key = f"field_{len(codebook)}"
                codebook[pythonic_key] = description

            # Process remaining rows
            for row in reader:
                if len(row) != 2:
                    continue  # Skip malformed rows

                original_key, description = row
                if not original_key.strip():  # Skip empty keys
                    continue

                pythonic_key = sanitize_string(original_key)
                if not is_valid_variable_name(pythonic_key):
                    pythonic_key = f"field_{len(codebook)}"

                codebook[pythonic_key] = description

        return codebook
