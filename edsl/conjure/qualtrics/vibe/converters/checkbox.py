"""
QuestionCheckBox converter implementation.
"""

from typing import Dict, Any
from edsl.questions import Question, QuestionCheckBox
from .base import AbstractQuestionConverter


class CheckBoxConverter(AbstractQuestionConverter):
    """Converts questions to QuestionCheckBox format."""

    @property
    def target_type(self) -> str:
        return "QuestionCheckBox"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to checkbox."""
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionCheckBox"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for checkbox conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }

        # Extract options from various sources
        options = self._determine_options(question, analysis)
        if options:
            params["question_options"] = options
        else:
            raise ValueError(f"Cannot convert {question.question_name} to CheckBox: no options available")

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionCheckBox with extracted parameters."""
        return QuestionCheckBox(**params)

    def _determine_options(self, question: Question, analysis: Dict[str, Any]) -> list:
        """Determine the best options for the checkbox question."""
        # First, check if analysis provides improved options
        improved_options = analysis.get("improved_options")
        if improved_options:
            return improved_options

        # If the original question has options, use those
        if hasattr(question, 'question_options') and question.question_options:
            return question.question_options

        # For MultipleChoice -> CheckBox conversion, use existing options
        # This is common when a question allows multiple selections but was misclassified

        # If no options can be determined, return None to trigger failure
        return None