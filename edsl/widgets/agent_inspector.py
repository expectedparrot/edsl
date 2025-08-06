"""
Agent Inspector Widget

An interactive widget for inspecting EDSL Agent objects, providing detailed views
of traits, instructions, codebook, and advanced features like dynamic traits and
direct answering methods.
"""

import traitlets
from typing import Any, Dict, Optional
from .inspector_widget import InspectorWidget


class AgentInspectorWidget(InspectorWidget):
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

    # Agent-specific traitlet (inherits object_data from base class)
    agent = traitlets.Any(allow_none=True).tag(sync=False)
    
    # For backward compatibility - maps to base class object_data
    @property
    def agent_data(self):
        return self.object_data
    
    @agent_data.setter
    def agent_data(self, value):
        self.object_data = value
    
    def __init__(self, agent=None, **kwargs):
        """Initialize the Agent Inspector Widget.
        
        Args:
            agent: An EDSL Agent instance to inspect. Can be set later via the 
                  `.agent` property or by calling `inspect(agent)`.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(inspected_object=agent, **kwargs)
        # Set up agent-specific observer
        if agent is not None:
            self.agent = agent
    
    @traitlets.observe('agent')
    def _on_agent_change(self, change):
        """Update widget data when agent changes - sync with base class."""
        self.inspected_object = change['new']
    
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
    
    def _update_object_data(self):
        """Extract and format agent data using to_dict(full_dict=True)."""
        if self.inspected_object is None:
            self.object_data = {}
            return
        
        # Use the base class safe conversion method
        self.object_data = self._safe_to_dict(self.inspected_object)
        
        # Sync the agent property for backward compatibility
        if hasattr(self, '_agent_property_sync'):
            return
        self._agent_property_sync = True
        self.agent = self.inspected_object
        self._agent_property_sync = False
    
    def _validate_object(self, obj) -> bool:
        """Validate that the object is an EDSL Agent.
        
        Args:
            obj: Object to validate
            
        Returns:
            bool: True if object is a valid Agent
        """
        if obj is None:
            return True
        
        # Check if it's an Agent by looking for key Agent attributes
        return (hasattr(obj, 'traits') and 
                (hasattr(obj, 'instruction') or hasattr(obj, 'codebook')))
    
    def export_summary(self) -> Dict[str, Any]:
        """Export a summary of the agent's key characteristics.
        
        Returns:
            Dictionary containing agent summary information
        """
        if not self.agent_data:
            return {}
        
        summary = super().export_summary()
        
        # Add agent-specific summary information
        summary.update({
            'name': self.object_data.get('name', 'Unnamed'),
            'trait_count': len(self.object_data.get('traits', {})),
            'codebook_entries': len(self.object_data.get('codebook', {})),
            'has_categories': bool(self.object_data.get('trait_categories')),
            'has_dynamic_traits': self.object_data.get('has_dynamic_traits_function', False),
            'has_direct_answer': bool(self.object_data.get('answer_question_directly_function_name')),
            'instruction_length': len(self.object_data.get('instruction', ''))
        })
        
        return summary
    
