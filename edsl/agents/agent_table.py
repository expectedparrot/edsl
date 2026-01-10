"""Agent table functionality.

This module provides the AgentTable class that handles table generation and
data presentation for Agent instances, including trait tables and generic
attribute tables.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent
    from ..dataset import Dataset


class AgentTable:
    """Handles table generation and data presentation for Agent instances.

    This class provides methods to create tabular representations of agent
    data, including trait tables and generic attribute tables.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the AgentTable manager.

        Args:
            agent: The agent instance this manager belongs to
        """
        self.agent = agent

    def table(self) -> "Dataset":
        """Create a tabular representation of the agent's traits.

        This method creates a Dataset containing the agent's traits with their
        descriptions (from codebook if available) and values. This is useful
        for displaying agent characteristics in a structured format.

        Returns:
            A Dataset containing trait information with columns:
            - Trait: The trait name
            - Description: Human-readable description (from codebook or trait name)
            - Value: The trait value

        Examples:
            Create table with traits and codebook:

            >>> from edsl.agents import Agent
            >>> codebook = {'age': 'Age in years', 'occupation': 'Current job'}
            >>> agent = Agent(traits={'age': 30, 'occupation': 'doctor'}, codebook=codebook)
            >>> dataset = agent.table_manager.table()
            >>> len(dataset) == 2
            True
            >>> 'Trait' in dataset[0]
            True

            Create table with traits but no codebook:

            >>> agent2 = Agent(traits={'height': 5.5, 'weight': 150})
            >>> dataset2 = agent2.table_manager.table()
            >>> len(dataset2) == 2
            True
            >>> 'height' in dataset2[0]['Trait']
            True
        """
        from ..scenarios import ScenarioList

        table_data = ScenarioList([])
        for trait_name, value in self.agent.traits.items():
            if trait_name in self.agent.codebook:
                trait_description = self.agent.codebook[trait_name]
            else:
                trait_description = trait_name
            table_data = table_data.append(
                {"Trait": trait_name, "Description": trait_description, "Value": value}
            )

        # Handle empty traits case
        if not table_data:
            # Add empty row to avoid Dataset creation issues
            table_data = table_data.append({"Trait": "", "Description": "", "Value": ""})

        return table_data.to_dataset()

    def generic_table(self) -> tuple[list[dict], list[str]]:
        """Prepare generic table data for all agent attributes.

        This method creates a table representation of all agent attributes,
        which is useful for debugging and introspection. It includes all
        attributes in the agent's __dict__.

        Returns:
            A tuple of (table_data, column_names) where:
            - table_data: List of dictionaries with 'Attribute' and 'Value' keys
            - column_names: List of column names ['Attribute', 'Value']

        Examples:
            Create generic attribute table:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30}, name='TestAgent')
            >>> data, columns = agent.table_manager.generic_table()
            >>> 'Attribute' in columns
            True
            >>> 'Value' in columns
            True
            >>> len(data) > 0
            True
            >>> any(row['Attribute'] == '_name' for row in data)
            True
        """
        table_data = []
        for attr_name, attr_value in self.agent.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    def traits_summary(self) -> dict:
        """Create a summary of the agent's traits.

        This method provides a structured summary of the agent's traits,
        including counts and basic statistics.

        Returns:
            Dictionary with trait summary information

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': 5.5, 'occupation': 'doctor'})
            >>> summary = agent.table_manager.traits_summary()
            >>> summary['total_traits'] == 3
            True
            >>> 'trait_types' in summary
            True
        """
        traits = self.agent.traits
        trait_types = {}

        for trait_name, trait_value in traits.items():
            value_type = type(trait_value).__name__
            trait_types[value_type] = trait_types.get(value_type, 0) + 1

        return {
            "total_traits": len(traits),
            "trait_types": trait_types,
            "has_codebook": len(self.agent.codebook) > 0,
            "codebook_coverage": (
                len([t for t in traits.keys() if t in self.agent.codebook])
                / len(traits)
                if traits
                else 0
            ),
            "trait_names": list(traits.keys()),
        }
