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
        source_type: str,
        *args,
        instructions: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        name_field: Optional[str] = None,
        **kwargs
    ) -> "AgentList":
        """
        Create an AgentList from a specified source type.
        
        This method serves as the main entry point for creating AgentList objects,
        providing a unified interface for various data sources while adding support
        for agent-specific parameters like instructions.
        
        Args:
            source_type: The type of source to create an AgentList from.
                        Valid values include: 'csv', 'tsv', 'excel', 'pandas', etc.
            *args: Positional arguments to pass to the source-specific method.
            instructions: Optional instructions to apply to all created agents.
            codebook: Optional dictionary mapping trait names to descriptions.
            name_field: The name of the field to use as the agent name (for CSV/Excel sources).
            **kwargs: Additional keyword arguments to pass to the source-specific method.
            
        Returns:
            An AgentList object created from the specified source.
            
        """
        from ..scenarios import ScenarioList
        from .agent_list import AgentList
        
        # Create ScenarioList from the source
        scenario_list = ScenarioList.from_source(source_type, *args, **kwargs)
        
        # Convert to AgentList
        agent_list = AgentList.from_scenario_list(scenario_list)
        
        # Apply name field if specified (for CSV-like sources)
        if name_field and hasattr(agent_list, 'data') and len(agent_list.data) > 0:
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
            
        """
        warnings.warn(
            "AgentListBuilder.from_csv is deprecated. Use AgentListBuilder.from_source('csv', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        return AgentListBuilder.from_source(
            'csv',
            file_path,
            name_field=name_field,
            codebook=codebook,
            instructions=instructions
        )