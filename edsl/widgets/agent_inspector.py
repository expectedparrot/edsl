"""
Agent Inspector Widget

An interactive widget for inspecting EDSL Agent objects, providing detailed views
of traits, instructions, codebook, and advanced features like dynamic traits and
direct answering methods.
"""

import traitlets
from typing import Any, Dict, Optional
from .base_widget import EDSLBaseWidget


class AgentInspectorWidget(EDSLBaseWidget):
    """Interactive widget for comprehensively inspecting EDSL Agent objects.
    
    This widget provides a multi-tabbed interface for exploring all aspects of
    an Agent instance, including:
    
    - Overview: Basic information, statistics, and system details
    - Traits: Interactive table of agent characteristics with search and filtering
    - Instructions: Agent's answering instructions
    - Codebook: Human-readable trait descriptions
    - Advanced: Dynamic traits functions, direct answer methods, and trait categories
    
    Example:
        >>> from edsl.agents import Agent
        >>> from edsl.widgets import AgentInspectorWidget
        >>> 
        >>> agent = Agent(
        ...     name="Research Assistant",
        ...     traits={
        ...         "age": 30,
        ...         "field": "computer_science",
        ...         "experience": "5_years"
        ...     },
        ...     codebook={
        ...         "age": "Age in years",
        ...         "field": "Academic field of expertise", 
        ...         "experience": "Years of research experience"
        ...     },
        ...     instruction="Answer questions from an expert researcher perspective"
        ... )
        >>> 
        >>> widget = AgentInspectorWidget(agent)
        >>> widget  # Display in Jupyter notebook
    """

    # Traitlets for data communication with frontend
    agent = traitlets.Any(allow_none=True).tag(sync=False)
    agent_data = traitlets.Dict().tag(sync=True)
    
    def __init__(self, agent=None, **kwargs):
        """Initialize the Agent Inspector Widget.
        
        Args:
            agent: An EDSL Agent instance to inspect. Can be set later via the 
                  `.agent` property or by calling `inspect(agent)`.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(**kwargs)
        if agent is not None:
            self.agent = agent
    
    @traitlets.observe('agent')
    def _on_agent_change(self, change):
        """Update widget data when agent changes."""
        if change['new'] is not None:
            self._update_agent_data()
        else:
            self.agent_data = {}
    
    def inspect(self, agent) -> 'AgentInspectorWidget':
        """Set the agent to inspect and return self for method chaining.
        
        Args:
            agent: An EDSL Agent instance to inspect
            
        Returns:
            Self, for method chaining
            
        Example:
            >>> widget = AgentInspectorWidget()
            >>> widget.inspect(my_agent)  # Returns widget for display
        """
        self.agent = agent
        return self
    
    def _update_agent_data(self):
        """Extract and format agent data for the frontend."""
        if self.agent is None:
            self.agent_data = {}
            return
        
        try:
            # Get basic agent information
            agent_data = {
                'name': getattr(self.agent, 'name', None),
                'traits': dict(self.agent.traits) if hasattr(self.agent, 'traits') else {},
                'codebook': dict(getattr(self.agent, 'codebook', {})),
                'instruction': getattr(self.agent, 'instruction', ''),
                'traits_presentation_template': getattr(self.agent, 'traits_presentation_template', None),
                'trait_categories': getattr(self.agent, 'trait_categories', None),
                'has_dynamic_traits_function': getattr(self.agent, 'has_dynamic_traits_function', False),
                'dynamic_traits_function_name': getattr(self.agent, 'dynamic_traits_function_name', None),
                'answer_question_directly_function_name': getattr(self.agent, 'answer_question_directly_function_name', None)
            }
            
            # Add system information if available
            if hasattr(self.agent, 'to_dict'):
                try:
                    dict_data = self.agent.to_dict(add_edsl_version=True)
                    agent_data['edsl_version'] = dict_data.get('edsl_version')
                    agent_data['edsl_class_name'] = dict_data.get('edsl_class_name')
                except Exception:
                    # If to_dict fails, continue without version info
                    pass
            
            self.agent_data = agent_data
            
        except Exception as e:
            print(f"Error updating agent data: {e}")
            self.agent_data = {
                'error': f"Failed to extract agent data: {str(e)}",
                'traits': {},
                'codebook': {},
                'instruction': '',
                'has_dynamic_traits_function': False
            }
    
    def refresh(self):
        """Refresh the widget display by re-extracting agent data.
        
        Useful if the agent has been modified after the widget was created.
        """
        if self.agent is not None:
            self._update_agent_data()
    
    def export_summary(self) -> Dict[str, Any]:
        """Export a summary of the agent's key characteristics.
        
        Returns:
            Dictionary containing agent summary information
        """
        if not self.agent_data:
            return {}
        
        return {
            'name': self.agent_data.get('name', 'Unnamed'),
            'trait_count': len(self.agent_data.get('traits', {})),
            'codebook_entries': len(self.agent_data.get('codebook', {})),
            'has_categories': bool(self.agent_data.get('trait_categories')),
            'has_dynamic_traits': self.agent_data.get('has_dynamic_traits_function', False),
            'has_direct_answer': bool(self.agent_data.get('answer_question_directly_function_name')),
            'instruction_length': len(self.agent_data.get('instruction', ''))
        }
    
    def search_traits(self, search_term: str) -> Dict[str, Any]:
        """Search agent traits by term and return matching entries.
        
        Args:
            search_term: Term to search for in trait keys, values, or descriptions
            
        Returns:
            Dictionary of matching traits with their values and descriptions
        """
        if not self.agent_data or not search_term:
            return {}
        
        traits = self.agent_data.get('traits', {})
        codebook = self.agent_data.get('codebook', {})
        search_lower = search_term.lower()
        
        matches = {}
        for key, value in traits.items():
            # Check if search term appears in key, value, or codebook description
            key_match = search_lower in key.lower()
            value_match = search_lower in str(value).lower()
            desc_match = search_lower in codebook.get(key, '').lower()
            
            if key_match or value_match or desc_match:
                matches[key] = {
                    'value': value,
                    'description': codebook.get(key, 'No description'),
                    'match_reasons': {
                        'key': key_match,
                        'value': value_match,
                        'description': desc_match
                    }
                }
        
        return matches