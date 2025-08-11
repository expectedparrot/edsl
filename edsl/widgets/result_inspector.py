"""
Result Inspector Widget

An anywidget for inspecting individual EDSL Results with detailed views of agent,
scenario, model, answers, prompts, and raw data structure.
"""

import traitlets
from .inspector_widget import InspectorWidget


class ResultInspectorWidget(InspectorWidget):
    """Interactive widget for inspecting individual EDSL Result objects with detailed exploration."""

    widget_short_name = "result_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "Result"

    # Result-specific data traitlet for JavaScript frontend
    result_data = traitlets.Dict().tag(sync=True)

    # UI state traitlets (additional to parent class data traitlet)
    active_tab = traitlets.Unicode("overview").tag(sync=True)
    expanded_sections = traitlets.List(["answers"]).tag(sync=True)
    copied_item = traitlets.Unicode("").tag(sync=True)
    loading = traitlets.Bool(False).tag(sync=True)
    error_message = traitlets.Unicode("").tag(sync=True)

    # Action requests from frontend
    tab_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    section_request = traitlets.Dict({"is_default": True}).tag(sync=True)
    copy_request = traitlets.Dict({"is_default": True}).tag(sync=True)

    def __init__(self, obj=None, **kwargs):
        """Initialize the Result Inspector Widget.

        Args:
            obj: An EDSL Result object to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(obj, **kwargs)

        # Set up observers for frontend requests
        self.observe(self._on_tab_request, names=["tab_request"])
        self.observe(self._on_section_request, names=["section_request"])
        self.observe(self._on_copy_request, names=["copy_request"])

    def _process_object_data(self):
        """Extract data from Result object using by_question_data() method."""
        if not self.object or not self.data:
            return

        try:
            self.loading = True
            self.error_message = ""

            # Use by_question_data() to get the properly formatted data for the widget
            if hasattr(self.object, "by_question_data"):
                result_dict = self.object.by_question_data()

                # Transform the by_question_data structure into the format expected by the widget
                processed_data = {
                    "agent": result_dict.get("agent_data", {}),
                    "scenario": result_dict.get("scenario_data", {}),
                    "model": {},  # by_question_data doesn't include model, we'll get it from self.data if available
                    "iteration": 0,  # by_question_data doesn't include iteration
                    "answer": {},
                    "prompt": {},
                    "raw_model_response": {},
                    "question_to_attributes": {},
                    "generated_tokens": {},
                    "comments_dict": {},
                    "reasoning_summaries_dict": {},
                    "cache_keys": {},
                    "validated_dict": {},
                    "indices": {},
                }

                # Process question_data into the various dictionaries the widget expects
                question_data = result_dict.get("question_data", {})
                for question_name, question_info in question_data.items():
                    processed_data["answer"][question_name] = question_info.get(
                        "answer"
                    )
                    processed_data["prompt"][question_name] = {
                        "user_prompt": question_info.get("user_prompt"),
                        "system_prompt": question_info.get("system_prompt"),
                    }
                    processed_data["raw_model_response"][question_name] = (
                        question_info.get("raw_model_response")
                    )
                    processed_data["question_to_attributes"][question_name] = {
                        "question_text": question_info.get("question_text"),
                        "question_type": question_info.get("question_type"),
                        "question_options": question_info.get("question_options"),
                    }
                    processed_data["generated_tokens"][question_name] = (
                        question_info.get("generated_tokens")
                    )
                    processed_data["comments_dict"][question_name] = question_info.get(
                        "comment"
                    )
                    processed_data["reasoning_summaries_dict"][question_name] = (
                        question_info.get("reasoning_summary")
                    )
                    processed_data["cache_keys"][question_name] = question_info.get(
                        "cache_key"
                    )
                    processed_data["validated_dict"][question_name] = question_info.get(
                        "validated"
                    )

                # Add the processed result data to both self.data (parent pattern) and result_data (for JS)
                self.data.update(processed_data)
                self.result_data = processed_data
            else:
                # Fallback to original logic if by_question_data is not available
                self.error_message = (
                    "Result object does not have by_question_data method"
                )

        except Exception as e:
            self.error_message = f"Error processing result: {str(e)}"
        finally:
            self.loading = False

    def _validate_object(self, obj) -> bool:
        """Validate that the object is a Result."""
        if obj is None:
            return True
        return hasattr(obj, "by_question_data") or type(obj).__name__ == "Result"

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
        return len(self.result_data.get("answer", {}))

    def get_question_names(self):
        """Get list of question names."""
        return list(self.result_data.get("answer", {}).keys())

    def get_agent_traits(self):
        """Get agent traits as a dictionary."""
        agent = self.result_data.get("agent", {})
        return agent.get("traits", {})

    def get_model_info(self):
        """Get model information."""
        model = self.result_data.get("model", {})
        return {
            "model": model.get("model", "Unknown"),
            "service": model.get("inference_service", "Unknown"),
            "parameters": model.get("parameters", {}),
        }

    def get_token_usage(self):
        """Extract token usage information from raw model response."""
        raw_response = self.result_data.get("raw_model_response", {})
        token_info = {}

        for key, value in raw_response.items():
            if "token" in key.lower() or "cost" in key.lower():
                token_info[key] = value

        return token_info

    def get_validation_status(self):
        """Get validation status for all questions."""
        validated_dict = self.result_data.get("validated_dict", {})
        total_questions = len(self.result_data.get("answer", {}))
        validated_count = sum(1 for v in validated_dict.values() if v)

        return {
            "total": total_questions,
            "validated": validated_count,
            "validation_rate": (validated_count / max(1, total_questions)) * 100,
            "details": validated_dict,
        }

    def export_as_json(self):
        """Export result data as JSON string."""
        import json

        return json.dumps(self.result_data, indent=2, default=str)


# Convenience function for easy import
def create_result_inspector_widget(result=None):
    """Create and return a new Result Inspector Widget instance."""
    return ResultInspectorWidget(obj=result)


# Export the main class
__all__ = ["ResultInspectorWidget", "create_result_inspector_widget"]
