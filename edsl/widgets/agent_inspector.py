"""
Agent Inspector Widget

An interactive widget for inspecting EDSL Agent objects, providing detailed views
of traits, instructions, codebook, and advanced features like dynamic traits and
direct answering methods.
"""

from typing import Any, Dict
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

    # Define which EDSL class this inspector handles
    associated_class = "Agent"

    
    def _enhance_summary(self, summary: Dict[str, Any]):
        """Add agent-specific summary information."""
        summary.update({
            'name': self.data.get('name', 'Unnamed'),
            'trait_count': len(self.data.get('traits', {})),
            'codebook_entries': len(self.data.get('codebook', {})),
            'has_categories': bool(self.data.get('trait_categories')),
            'has_dynamic_traits': self.data.get('has_dynamic_traits_function', False),
            'has_direct_answer': bool(self.data.get('answer_question_directly_function_name')),
            'instruction_length': len(self.data.get('instruction', ''))
        })