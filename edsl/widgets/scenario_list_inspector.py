"""
Scenario List Inspector Widget

An interactive widget for inspecting multiple EDSL Scenario objects in a scrollable
list format. Users can browse scenario cards and click to view detailed information
for individual scenarios.
"""

from typing import Any, Dict, List, Optional
from .inspector_widget import InspectorWidget


class ScenarioListInspectorWidget(InspectorWidget):
    """Interactive widget for inspecting multiple EDSL Scenario objects.
    
    This widget provides a tile-based interface for exploring multiple scenarios:
    
    - List View: Compact scenario cards showing key information
    - Search & Filter: Find scenarios by variables, values, or names
    - Sort Options: Order by name, variable count, or original order
    - Detailed Inspection: Click any scenario card to view full details
    - Responsive Design: Adapts to different screen sizes
    
    Example:
        >>> from edsl.scenarios import Scenario, ScenarioList
        >>> from edsl.widgets import ScenarioListInspectorWidget
        >>> 
        >>> scenarios = ScenarioList([
        ...     Scenario({"product": "laptop", "price": 999}, name="Tech Product"),
        ...     Scenario({"product": "coffee", "price": 4.99}, name="Food Product"),
        ...     Scenario({"product": "book", "price": 19.99}, name="Media Product")
        ... ])
        >>> 
        >>> widget = ScenarioListInspectorWidget(scenarios)
        >>> widget  # Display in Jupyter notebook
    """

    # Define which EDSL class this inspector handles
    associated_class = "ScenarioList"
    
    def __init__(self, obj=None, **kwargs):
        """Initialize the Scenario List Inspector Widget.
        
        Args:
            obj: An EDSL ScenarioList or list of Scenario instances to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(obj, **kwargs)
    
    def _process_object_data(self):
        """No additional processing needed - ScenarioList.to_dict() has everything we need."""
        pass
    
    def _validate_object(self, obj) -> bool:
        """Validate that the object is a ScenarioList or list of scenarios."""
        if obj is None:
            return True
        return (hasattr(obj, 'scenarios') and hasattr(obj, '__len__') and hasattr(obj, '__iter__')) or type(obj).__name__ == 'ScenarioList'

    def _safe_to_dict(self, obj):
        """Override to handle ScenarioList's specific to_dict signature."""
        try:
            # ScenarioList doesn't support full_dict parameter
            return obj.to_dict(add_edsl_version=True)
        except Exception as e:
            return {
                'error': f"Failed to convert object to dictionary: {str(e)}",
                'type': type(obj).__name__,
                'str_representation': str(obj)
            }

    @property
    def scenarios_data(self):
        """Get the scenarios data for frontend compatibility."""
        return self.data.get('scenarios', [])

    def _enhance_summary(self, summary: Dict[str, Any]):
        """Add scenario list specific summary information."""
        scenarios_data = self.scenarios_data
        
        if not scenarios_data:
            summary.update({
                'scenario_count': 0,
                'total_variables': 0,
                'common_variables': [],
                'has_codebook': False
            })
            return
        
        # Analyze all scenarios to find common patterns
        all_variables = set()
        variable_counts = {}
        
        for scenario in scenarios_data:
            scenario_data = scenario.get('data', {}) if 'data' in scenario else scenario
            if isinstance(scenario_data, dict):
                for var in scenario_data.keys():
                    all_variables.add(var)
                    variable_counts[var] = variable_counts.get(var, 0) + 1
        
        # Find variables that appear in all scenarios
        scenario_count = len(scenarios_data)
        common_variables = [var for var, count in variable_counts.items() if count == scenario_count]
        
        summary.update({
            'scenario_count': scenario_count,
            'total_variables': len(all_variables),
            'common_variables': common_variables,
            'has_codebook': bool(self.data.get('codebook'))
        })


# Convenience function for easy import
def create_scenario_list_inspector_widget(scenario_list=None):
    """Create and return a new Scenario List Inspector Widget instance."""
    return ScenarioListInspectorWidget(obj=scenario_list)


# Export the main class
__all__ = ["ScenarioListInspectorWidget", "create_scenario_list_inspector_widget"]