"""
Result Inspector Widget

An anywidget for inspecting individual EDSL Results with detailed views of agent,
scenario, model, answers, prompts, and raw data structure.
"""

import traitlets
from typing import Any, Dict, List, Optional
from .base_widget import EDSLBaseWidget


class ResultInspectorWidget(EDSLBaseWidget):
    """Interactive widget for inspecting individual EDSL Result objects with detailed exploration."""

    # Traitlets for data communication with frontend
    result = traitlets.Any(allow_none=True).tag(sync=False)
    result_data = traitlets.Dict().tag(sync=True)
    
    # UI state
    active_tab = traitlets.Unicode('overview').tag(sync=True)
    expanded_sections = traitlets.List(['answers']).tag(sync=True)
    copied_item = traitlets.Unicode('').tag(sync=True)
    loading = traitlets.Bool(False).tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)
    
    # Action requests from frontend
    tab_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    section_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    copy_request = traitlets.Dict({"is_default": True}).tag(sync=True)

    def __init__(self, result=None, **kwargs):
        super().__init__(**kwargs)
        
        # Set up observers for frontend requests
        self.observe(self._on_tab_request, names=["tab_request"])
        self.observe(self._on_section_request, names=["section_request"])
        self.observe(self._on_copy_request, names=["copy_request"])
        
        # Initialize with result if provided
        if result is not None:
            self.result = result

    @traitlets.observe('result')
    def _on_result_change(self, change):
        """Update widget data when result changes."""
        if change['new'] is not None:
            self._extract_result_data()

    def _extract_result_data(self):
        """Extract and process data from the Result object."""
        if self.result is None:
            self._reset_data()
            return

        try:
            self.loading = True
            self.error_message = ""
            
            # Convert result to dictionary format for frontend
            result_dict = {}
            
            # Handle dictionary input
            if isinstance(self.result, dict):
                result_dict = self.result
            else:
                # Handle EDSL Result object - convert to dict
                try:
                    result_dict = dict(self.result)
                except:
                    # Fallback: manually extract attributes
                    result_dict = self._extract_result_attributes()
            
            # Ensure all expected sections exist with defaults
            processed_data = {
                'agent': result_dict.get('agent', {}),
                'scenario': result_dict.get('scenario', {}),
                'model': result_dict.get('model', {}),
                'iteration': result_dict.get('iteration', 0),
                'answer': result_dict.get('answer', {}),
                'prompt': result_dict.get('prompt', {}),
                'raw_model_response': result_dict.get('raw_model_response', {}),
                'question_to_attributes': result_dict.get('question_to_attributes', {}),
                'generated_tokens': result_dict.get('generated_tokens', {}),
                'comments_dict': result_dict.get('comments_dict', {}),
                'reasoning_summaries_dict': result_dict.get('reasoning_summaries_dict', {}),
                'cache_keys': result_dict.get('cache_keys', {}),
                'validated_dict': result_dict.get('validated_dict', {}),
                'indices': result_dict.get('indices', {})
            }
            
            # Clean up agent data if it's an object
            if hasattr(processed_data['agent'], '__dict__'):
                agent_dict = {}
                if hasattr(processed_data['agent'], 'traits'):
                    try:
                        agent_dict['traits'] = dict(processed_data['agent'].traits)
                    except:
                        agent_dict['traits'] = {}
                if hasattr(processed_data['agent'], 'edsl_version'):
                    agent_dict['edsl_version'] = processed_data['agent'].edsl_version
                if hasattr(processed_data['agent'], 'edsl_class_name'):
                    agent_dict['edsl_class_name'] = processed_data['agent'].edsl_class_name
                if hasattr(processed_data['agent'], 'name'):
                    agent_dict['name'] = processed_data['agent'].name
                processed_data['agent'] = agent_dict
            
            # Clean up scenario data if it's an object
            if hasattr(processed_data['scenario'], '__dict__'):
                scenario_dict = {}
                for attr in ['period', 'scenario_index', 'edsl_version', 'edsl_class_name']:
                    if hasattr(processed_data['scenario'], attr):
                        scenario_dict[attr] = getattr(processed_data['scenario'], attr)
                # Also extract any scenario variables
                if hasattr(processed_data['scenario'], '__dict__'):
                    for key, value in processed_data['scenario'].__dict__.items():
                        if not key.startswith('_') and key not in scenario_dict:
                            scenario_dict[key] = value
                processed_data['scenario'] = scenario_dict
            
            # Clean up model data if it's an object
            if hasattr(processed_data['model'], '__dict__'):
                model_dict = {}
                for attr in ['model', 'parameters', 'inference_service', 'edsl_version', 'edsl_class_name']:
                    if hasattr(processed_data['model'], attr):
                        model_dict[attr] = getattr(processed_data['model'], attr)
                processed_data['model'] = model_dict
            
            self.result_data = processed_data

        except Exception as e:
            self.error_message = f"Error processing result: {str(e)}"
            self._reset_data()
        finally:
            self.loading = False

    def _extract_result_attributes(self):
        """Manually extract attributes from Result object."""
        result_dict = {}
        
        # Common attributes to extract
        attrs_to_extract = [
            'agent', 'scenario', 'model', 'iteration', 'answer', 'prompt',
            'raw_model_response', 'question_to_attributes', 'generated_tokens',
            'comments_dict', 'reasoning_summaries_dict', 'cache_keys',
            'validated_dict', 'indices'
        ]
        
        for attr in attrs_to_extract:
            # Try both getattr and dict-like access
            if hasattr(self.result, attr):
                result_dict[attr] = getattr(self.result, attr)
            elif hasattr(self.result, 'keys') and attr in self.result.keys():
                try:
                    result_dict[attr] = self.result[attr]
                except:
                    pass
        
        # Also extract any other attributes that don't start with underscore
        if hasattr(self.result, '__dict__'):
            for key, value in self.result.__dict__.items():
                if not key.startswith('_') and key not in result_dict:
                    result_dict[key] = value
        
        return result_dict

    def _reset_data(self):
        """Reset all data to empty state."""
        self.result_data = {
            'agent': {},
            'scenario': {},
            'model': {},
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

    def _on_tab_request(self, change):
        """Handle tab change request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        tab_id = request.get("tab", "overview")
        self.active_tab = tab_id

    def _on_section_request(self, change):
        """Handle section expand/collapse request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        section = request.get("section")
        if section:
            current_expanded = list(self.expanded_sections)
            if section in current_expanded:
                current_expanded.remove(section)
            else:
                current_expanded.append(section)
            self.expanded_sections = current_expanded

    def _on_copy_request(self, change):
        """Handle copy to clipboard request from frontend."""
        request = change.get("new", {})
        if not request or request.get("is_default"):
            return
        
        item_id = request.get("item_id", "")
        self.copied_item = item_id
        # Reset after 2 seconds (handled by frontend timer)

    def get_answer_count(self):
        """Get the number of answers in the result."""
        return len(self.result_data.get('answer', {}))

    def get_question_names(self):
        """Get list of question names."""
        return list(self.result_data.get('answer', {}).keys())

    def get_agent_traits(self):
        """Get agent traits as a dictionary."""
        agent = self.result_data.get('agent', {})
        return agent.get('traits', {})

    def get_model_info(self):
        """Get model information."""
        model = self.result_data.get('model', {})
        return {
            'model': model.get('model', 'Unknown'),
            'service': model.get('inference_service', 'Unknown'),
            'parameters': model.get('parameters', {})
        }

    def get_token_usage(self):
        """Extract token usage information from raw model response."""
        raw_response = self.result_data.get('raw_model_response', {})
        token_info = {}
        
        for key, value in raw_response.items():
            if 'token' in key.lower() or 'cost' in key.lower():
                token_info[key] = value
        
        return token_info

    def get_validation_status(self):
        """Get validation status for all questions."""
        validated_dict = self.result_data.get('validated_dict', {})
        total_questions = len(self.result_data.get('answer', {}))
        validated_count = sum(1 for v in validated_dict.values() if v)
        
        return {
            'total': total_questions,
            'validated': validated_count,
            'validation_rate': (validated_count / max(1, total_questions)) * 100,
            'details': validated_dict
        }

    def export_as_json(self):
        """Export result data as JSON string."""
        import json
        return json.dumps(self.result_data, indent=2, default=str)


# Convenience function for easy import
def create_result_inspector_widget(result=None):
    """Create and return a new Result Inspector Widget instance."""
    return ResultInspectorWidget(result=result)


# Export the main class
__all__ = ["ResultInspectorWidget", "create_result_inspector_widget"]