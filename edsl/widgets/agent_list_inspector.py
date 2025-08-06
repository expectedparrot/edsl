"""
Agent List Inspector Widget

An interactive widget for inspecting multiple EDSL Agent objects in a scrollable
list format. Users can browse agent cards and click to view detailed information
for individual agents.
"""

from typing import Any, Dict, List, Optional
from .inspector_widget import InspectorWidget


class AgentListInspectorWidget(InspectorWidget):
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

    widget_short_name = "agent_list_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "AgentList"

    def __init__(self, obj=None, **kwargs):
        """Initialize the Agent List Inspector Widget.

        Args:
            obj: An EDSL AgentList or list of Agent instances to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(obj, **kwargs)

    def _process_object_data(self):
        """No additional processing needed - AgentList.to_dict(full_dict=True) has everything we need."""
        pass

    def _validate_object(self, obj) -> bool:
        """Validate that the object is an AgentList or list of agents.

        Args:
            obj: Object to validate

        Returns:
            bool: True if object is valid for this inspector
        """
        if obj is None:
            return True

        # Check if it's an AgentList
        if hasattr(obj, "data") and hasattr(obj, "__len__"):
            return True

        # Check if it's a list/tuple of agents
        if isinstance(obj, (list, tuple)):
            return True

        # Check if it's some other iterable
        if hasattr(obj, "__iter__") and not isinstance(obj, str):
            return True

        # Single agent is also acceptable
        return hasattr(obj, "traits") or type(obj).__name__ == "Agent"

    def _enhance_summary(self, summary: Dict[str, Any]):
        """Add agent list specific summary information."""
        agents_data = self.data.get("agent_list", [])
        if not agents_data:
            summary.update(
                {
                    "agent_count": 0,
                    "named_agents": 0,
                    "total_traits": 0,
                    "avg_traits_per_agent": 0,
                }
            )
            return

        total_traits = sum(len(agent.get("traits", {})) for agent in agents_data)
        named_agents = sum(1 for agent in agents_data if agent.get("name"))

        summary.update(
            {
                "agent_count": len(agents_data),
                "named_agents": named_agents,
                "total_traits": total_traits,
                "avg_traits_per_agent": (
                    total_traits / len(agents_data) if agents_data else 0
                ),
            }
        )

    @property
    def agents_data(self):
        """Get the agents data for frontend compatibility."""
        return self.data.get("agent_list", [])

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
            name_match = search_lower in (agent_data.get("name") or "").lower()

            # Check instruction match
            instruction_match = (
                search_lower in (agent_data.get("instruction") or "").lower()
            )

            # Check traits match
            traits = agent_data.get("traits", {})
            traits_match = any(
                search_lower in key.lower() or search_lower in str(value).lower()
                for key, value in traits.items()
            )

            # Check codebook match
            codebook = agent_data.get("codebook", {})
            codebook_match = any(
                search_lower in desc.lower() for desc in codebook.values()
            )

            if name_match or instruction_match or traits_match or codebook_match:
                match_data = agent_data.copy()
                match_data["original_index"] = i
                match_data["match_reasons"] = {
                    "name": name_match,
                    "instruction": instruction_match,
                    "traits": traits_match,
                    "codebook": codebook_match,
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

    def filter_by_trait_count(
        self, min_traits: int = 0, max_traits: Optional[int] = None
    ) -> List[Dict[str, Any]]:
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
            trait_count = len(agent_data.get("traits", {}))
            if trait_count >= min_traits:
                if max_traits is None or trait_count <= max_traits:
                    filtered.append(agent_data)

        return filtered
