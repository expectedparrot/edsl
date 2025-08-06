"""
Scenario Inspector Widget

An interactive widget for inspecting EDSL Scenario objects, providing detailed views
of key-value pairs, metadata, and scenario-specific operations.
"""

from typing import Any, Dict
from .inspector_widget import InspectorWidget


class ScenarioInspectorWidget(InspectorWidget):
    """Interactive widget for comprehensively inspecting EDSL Scenario objects.

    This widget provides a multi-tabbed interface for exploring all aspects of
    a Scenario instance, including:

    - Overview: Basic information, statistics, and key-value pairs
    - Data: Interactive table of scenario variables with search and filtering
    - Metadata: Scenario name, source information, and EDSL version details
    - Operations: Available scenario methods and transformations

    Example:
        >>> from edsl.scenarios import Scenario
        >>> from edsl.widgets import ScenarioInspectorWidget
        >>>
        >>> scenario = Scenario({
        ...     "product": "smartphone",
        ...     "price": 699,
        ...     "brand": "TechCorp",
        ...     "features": ["5G", "wireless_charging", "face_unlock"]
        ... }, name="Product Survey Scenario")
        >>>
        >>> widget = ScenarioInspectorWidget(scenario)
        >>> widget  # Display in Jupyter notebook
    """

    widget_short_name = "scenario_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "Scenario"

    def _validate_object(self, obj) -> bool:
        """Validate that the object is a Scenario instance."""
        if obj is None:
            return True
        return (
            hasattr(obj, "data")
            and hasattr(obj, "name")
            or type(obj).__name__ == "Scenario"
        )

    def _safe_to_dict(self, obj):
        """Override to handle Scenario's specific to_dict signature."""
        try:
            # Scenario doesn't support full_dict parameter
            return obj.to_dict(add_edsl_version=True)
        except Exception as e:
            return {
                "error": f"Failed to convert object to dictionary: {str(e)}",
                "type": type(obj).__name__,
                "str_representation": str(obj),
            }

    def _enhance_summary(self, summary: Dict[str, Any]):
        """Add scenario-specific summary information."""
        if not self.data:
            return

        # Count different types of values
        value_counts = {
            "strings": 0,
            "numbers": 0,
            "lists": 0,
            "objects": 0,
            "booleans": 0,
        }

        # For Scenario, the actual data is at the root level, not in a 'data' key
        # We need to exclude EDSL metadata fields
        scenario_data = {
            k: v
            for k, v in self.data.items()
            if k not in ["edsl_version", "edsl_class_name", "name"]
        }

        if isinstance(scenario_data, dict):
            for key, value in scenario_data.items():
                if isinstance(value, str):
                    value_counts["strings"] += 1
                elif isinstance(value, (int, float)):
                    value_counts["numbers"] += 1
                elif isinstance(value, list):
                    value_counts["lists"] += 1
                elif isinstance(value, bool):
                    value_counts["booleans"] += 1
                else:
                    value_counts["objects"] += 1

        summary.update(
            {
                "name": self.data.get("name", "Unnamed"),
                "variable_count": (
                    len(scenario_data) if isinstance(scenario_data, dict) else 0
                ),
                "value_types": value_counts,
                "has_name": bool(self.data.get("name")),
            }
        )


# Convenience function for easy import
def create_scenario_inspector_widget(scenario=None):
    """Create and return a new Scenario Inspector Widget instance."""
    return ScenarioInspectorWidget(obj=scenario)


# Export the main class
__all__ = ["ScenarioInspectorWidget", "create_scenario_inspector_widget"]
