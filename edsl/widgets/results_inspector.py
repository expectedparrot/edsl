"""
Results Inspector Widget

An interactive widget for inspecting EDSL Results objects (collections of Result objects)
with detailed views of the survey, individual results, and aggregate statistics.
"""

import traitlets
from typing import Any, Dict, List, Optional
from .inspector_widget import InspectorWidget


class ResultsInspectorWidget(InspectorWidget):
    """Interactive widget for inspecting EDSL Results objects (collections of Result objects)."""

    # Define which EDSL class this inspector handles
    associated_class = "Results"
    
    # Results-specific data traitlet for JavaScript frontend
    results_data = traitlets.Dict().tag(sync=True)
    
    # UI state traitlets
    active_tab = traitlets.Unicode('overview').tag(sync=True)
    selected_result_index = traitlets.Int(-1).tag(sync=True)
    expanded_sections = traitlets.List(['survey', 'results']).tag(sync=True)
    page_size = traitlets.Int(10).tag(sync=True)
    current_page = traitlets.Int(0).tag(sync=True)
    
    # Action requests from frontend
    tab_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    result_select_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    page_request = traitlets.Dict({"is_default": True}).tag(sync=True)

    def __init__(self, obj=None, **kwargs):
        """Initialize the Results Inspector Widget.
        
        Args:
            obj: An EDSL Results object to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(obj, **kwargs)
        
        # Set up observers for frontend requests
        self.observe(self._on_tab_request, names=["tab_request"])
        self.observe(self._on_result_select_request, names=["result_select_request"])
        self.observe(self._on_page_request, names=["page_request"])

    def _process_object_data(self):
        """Extract data from Results object by calling by_question_data() on each Result."""
        if not self.object or not self.data:
            return
            
        try:
            # Results object structure from to_dict()
            results_dict = self.data
            
            # Extract survey information
            survey_data = results_dict.get('survey', {})
            
            # Process each individual Result using by_question_data()
            processed_results = []
            results_list = results_dict.get('data', [])
            
            for i, result_data in enumerate(results_list):
                try:
                    # Get the actual Result object from the Results collection
                    if i < len(self.object) and hasattr(self.object[i], 'by_question_data'):
                        result_obj = self.object[i]
                        by_question_data = result_obj.by_question_data()
                        
                        # Transform to format expected by Result viewer component
                        processed_result = self._transform_result_data(by_question_data, i)
                        processed_results.append(processed_result)
                    else:
                        # Fallback: use raw result data
                        processed_results.append({
                            'index': i,
                            'agent': result_data.get('agent', {}),
                            'scenario': result_data.get('scenario', {}), 
                            'answers': result_data.get('answer', {}),
                            'error': 'Could not process result with by_question_data'
                        })
                        
                except Exception as e:
                    processed_results.append({
                        'index': i,
                        'error': f'Error processing result {i}: {str(e)}'
                    })
            
            # Create the data structure for the frontend
            results_widget_data = {
                'survey': self._process_survey_data(survey_data),
                'results': processed_results,
                'total_results': len(processed_results),
                'created_columns': results_dict.get('created_columns', []),
                'cache_info': self._extract_cache_info(results_dict.get('cache', {}))
            }
            
            # Update both data stores
            self.data.update(results_widget_data)
            self.results_data = results_widget_data
            
        except Exception as e:
            error_data = {'error': f"Error processing Results object: {str(e)}"}
            self.data.update(error_data)  
            self.results_data = error_data

    def _transform_result_data(self, by_question_data: Dict, index: int) -> Dict:
        """Transform by_question_data into format expected by Result viewer."""
        question_data = by_question_data.get('question_data', {})
        
        # Create the same structure as ResultInspectorWidget expects
        result_data = {
            'index': index,
            'agent': by_question_data.get('agent_data', {}),
            'scenario': by_question_data.get('scenario_data', {}),
            'model': {},  # by_question_data doesn't include model info
            'iteration': 0,  
            'answer': {},
            'prompt': {},
            'raw_model_response': {},
            'question_to_attributes': {},
            'generated_tokens': {},
            'comments_dict': {},
            'reasoning_summaries_dict': {},
            'cache_keys': {},
            'validated_dict': {},
            'indices': {}
        }
        
        # Process question data into the various dictionaries
        for question_name, question_info in question_data.items():
            result_data['answer'][question_name] = question_info.get('answer')
            result_data['prompt'][question_name] = {
                'user_prompt': question_info.get('user_prompt'),
                'system_prompt': question_info.get('system_prompt')
            }
            result_data['raw_model_response'][question_name] = question_info.get('raw_model_response')
            result_data['question_to_attributes'][question_name] = {
                'question_text': question_info.get('question_text'),
                'question_type': question_info.get('question_type'),
                'question_options': question_info.get('question_options')
            }
            result_data['generated_tokens'][question_name] = question_info.get('generated_tokens')
            result_data['comments_dict'][question_name] = question_info.get('comment')
            result_data['reasoning_summaries_dict'][question_name] = question_info.get('reasoning_summary')
            result_data['cache_keys'][question_name] = question_info.get('cache_key')
            result_data['validated_dict'][question_name] = question_info.get('validated')
        
        return result_data

    def _process_survey_data(self, survey_data: Dict) -> Dict:
        """Process survey data for display."""
        return {
            'questions': survey_data.get('questions', []),
            'question_count': len(survey_data.get('questions', [])),
            'question_names': [q.get('question_name', '') for q in survey_data.get('questions', [])],
            'question_types': [q.get('question_type', '') for q in survey_data.get('questions', [])],
            'edsl_version': survey_data.get('edsl_version'),
            'edsl_class_name': survey_data.get('edsl_class_name')
        }

    def _extract_cache_info(self, cache_data: Dict) -> Dict:
        """Extract cache information for display."""
        return {
            'cache_entries': len(cache_data.get('data', {})),
            'has_cache': bool(cache_data.get('data'))
        }

    def _validate_object(self, obj) -> bool:
        """Validate that the object is a Results object."""
        if obj is None:
            return True
        return (hasattr(obj, 'survey') and hasattr(obj, 'data') and 
                hasattr(obj, '__len__') and hasattr(obj, '__iter__')) or type(obj).__name__ == 'Results'

    def _on_tab_request(self, change):
        """Handle tab change request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        tab_id = request.get("tab", "overview")
        self.active_tab = tab_id

    def _on_result_select_request(self, change):
        """Handle result selection request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        result_index = request.get("index", -1)
        self.selected_result_index = result_index

    def _on_page_request(self, change):
        """Handle pagination request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        page = request.get("page", 0)
        page_size = request.get("page_size", self.page_size)
        
        self.current_page = page
        if page_size != self.page_size:
            self.page_size = page_size

    # Utility methods for external access
    def get_results_count(self):
        """Get the number of results."""
        return len(self.results_data.get('results', []))

    def get_survey_info(self):
        """Get survey information."""
        survey = self.results_data.get('survey', {})
        return {
            'question_count': survey.get('question_count', 0),
            'question_names': survey.get('question_names', []),
            'question_types': survey.get('question_types', [])
        }

    def get_result_by_index(self, index: int):
        """Get a specific result by index."""
        results = self.results_data.get('results', [])
        if 0 <= index < len(results):
            return results[index]
        return None

    def get_paginated_results(self, page: int = 0, page_size: int = 10):
        """Get a paginated subset of results."""
        results = self.results_data.get('results', [])
        start = page * page_size
        end = start + page_size
        return results[start:end]


# Convenience function for easy import
def create_results_inspector_widget(results=None):
    """Create and return a new Results Inspector Widget instance."""
    return ResultsInspectorWidget(obj=results)


# Export the main class
__all__ = ["ResultsInspectorWidget", "create_results_inspector_widget"]