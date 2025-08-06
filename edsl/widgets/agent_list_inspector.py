"""
Agent List Inspector Widget

An interactive widget for inspecting multiple EDSL Agent objects in a scrollable
list format. Users can browse agent cards and click to view detailed information
for individual agents.
"""

import traitlets
from typing import Any, Dict, List, Optional
from .base_widget import EDSLBaseWidget


class AgentListInspectorWidget(EDSLBaseWidget):
    """Interactive widget for inspecting multiple EDSL Agent objects.
    
    This widget provides a tile-based interface for exploring multiple agents:
    
    - List View: Compact agent cards showing key information
    - Search & Filter: Find agents by name, traits, or instructions
    - Sort Options: Order by name, trait count, or original order
    - Detailed Inspection: Click any agent card to view full details
    - Responsive Design: Adapts to different screen sizes
    
    Example:
        >>> from edsl.agents import Agent
        >>> from edsl.widgets import AgentListInspectorWidget
        >>> 
        >>> agents = [
        ...     Agent(name="Researcher", traits={"field": "AI", "experience": 5}),
        ...     Agent(name="Teacher", traits={"subject": "Math", "years": 10}),
        ...     Agent(name="Analyst", traits={"domain": "Finance", "level": "Senior"})
        ... ]
        >>> 
        >>> widget = AgentListInspectorWidget(agents)
        >>> widget  # Display in Jupyter notebook
    """

    # Traitlets for data communication with frontend
    agents = traitlets.Any(allow_none=True).tag(sync=False)
    agents_data = traitlets.List().tag(sync=True)
    
    def __init__(self, agents=None, **kwargs):
        """Initialize the Agent List Inspector Widget.
        
        Args:
            agents: A list of EDSL Agent instances to inspect. Can be set later 
                   via the `.agents` property or by calling `inspect(agents)`.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(**kwargs)
        if agents is not None:
            self.agents = agents
    
    @traitlets.observe('agents')
    def _on_agents_change(self, change):
        """Update widget data when agents list changes."""
        if change['new'] is not None:
            self._update_agents_data()
        else:
            self.agents_data = []
    
    def inspect(self, agents) -> 'AgentListInspectorWidget':
        """Set the agents list to inspect and return self for method chaining.
        
        Args:
            agents: A list of EDSL Agent instances to inspect
            
        Returns:
            Self, for method chaining
            
        Example:
            >>> widget = AgentListInspectorWidget()
            >>> widget.inspect(my_agents)  # Returns widget for display
        """
        self.agents = agents
        return self
    
    def _extract_agent_data(self, agent):
        """Extract data from a single agent."""
        try:
            # Get basic agent information
            agent_data = {
                'name': getattr(agent, 'name', None),
                'traits': dict(agent.traits) if hasattr(agent, 'traits') else {},
                'codebook': dict(getattr(agent, 'codebook', {})),
                'instruction': getattr(agent, 'instruction', ''),
                'traits_presentation_template': getattr(agent, 'traits_presentation_template', None),
                'trait_categories': getattr(agent, 'trait_categories', None),
                'has_dynamic_traits_function': getattr(agent, 'has_dynamic_traits_function', False),
                'dynamic_traits_function_name': getattr(agent, 'dynamic_traits_function_name', None),
                'answer_question_directly_function_name': getattr(agent, 'answer_question_directly_function_name', None)
            }
            
            # Add system information if available
            if hasattr(agent, 'to_dict'):
                try:
                    dict_data = agent.to_dict(add_edsl_version=True)
                    agent_data['edsl_version'] = dict_data.get('edsl_version')
                    agent_data['edsl_class_name'] = dict_data.get('edsl_class_name')
                except Exception:
                    # If to_dict fails, continue without version info
                    pass
            
            return agent_data
            
        except Exception as e:
            print(f"Error extracting data from agent: {e}")
            return {
                'error': f"Failed to extract agent data: {str(e)}",
                'traits': {},
                'codebook': {},
                'instruction': '',
                'has_dynamic_traits_function': False
            }
    
    def _update_agents_data(self):
        """Extract and format data from all agents for the frontend."""
        if self.agents is None:
            self.agents_data = []
            return
        
        try:
            # Handle AgentList objects (which have a .data attribute)
            if hasattr(self.agents, 'data') and hasattr(self.agents, '__len__'):
                # This is likely an AgentList
                agents_list = self.agents.data
            elif isinstance(self.agents, (list, tuple)):
                # This is a regular list/tuple
                agents_list = self.agents
            elif hasattr(self.agents, '__iter__') and not isinstance(self.agents, str):
                # This is some other iterable
                agents_list = list(self.agents)
            else:
                # Single agent
                agents_list = [self.agents]
            
            agents_data = []
            for agent in agents_list:
                if agent is not None:
                    agent_data = self._extract_agent_data(agent)
                    agents_data.append(agent_data)
            
            self.agents_data = agents_data
            
        except Exception as e:
            print(f"Error updating agents data: {e}")
            import traceback
            traceback.print_exc()
            self.agents_data = []
    
    def refresh(self):
        """Refresh the widget display by re-extracting agents data.
        
        Useful if any agents have been modified after the widget was created.
        """
        if self.agents is not None:
            self._update_agents_data()
    
    def export_summary(self) -> Dict[str, Any]:
        """Export a summary of all agents' characteristics.
        
        Returns:
            Dictionary containing agents summary information
        """
        if not self.agents_data:
            return {'agent_count': 0}
        
        total_traits = sum(len(agent.get('traits', {})) for agent in self.agents_data)
        total_codebook_entries = sum(len(agent.get('codebook', {})) for agent in self.agents_data)
        named_agents = sum(1 for agent in self.agents_data if agent.get('name'))
        agents_with_categories = sum(1 for agent in self.agents_data if agent.get('trait_categories'))
        dynamic_agents = sum(1 for agent in self.agents_data if agent.get('has_dynamic_traits_function'))
        direct_answer_agents = sum(1 for agent in self.agents_data if agent.get('answer_question_directly_function_name'))
        
        return {
            'agent_count': len(self.agents_data),
            'named_agents': named_agents,
            'total_traits': total_traits,
            'avg_traits_per_agent': total_traits / len(self.agents_data) if self.agents_data else 0,
            'total_codebook_entries': total_codebook_entries,
            'agents_with_categories': agents_with_categories,
            'dynamic_agents': dynamic_agents,
            'direct_answer_agents': direct_answer_agents
        }
    
    def search_agents(self, search_term: str) -> List[Dict[str, Any]]:
        """Search agents by term and return matching entries.
        
        Args:
            search_term: Term to search for in agent names, traits, values, or instructions
            
        Returns:
            List of matching agent data dictionaries
        """
        if not self.agents_data or not search_term:
            return list(self.agents_data) if self.agents_data else []
        
        search_lower = search_term.lower()
        matches = []
        
        for i, agent_data in enumerate(self.agents_data):
            # Check name match
            name_match = search_lower in (agent_data.get('name') or '').lower()
            
            # Check instruction match
            instruction_match = search_lower in (agent_data.get('instruction') or '').lower()
            
            # Check traits match
            traits = agent_data.get('traits', {})
            traits_match = any(
                search_lower in key.lower() or search_lower in str(value).lower()
                for key, value in traits.items()
            )
            
            # Check codebook match
            codebook = agent_data.get('codebook', {})
            codebook_match = any(
                search_lower in desc.lower()
                for desc in codebook.values()
            )
            
            if name_match or instruction_match or traits_match or codebook_match:
                match_data = agent_data.copy()
                match_data['original_index'] = i
                match_data['match_reasons'] = {
                    'name': name_match,
                    'instruction': instruction_match,
                    'traits': traits_match,
                    'codebook': codebook_match
                }
                matches.append(match_data)
        
        return matches
    
    def get_agent_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get agent data by index.
        
        Args:
            index: Zero-based index of the agent
            
        Returns:
            Agent data dictionary or None if index is invalid
        """
        if 0 <= index < len(self.agents_data):
            return self.agents_data[index]
        return None
    
    def filter_by_trait_count(self, min_traits: int = 0, max_traits: Optional[int] = None) -> List[Dict[str, Any]]:
        """Filter agents by number of traits.
        
        Args:
            min_traits: Minimum number of traits (inclusive)
            max_traits: Maximum number of traits (inclusive), None for no limit
            
        Returns:
            List of agent data dictionaries matching the criteria
        """
        if not self.agents_data:
            return []
        
        filtered = []
        for agent_data in self.agents_data:
            trait_count = len(agent_data.get('traits', {}))
            if trait_count >= min_traits:
                if max_traits is None or trait_count <= max_traits:
                    filtered.append(agent_data)
        
        return filtered