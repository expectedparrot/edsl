"""
Survey Manager Widget

An anywidget for managing EDSL Surveys with pagination, deletion, and UUID copying.
"""

import traitlets
from typing import Dict, Any, List, Optional
from .base_widget import EDSLBaseWidget


class SurveyManagerWidget(EDSLBaseWidget):
    """A widget for managing EDSL Surveys with table view, pagination, and actions."""

    # Traitlets for bidirectional communication
    current_page = traitlets.Int(1).tag(sync=True)
    surveys = traitlets.List([]).tag(sync=True)
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
        self._load_surveys()

    def _on_load_request(self, change):
        """Handle refresh request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        # Reset to first page and clear existing data
        self.current_page = 1
        self.surveys = []
        self.has_more_pages = True
        self._load_surveys()

    def _on_load_more_request(self, change):
        """Handle load more request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
            
        if self.has_more_pages and not self.loading_more:
            self.current_page += 1
            self._load_surveys(append_mode=True)

    def _on_delete_request(self, change):
        """Handle delete request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
            
        uuid = request.get("uuid")
        if uuid:
            self._delete_survey(uuid)

    def _on_copy_request(self, change):
        """Handle copy UUID request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
            
        # For copy requests, we just need to acknowledge - the frontend handles clipboard
        uuid = request.get("uuid")
        if uuid:
            print(f"UUID copied to clipboard: {uuid}")

    def _load_surveys(self, append_mode=False):
        """Load surveys from EDSL with pagination."""
        if append_mode:
            self.loading_more = True
        else:
            self.loading = True
        self.error_message = ""
        
        try:
            from edsl import Survey
            
            # Get surveys with pagination
            result = Survey.list(page=self.current_page)
            
            # The result is a CoopRegularObjects containing Survey objects
            surveys_data = result if hasattr(result, '__iter__') else []
            
            # Check if we have more pages (if this page returned fewer than expected items, we're at the end)
            # Most APIs return 10 items per page, so if we get less than 10, we're at the end
            if len(surveys_data) < 10:
                self.has_more_pages = False
            
            # Convert survey objects to dictionaries for frontend
            formatted_surveys = []
            for survey_obj in surveys_data:
                try:
                    # The actual data is in survey_obj.data
                    data = survey_obj.data if hasattr(survey_obj, 'data') else {}
                    
                    # Extract relevant fields from the data
                    formatted_surveys.append({
                        'uuid': data.get('uuid', 'N/A'),
                        'name': data.get('alias', 'Unnamed'),
                        'description': data.get('description', ''),
                        'question_count': 'N/A',  # This info might not be available in the list
                        'created_at': data.get('created_ts', ''),
                        'updated_at': data.get('last_updated_ts', ''),
                        'owner': data.get('owner_username', ''),
                        'visibility': data.get('visibility', ''),
                        'version': data.get('version', ''),
                        'url': data.get('url', ''),
                    })
                except Exception as e:
                    # If we can't access data, create a minimal entry
                    formatted_surveys.append({
                        'uuid': 'Unknown',
                        'name': 'Error loading Survey',
                        'description': f'Error accessing details: {str(e)}',
                        'question_count': 0,
                        'created_at': '',
                        'updated_at': '',
                        'owner': '',
                        'visibility': '',
                        'version': '',
                        'url': '',
                    })
            
            # In append mode, add to existing list; otherwise replace
            if append_mode:
                current_surveys = list(self.surveys)
                current_surveys.extend(formatted_surveys)
                self.surveys = current_surveys
            else:
                self.surveys = formatted_surveys
            
        except ImportError as e:
            self.error_message = f"EDSL not installed. Please install with: pip install edsl\nDetails: {str(e)}"
            if not append_mode:
                self.surveys = []
        except Exception as e:
            self.error_message = f"Error loading surveys: {str(e)}"
            if not append_mode:
                self.surveys = []
        finally:
            self.loading = False
            self.loading_more = False

    def _delete_survey(self, uuid: str):
        """Delete a survey by UUID."""
        try:
            from edsl import Survey
            
            # Delete the survey - the method returns None but throws exception on failure
            Survey.delete(uuid)
            
            # If we get here, deletion was successful - reload the current page
            self._load_surveys()
                
        except ImportError as e:
            self.error_message = f"EDSL not installed. Please install with: pip install edsl"
        except AttributeError:
            self.error_message = "Delete functionality not available in current EDSL version"
        except Exception as e:
            self.error_message = f"Error deleting survey: {str(e)}"

    def refresh(self):
        """Refresh and reload from the beginning."""
        self.current_page = 1
        self.surveys = []
        self.has_more_pages = True
        self._load_surveys()
    
    def load_more(self):
        """Load more surveys."""
        if self.has_more_pages and not self.loading_more:
            self.current_page += 1
            self._load_surveys(append_mode=True)


# Convenience function for easy import
def create_survey_manager_widget():
    """Create and return a new Survey Manager Widget instance."""
    return SurveyManagerWidget()


# Export the main class
__all__ = ["SurveyManagerWidget", "create_survey_manager_widget"]