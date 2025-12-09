"""
Agent List Builder Widget

An anywidget for selecting and filtering agents from a passed-in AgentList.
Provides interactive filtering, sampling, and agent selection capabilities.
"""

import traitlets
from .base_widget import EDSLBaseWidget


class AgentListBuilderWidget(EDSLBaseWidget):
    """A widget for building and filtering AgentLists with interactive selection."""

    widget_short_name = "agent_list_builder"

    # Agent list data and state
    agent_list_data = traitlets.Dict({}).tag(sync=True)
    selected_agents = traitlets.List([]).tag(sync=True)
    filtered_agents = traitlets.List([]).tag(sync=True)
    available_traits = traitlets.List([]).tag(sync=True)
    selected_traits = traitlets.List([]).tag(sync=True)

    # Filter and sampling state
    trait_filters = traitlets.Dict({}).tag(sync=True)
    sample_percentage = traitlets.Int(100).tag(sync=True)
    custom_sample_count = traitlets.Int(0).tag(sync=True)

    # UI state
    loading = traitlets.Bool(False).tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)
    is_edited = traitlets.Bool(False).tag(sync=True)

    # SQL query functionality
    sql_query = traitlets.Unicode("SELECT * FROM agents").tag(sync=True)
    sql_error = traitlets.Unicode("").tag(sync=True)

    # Statistics
    stats = traitlets.Dict(
        {
            "total_agents": 0,
            "filtered_count": 0,
            "selected_count": 0,
            "filtered_percentage": 100,
            "total_trait_count": 0,
            "selected_trait_count": 0,
            "active_filter_count": 0,
        }
    ).tag(sync=True)

    # Action requests from frontend
    filter_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    sample_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    selection_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    sql_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    trait_toggle_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    update_request = traitlets.Dict({"is_default": True}).tag(sync=True)

    # Update status
    update_status = traitlets.Unicode("").tag(sync=True)
    update_success = traitlets.Bool(False).tag(sync=True)

    def __init__(self, agent_list=None, **kwargs):
        super().__init__(**kwargs)

        # Store reference to original agent list for updates
        self._original_agent_list = agent_list

        # Set up observers for frontend requests
        self.observe(self._on_filter_request, names=["filter_request"])
        self.observe(self._on_sample_request, names=["sample_request"])
        self.observe(self._on_selection_request, names=["selection_request"])
        self.observe(self._on_sql_request, names=["sql_request"])
        self.observe(self._on_trait_toggle_request, names=["trait_toggle_request"])
        self.observe(self._on_update_request, names=["update_request"])

        # Initialize with agent list if provided
        if agent_list is not None:
            self.set_agent_list(agent_list)

    def set_agent_list(self, agent_list):
        """Set the agent list and initialize the widget state."""
        try:
            # Convert AgentList to dictionary format for frontend
            if hasattr(agent_list, "__iter__"):
                # Handle AgentList object
                agents_data = []
                all_traits = set()

                for i, agent in enumerate(agent_list):
                    # Get agent name or create one
                    agent_name = (
                        agent.name
                        if hasattr(agent, "name") and agent.name
                        else f"Agent_{i+1}"
                    )

                    # Extract agent data - convert traits to regular dict
                    agent_traits = {}
                    if hasattr(agent, "traits"):
                        # Convert EDSL traits object to regular dict
                        try:
                            agent_traits = dict(agent.traits)
                        except:
                            # Fallback if dict() doesn't work
                            agent_traits = {
                                k: agent.traits[k] for k in agent.traits.keys()
                            }

                    agent_data = {
                        "name": agent_name,
                        "traits": agent_traits,
                        "instruction": getattr(agent, "instruction", None),
                        "traits_presentation_template": getattr(
                            agent, "traits_presentation_template", None
                        ),
                    }
                    agents_data.append(agent_data)

                    # Collect all trait names
                    if agent_traits:
                        all_traits.update(agent_traits.keys())

                # Set up widget data
                self.agent_list_data = {
                    "agents": agents_data,
                    "agent_count": len(agents_data),
                    "available_traits": sorted(list(all_traits)),
                    "description": getattr(agent_list, "description", ""),
                    "alias": getattr(agent_list, "alias", ""),
                    "visibility": getattr(agent_list, "visibility", "private"),
                    "uuid": getattr(agent_list, "uuid", None),
                }

                # Initialize state
                self.available_traits = sorted(list(all_traits))
                self.selected_traits = self.available_traits.copy()
                self.selected_agents = agents_data.copy()
                self.filtered_agents = agents_data.copy()
                self.is_edited = False

                # Update statistics
                self._update_stats()

            else:
                raise ValueError("Invalid agent list format")

        except Exception as e:
            self.error_message = f"Error loading agent list: {str(e)}"
            self.agent_list_data = {}

    def _on_filter_request(self, change):
        """Handle filter request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        filters = request.get("filters", {})
        self.trait_filters = filters
        self._apply_filters()

    def _on_sample_request(self, change):
        """Handle sampling request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        sample_type = request.get("type")
        if sample_type == "percentage":
            percentage = request.get("percentage", 100)
            self._apply_percentage_sample(percentage)
        elif sample_type == "count":
            count = request.get("count", 0)
            self._apply_count_sample(count)
        elif sample_type == "clear":
            self._clear_selection()

    def _on_selection_request(self, change):
        """Handle agent selection request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        action = request.get("action")
        if action == "toggle":
            agent_name = request.get("agent_name")
            self._toggle_agent_selection(agent_name)
        elif action == "select_all":
            self._select_all_filtered()
        elif action == "select_none":
            self._select_none()

    def _on_sql_request(self, change):
        """Handle SQL query request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        query = request.get("query", "SELECT * FROM agents")
        self._execute_sql_query(query)

    def _on_trait_toggle_request(self, change):
        """Handle trait toggle request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        trait = request.get("trait")
        if trait:
            self._toggle_trait_selection(trait)

    def _on_update_request(self, change):
        """Handle update agent list request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        self._update_original_agent_list()

    def _apply_filters(self):
        """Apply trait filters to the agent list."""
        if not self.agent_list_data.get("agents"):
            return

        filtered = []
        for agent in self.agent_list_data["agents"]:
            matches = True
            agent_traits = agent.get("traits", {})

            for trait, filter_config in self.trait_filters.items():
                if not filter_config.get("enabled", False):
                    continue

                trait_value = agent_traits.get(trait)
                filter_type = filter_config.get("type", "equals")
                filter_value = filter_config.get("value")
                filter_values = filter_config.get("values", [])

                # Determine trait type for proper comparison
                trait_type = self._get_trait_type(trait_value)

                # Convert values for comparison
                if trait_type == "number":
                    try:
                        trait_value = (
                            float(trait_value) if trait_value is not None else None
                        )
                        filter_value = float(filter_value) if filter_value else 0
                        filter_values = [float(v) for v in filter_values if v]
                    except (ValueError, TypeError):
                        trait_value = None
                elif trait_type == "boolean":
                    trait_value = (
                        str(trait_value).lower() in ["true", "1", "yes", "on"]
                        if trait_value is not None
                        else False
                    )
                    filter_value = (
                        str(filter_value).lower() in ["true", "1", "yes", "on"]
                        if filter_value
                        else False
                    )
                else:
                    trait_value = str(trait_value) if trait_value is not None else ""
                    filter_value = str(filter_value) if filter_value else ""
                    filter_values = [str(v) for v in filter_values]

                # Apply filter logic
                if not self._evaluate_filter(
                    trait_value, filter_type, filter_value, filter_values, trait_type
                ):
                    matches = False
                    break

            if matches:
                filtered.append(agent)

        self.filtered_agents = filtered
        self.is_edited = True
        self._update_stats()

    def _get_trait_type(self, value):
        """Determine the type of a trait value."""
        if value is None:
            return "string"

        # Check if it's a number
        try:
            float(value)
            return "number"
        except (ValueError, TypeError):
            pass

        # Check if it's a boolean
        if isinstance(value, bool) or str(value).lower() in [
            "true",
            "false",
            "1",
            "0",
            "yes",
            "no",
            "on",
            "off",
        ]:
            return "boolean"

        return "string"

    def _evaluate_filter(
        self, trait_value, filter_type, filter_value, filter_values, trait_type
    ):
        """Evaluate a single filter condition."""
        if trait_value is None:
            return False

        try:
            if filter_type == "equals":
                return trait_value == filter_value
            elif filter_type == "not_equals":
                return trait_value != filter_value
            elif filter_type == "contains":
                return filter_value.lower() in str(trait_value).lower()
            elif filter_type == "not_contains":
                return filter_value.lower() not in str(trait_value).lower()
            elif filter_type == "starts_with":
                return str(trait_value).lower().startswith(filter_value.lower())
            elif filter_type == "ends_with":
                return str(trait_value).lower().endswith(filter_value.lower())
            elif filter_type == "greater_than":
                return trait_type == "number" and trait_value > filter_value
            elif filter_type == "greater_equal":
                return trait_type == "number" and trait_value >= filter_value
            elif filter_type == "less_than":
                return trait_type == "number" and trait_value < filter_value
            elif filter_type == "less_equal":
                return trait_type == "number" and trait_value <= filter_value
            elif filter_type == "between":
                # This would need additional value2 parameter
                return True  # TODO: Implement between logic
            elif filter_type == "in":
                if trait_type == "string":
                    return any(
                        str(trait_value).lower() == str(v).lower()
                        for v in filter_values
                    )
                else:
                    return trait_value in filter_values
            elif filter_type == "not_in":
                if trait_type == "string":
                    return not any(
                        str(trait_value).lower() == str(v).lower()
                        for v in filter_values
                    )
                else:
                    return trait_value not in filter_values
            else:
                return True  # Unknown filter type, pass through
        except Exception:
            return False  # Error in evaluation, fail the filter

    def _apply_percentage_sample(self, percentage):
        """Apply percentage-based sampling to filtered agents."""
        import random

        if not self.filtered_agents:
            return

        self.sample_percentage = percentage

        if percentage >= 100:
            self.selected_agents = self.filtered_agents.copy()
        else:
            sample_size = max(1, int(len(self.filtered_agents) * percentage / 100))
            self.selected_agents = random.sample(
                self.filtered_agents, min(sample_size, len(self.filtered_agents))
            )

        self.is_edited = True
        self._update_stats()

    def _apply_count_sample(self, count):
        """Apply count-based sampling to filtered agents."""
        import random

        if not self.filtered_agents or count <= 0:
            return

        self.custom_sample_count = count
        sample_size = min(count, len(self.filtered_agents))
        self.selected_agents = random.sample(self.filtered_agents, sample_size)

        # Update percentage for display
        self.sample_percentage = int((sample_size / len(self.filtered_agents)) * 100)
        self.is_edited = True
        self._update_stats()

    def _clear_selection(self):
        """Clear all agent selections."""
        self.selected_agents = []
        self.sample_percentage = 0
        self.is_edited = True
        self._update_stats()

    def _toggle_agent_selection(self, agent_name):
        """Toggle selection of a specific agent."""
        current_selected = [
            agent for agent in self.selected_agents if agent.get("name") == agent_name
        ]

        if current_selected:
            # Remove from selection
            self.selected_agents = [
                agent
                for agent in self.selected_agents
                if agent.get("name") != agent_name
            ]
        else:
            # Add to selection
            agent_to_add = None
            for agent in self.filtered_agents:
                if agent.get("name") == agent_name:
                    agent_to_add = agent
                    break

            if agent_to_add:
                self.selected_agents = self.selected_agents + [agent_to_add]

        self.is_edited = True
        self._update_stats()

    def _select_all_filtered(self):
        """Select all filtered agents."""
        self.selected_agents = self.filtered_agents.copy()
        self.sample_percentage = 100
        self.is_edited = True
        self._update_stats()

    def _select_none(self):
        """Deselect all agents."""
        self.selected_agents = []
        self.sample_percentage = 0
        self.is_edited = True
        self._update_stats()

    def _execute_sql_query(self, query):
        """Execute SQL query against agents (simplified version)."""
        try:
            # This is a simplified implementation
            # In a full implementation, you'd use a proper SQL engine like alasql
            self.sql_query = query
            self.sql_error = ""

            # For now, just filter based on basic SQL patterns
            if "WHERE" in query.upper():
                # Simple WHERE clause parsing could be implemented here
                pass

            # Default to showing all agents
            self.filtered_agents = self.agent_list_data.get("agents", [])
            self._update_stats()

        except Exception as e:
            self.sql_error = str(e)

    def _toggle_trait_selection(self, trait):
        """Toggle trait selection for display."""
        if trait in self.selected_traits:
            self.selected_traits = [t for t in self.selected_traits if t != trait]
        else:
            self.selected_traits = self.selected_traits + [trait]

        self.is_edited = True
        self._update_stats()

    def _update_stats(self):
        """Update statistics for display."""
        total_agents = len(self.agent_list_data.get("agents", []))
        filtered_count = len(self.filtered_agents)
        selected_count = len(self.selected_agents)

        self.stats = {
            "total_agents": total_agents,
            "filtered_count": filtered_count,
            "selected_count": selected_count,
            "filtered_percentage": int((filtered_count / max(1, total_agents)) * 100),
            "total_trait_count": len(self.available_traits),
            "selected_trait_count": len(self.selected_traits),
            "active_filter_count": len(
                [f for f in self.trait_filters.values() if f.get("enabled", False)]
            ),
        }

    def _update_widget_data_after_agent_list_change(self):
        """Update widget's internal data after the original AgentList has been modified.

        This preserves current selections while updating the underlying data structure
        to reflect changes made to the original AgentList (like trait removal).
        """
        if not self._original_agent_list:
            return

        try:
            # Store current selections to preserve them
            current_selected_agent_names = [
                agent.get("name", "") for agent in self.selected_agents
            ]
            current_filtered_agent_names = [
                agent.get("name", "") for agent in self.filtered_agents
            ]

            # Re-process the updated AgentList to get new agent data
            agents_data = []
            all_traits = set()

            for i, agent in enumerate(self._original_agent_list):
                # Get agent name or create one
                agent_name = (
                    agent.name
                    if hasattr(agent, "name") and agent.name
                    else f"Agent_{i+1}"
                )

                # Extract agent data - convert traits to regular dict
                agent_traits = {}
                if hasattr(agent, "traits"):
                    try:
                        agent_traits = dict(agent.traits)
                    except:
                        agent_traits = {k: agent.traits[k] for k in agent.traits.keys()}

                agent_data = {
                    "name": agent_name,
                    "traits": agent_traits,
                    "instruction": getattr(agent, "instruction", None),
                    "traits_presentation_template": getattr(
                        agent, "traits_presentation_template", None
                    ),
                }
                agents_data.append(agent_data)

                # Collect all trait names from the updated agents
                if agent_traits:
                    all_traits.update(agent_traits.keys())

            # Update agent_list_data with the new data
            self.agent_list_data = {
                "agents": agents_data,
                "agent_count": len(agents_data),
                "available_traits": sorted(list(all_traits)),
                "description": getattr(self._original_agent_list, "description", ""),
                "alias": getattr(self._original_agent_list, "alias", ""),
                "visibility": getattr(
                    self._original_agent_list, "visibility", "private"
                ),
                "uuid": getattr(self._original_agent_list, "uuid", None),
            }

            # Update available traits and remove any selected traits that no longer exist
            self.available_traits = sorted(list(all_traits))
            self.selected_traits = [
                trait for trait in self.selected_traits if trait in all_traits
            ]

            # Update filtered_agents and selected_agents to use the new data structure
            # while preserving current selections based on agent names
            self.filtered_agents = [
                agent
                for agent in agents_data
                if agent.get("name", "") in current_filtered_agent_names
            ]
            self.selected_agents = [
                agent
                for agent in agents_data
                if agent.get("name", "") in current_selected_agent_names
            ]

            # Update statistics
            self._update_stats()

        except Exception as e:
            # If update fails, at least show an error message
            self.error_message = f"Error updating widget data: {str(e)}"

    def get_selected_agent_list(self):
        """Return a new AgentList with only the selected agents."""
        try:
            from edsl import Agent, AgentList

            # Convert selected agents back to Agent objects
            agents = []
            for agent_data in self.selected_agents:
                # Create agent with traits and name if available
                traits = agent_data.get("traits", {})
                agent_name = agent_data.get("name", "")

                if agent_name and not agent_name.startswith("Agent_"):
                    # This is a real name, not a generated one
                    agent = Agent(name=agent_name, traits=traits)
                else:
                    # Use default Agent creation without name
                    agent = Agent(traits=traits)

                # Set instruction if available
                if agent_data.get("instruction"):
                    agent._instruction = agent_data["instruction"]

                # Set traits presentation template if available
                if agent_data.get("traits_presentation_template"):
                    agent._traits_presentation_template = agent_data[
                        "traits_presentation_template"
                    ]

                agents.append(agent)

            # Create new AgentList
            agent_list = AgentList(agents)

            # Set metadata if available
            original_data = self.agent_list_data
            if original_data.get("description"):
                agent_list.description = original_data["description"]
            if original_data.get("alias"):
                agent_list.alias = original_data["alias"]
            if original_data.get("visibility"):
                agent_list.visibility = original_data["visibility"]

            return agent_list

        except ImportError:
            raise ImportError("EDSL package not available. Cannot create AgentList.")
        except Exception as e:
            raise Exception(f"Error creating AgentList: {str(e)}")

    def reset_filters(self):
        """Reset all filters and selections."""
        self.trait_filters = {}
        self.selected_agents = self.agent_list_data.get("agents", []).copy()
        self.filtered_agents = self.agent_list_data.get("agents", []).copy()
        self.selected_traits = self.available_traits.copy()
        self.sample_percentage = 100
        self.custom_sample_count = 0
        self.sql_query = "SELECT * FROM agents"
        self.sql_error = ""
        self.is_edited = False
        self._update_stats()

    def _update_original_agent_list(self):
        """Update the original AgentList with the currently selected agents."""
        if not self._original_agent_list:
            self.update_status = "Error: No original agent list to update"
            self.update_success = False
            return

        if not self.selected_agents:
            self.update_status = "Error: No agents selected"
            self.update_success = False
            return

        try:
            from edsl import Agent

            # Convert selected agents back to Agent objects
            new_agents = []
            for agent_data in self.selected_agents:
                # Only include traits that are selected for display
                all_traits = agent_data.get("traits", {})
                filtered_traits = {
                    trait: all_traits[trait]
                    for trait in self.selected_traits
                    if trait in all_traits
                }

                agent_name = agent_data.get("name", "")

                if agent_name and not agent_name.startswith("Agent_"):
                    # This is a real name, not a generated one
                    agent = Agent(name=agent_name, traits=filtered_traits)
                else:
                    # Use default Agent creation without name
                    agent = Agent(traits=filtered_traits)

                # Set instruction if available
                if agent_data.get("instruction"):
                    agent._instruction = agent_data["instruction"]

                # Set traits presentation template if available
                if agent_data.get("traits_presentation_template"):
                    agent._traits_presentation_template = agent_data[
                        "traits_presentation_template"
                    ]

                new_agents.append(agent)

            # Clear the original agent list and add the new agents
            self._original_agent_list.clear()
            for agent in new_agents:
                self._original_agent_list.append(agent)

            # Update status
            trait_count = len(self.selected_traits)
            self.update_status = f"Successfully updated agent list with {len(new_agents)} agents and {trait_count} traits"
            self.update_success = True
            self.is_edited = False  # Reset edited flag since changes are applied

            # DON'T update widget data here - it would reset the frontend
            # The frontend should continue showing the current filtered/selected state
            # The original AgentList has been updated, which is what matters

        except ImportError:
            self.update_status = "Error: EDSL package not available"
            self.update_success = False
        except Exception as e:
            self.update_status = f"Error updating agent list: {str(e)}"
            self.update_success = False


# Convenience function for easy import
def create_agent_list_builder_widget(agent_list=None):
    """Create and return a new Agent List Builder Widget instance."""
    return AgentListBuilderWidget(agent_list=agent_list)


# Export the main class
__all__ = ["AgentListBuilderWidget", "create_agent_list_builder_widget"]
