"""
Question Inspector Widget

An interactive widget for inspecting EDSL Question objects, providing detailed views
of question properties, validation rules, templates, and type-specific features.
"""

from typing import Any, Dict, Optional
from .inspector_widget import InspectorWidget


class QuestionInspectorWidget(InspectorWidget):
    """Interactive widget for comprehensively inspecting EDSL Question objects.

    This widget provides a multi-tabbed interface for exploring all aspects of
    a Question instance, including:

    - Overview: Basic information, question type, and key properties
    - Configuration: Question text, options, validation rules, and parameters
    - Templates: Prompt templates and rendering preview
    - Validation: Response validators and answer constraints
    - Advanced: Question metadata, serialization, and type-specific features

    Example:
        >>> from edsl.questions import QuestionMultipleChoice
        >>> from edsl.widgets import QuestionInspectorWidget
        >>>
        >>> question = QuestionMultipleChoice(
        ...     question_name="favorite_color",
        ...     question_text="What is your favorite color?",
        ...     question_options=["Red", "Blue", "Green", "Yellow", "Other"]
        ... )
        >>>
        >>> widget = QuestionInspectorWidget(question)
        >>> widget  # Display in Jupyter notebook
    """

    widget_short_name = "question_inspector"

    # Define which EDSL class this inspector handles
    associated_class = "QuestionBase"

    def _validate_object(self, obj) -> bool:
        """Validate that the object is a Question instance."""
        if obj is None:
            return True
        # Check if it's a question by looking for common question attributes
        return (
            hasattr(obj, "question_name")
            and hasattr(obj, "question_text")
            and hasattr(obj, "question_type")
        ) or "Question" in type(obj).__name__

    def _safe_to_dict(self, obj):
        """Override to handle Question's specific to_dict signature."""
        try:
            # Questions support standard to_dict
            return obj.to_dict(add_edsl_version=True)
        except Exception as e:
            return {
                "error": f"Failed to convert object to dictionary: {str(e)}",
                "type": type(obj).__name__,
                "str_representation": str(obj),
            }

    def _validate_object(self, obj) -> bool:
        """Accept any Question object type."""
        if obj is None:
            return True

        # Check if the object is any type of Question
        from edsl.questions.question_base import QuestionBase

        return isinstance(obj, QuestionBase)

    def _enhance_summary(self, summary: Dict[str, Any]):
        """Add question-specific summary information."""
        if not self.data:
            return

        # Analyze question properties
        question_type = self.data.get("question_type", "unknown")
        has_options = bool(self.data.get("question_options"))

        # Count various question features
        features = {
            "has_options": has_options,
            "has_min_value": "min_value" in self.data,
            "has_max_value": "max_value" in self.data,
            "has_min_selections": "min_selections" in self.data,
            "has_max_selections": "max_selections" in self.data,
            "has_other_option": self.data.get("include_other", False),
            "has_randomize": self.data.get("randomize_options", False),
        }

        # Get option count if available
        option_count = 0
        if has_options:
            options = self.data.get("question_options", [])
            option_count = len(options) if isinstance(options, list) else 0

        summary.update(
            {
                "question_name": self.data.get("question_name", "unnamed"),
                "question_type": question_type,
                "option_count": option_count,
                "features": features,
                "has_validation": any(
                    [
                        "min_value" in self.data,
                        "max_value" in self.data,
                        "min_selections" in self.data,
                        "max_selections" in self.data,
                    ]
                ),
            }
        )


# Convenience function for easy import
def create_question_inspector_widget(question=None):
    """Create and return a new Question Inspector Widget instance."""
    return QuestionInspectorWidget(obj=question)


# Export the main class
__all__ = ["QuestionInspectorWidget", "create_question_inspector_widget"]
