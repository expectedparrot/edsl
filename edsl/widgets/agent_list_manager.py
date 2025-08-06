"""
Agent List Manager Widget

An anywidget for managing EDSL AgentLists with pagination, deletion, and UUID copying.
"""

import traitlets
from typing import Dict, Any, List, Optional
from .base_widget import EDSLBaseWidget


class AgentListManagerWidget(EDSLBaseWidget):
    """A widget for managing EDSL AgentLists with table view, pagination, and actions."""

    widget_short_name = "agent_list_manager"

    # Traitlets for bidirectional communication
    current_page = traitlets.Int(1).tag(sync=True)
    agent_lists = traitlets.List([]).tag(sync=True)
    has_more_pages = traitlets.Bool(True).tag(sync=True)
    loading = traitlets.Bool(False).tag(sync=True)
    loading_more = traitlets.Bool(False).tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)

    # Action requests from frontend
    load_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    load_more_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    delete_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    copy_request = traitlets.Dict({"is_default": True}).tag(sync=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set up observers for frontend requests
        self.observe(self._on_load_request, names=["load_request"])
        self.observe(self._on_load_more_request, names=["load_more_request"])
        self.observe(self._on_delete_request, names=["delete_request"])
        self.observe(self._on_copy_request, names=["copy_request"])

        # Load initial data
        self._load_agent_lists()

    def _on_load_request(self, change):
        """Handle refresh request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        # Reset to first page and clear existing data
        self.current_page = 1
        self.agent_lists = []
        self.has_more_pages = True
        self._load_agent_lists()

    def _on_load_more_request(self, change):
        """Handle load more request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        if self.has_more_pages and not self.loading_more:
            self.current_page += 1
            self._load_agent_lists(append_mode=True)

    def _on_delete_request(self, change):
        """Handle delete request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        uuid = request.get("uuid")
        if uuid:
            self._delete_agent_list(uuid)

    def _on_copy_request(self, change):
        """Handle copy UUID request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return

        # For copy requests, we just need to acknowledge - the frontend handles clipboard
        uuid = request.get("uuid")
        if uuid:
            print(f"UUID copied to clipboard: {uuid}")

    def _load_agent_lists(self, append_mode=False):
        """Load agent lists from EDSL with pagination."""
        if append_mode:
            self.loading_more = True
        else:
            self.loading = True
        self.error_message = ""

        try:
            from edsl import AgentList

            # Get agent lists with pagination
            result = AgentList.list(page=self.current_page)

            # The result is a CoopRegularObjects containing Scenario objects
            agent_lists_data = result if hasattr(result, "__iter__") else []

            # Check if we have more pages (if this page returned fewer than expected items, we're at the end)
            # Most APIs return 10 items per page, so if we get less than 10, we're at the end
            if len(agent_lists_data) < 10:
                self.has_more_pages = False

            # Convert scenario objects to dictionaries for frontend
            formatted_lists = []
            for scenario in agent_lists_data:
                try:
                    # The actual data is in scenario.data
                    data = scenario.data if hasattr(scenario, "data") else {}

                    # Extract relevant fields from the data
                    formatted_lists.append(
                        {
                            "uuid": data.get("uuid", "N/A"),
                            "name": data.get("alias", "Unnamed"),
                            "description": data.get("description", ""),
                            "agent_count": "N/A",  # This info might not be available in the list
                            "created_at": data.get("created_ts", ""),
                            "updated_at": data.get("last_updated_ts", ""),
                            "owner": data.get("owner_username", ""),
                            "visibility": data.get("visibility", ""),
                            "version": data.get("version", ""),
                            "url": data.get("url", ""),
                        }
                    )
                except Exception as e:
                    # If we can't access data, create a minimal entry
                    formatted_lists.append(
                        {
                            "uuid": "Unknown",
                            "name": "Error loading AgentList",
                            "description": f"Error accessing details: {str(e)}",
                            "agent_count": 0,
                            "created_at": "",
                            "updated_at": "",
                            "owner": "",
                            "visibility": "",
                            "version": "",
                            "url": "",
                        }
                    )

            # In append mode, add to existing list; otherwise replace
            if append_mode:
                current_lists = list(self.agent_lists)
                current_lists.extend(formatted_lists)
                self.agent_lists = current_lists
            else:
                self.agent_lists = formatted_lists

        except ImportError as e:
            self.error_message = f"EDSL not installed. Please install with: pip install edsl\nDetails: {str(e)}"
            if not append_mode:
                self.agent_lists = []
        except Exception as e:
            self.error_message = f"Error loading agent lists: {str(e)}"
            if not append_mode:
                self.agent_lists = []
        finally:
            self.loading = False
            self.loading_more = False

    def _delete_agent_list(self, uuid: str):
        """Delete an agent list by UUID."""
        try:
            from edsl import AgentList

            # Delete the agent list - the method returns None but throws exception on failure
            AgentList.delete(uuid)

            # If we get here, deletion was successful - reload the current page
            self._load_agent_lists()

        except ImportError as e:
            self.error_message = (
                f"EDSL not installed. Please install with: pip install edsl"
            )
        except AttributeError:
            self.error_message = (
                "Delete functionality not available in current EDSL version"
            )
        except Exception as e:
            self.error_message = f"Error deleting agent list: {str(e)}"

    def refresh(self):
        """Refresh and reload from the beginning."""
        self.current_page = 1
        self.agent_lists = []
        self.has_more_pages = True
        self._load_agent_lists()

    def load_more(self):
        """Load more agent lists."""
        if self.has_more_pages and not self.loading_more:
            self.current_page += 1
            self._load_agent_lists(append_mode=True)


# Convenience function for easy import
def create_agent_list_manager_widget():
    """Create and return a new Agent List Manager Widget instance."""
    return AgentListManagerWidget()


# Export the main class
__all__ = ["AgentListManagerWidget", "create_agent_list_manager_widget"]
