"""
Survey Inspector Widget

An interactive widget for inspecting EDSL Survey objects, providing detailed views
of questions, rules, flow logic, and survey structure.
"""

from typing import Any, Dict, List, Optional
from .inspector_widget import InspectorWidget


class SurveyInspectorWidget(InspectorWidget):
    """Interactive widget for inspecting EDSL Survey objects.
    
    This widget provides a comprehensive interface for exploring surveys:
    
    - Overview: Survey statistics, question count, rule summary
    - Questions: Interactive list of questions with click-through details
    - Rules: Survey flow rules and conditional logic
    - Structure: Question dependencies and survey flow visualization
    - Configuration: Survey settings, memory plan, and advanced features
    
    Example:
        >>> from edsl.surveys import Survey
        >>> from edsl.questions import QuestionFreeText, QuestionMultipleChoice
        >>> from edsl.widgets import SurveyInspectorWidget
        >>> 
        >>> survey = Survey([
        ...     QuestionFreeText(question_name="name", question_text="What is your name?"),
        ...     QuestionMultipleChoice(
        ...         question_name="satisfaction",
        ...         question_text="How satisfied are you?", 
        ...         question_options=["Very Satisfied", "Satisfied", "Neutral", "Dissatisfied"]
        ...     )
        ... ])
        >>> 
        >>> widget = SurveyInspectorWidget(survey)
        >>> widget  # Display in Jupyter notebook
    """

    # Define which EDSL class this inspector handles
    associated_class = "Survey"
    
    def __init__(self, obj=None, **kwargs):
        """Initialize the Survey Inspector Widget.
        
        Args:
            obj: An EDSL Survey instance to inspect.
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(obj, **kwargs)
    
    def _process_object_data(self):
        """No additional processing needed - Survey.to_dict() has everything we need."""
        pass
    
    def _validate_object(self, obj) -> bool:
        """Validate that the object is a Survey instance."""
        if obj is None:
            return True
        return (hasattr(obj, 'questions') and hasattr(obj, 'rules') and 
                hasattr(obj, '__len__')) or type(obj).__name__ == 'Survey'

    def _safe_to_dict(self, obj):
        """Override to handle Survey's specific to_dict signature."""
        try:
            # Survey supports standard to_dict
            return obj.to_dict(add_edsl_version=True)
        except Exception as e:
            return {
                'error': f"Failed to convert object to dictionary: {str(e)}",
                'type': type(obj).__name__,
                'str_representation': str(obj)
            }

    @property
    def questions_data(self):
        """Get the questions data for frontend compatibility."""
        return self.data.get('questions', [])

    @property
    def rules_data(self):
        """Get the rules data for frontend compatibility."""
        return self.data.get('rule_collection', {}).get('rules', [])

    def _enhance_summary(self, summary: Dict[str, Any]):
        """Add survey-specific summary information."""
        questions_data = self.questions_data
        rules_data = self.rules_data
        
        if not questions_data:
            summary.update({
                'question_count': 0,
                'rule_count': 0,
                'question_types': {},
                'has_memory_plan': False,
                'has_question_groups': False
            })
            return
        
        # Analyze question types
        question_types = {}
        for question in questions_data:
            qtype = question.get('question_type', 'unknown')
            question_types[qtype] = question_types.get(qtype, 0) + 1
        
        # Check for advanced features
        has_memory_plan = bool(self.data.get('memory_plan'))
        has_question_groups = bool(self.data.get('question_groups'))
        has_rules = len(rules_data) > 0
        
        summary.update({
            'question_count': len(questions_data),
            'rule_count': len(rules_data),
            'question_types': question_types,
            'has_memory_plan': has_memory_plan,
            'has_question_groups': has_question_groups,
            'has_rules': has_rules,
            'is_linear': not has_rules  # Linear if no branching rules
        })


# Convenience function for easy import
def create_survey_inspector_widget(survey=None):
    """Create and return a new Survey Inspector Widget instance."""
    return SurveyInspectorWidget(obj=survey)


# Export the main class
__all__ = ["SurveyInspectorWidget", "create_survey_inspector_widget"]