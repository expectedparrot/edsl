"""
QuestionMultipleChoice converter implementation.
"""

from typing import Dict, Any
from edsl.questions import Question, QuestionMultipleChoice
from .base import AbstractQuestionConverter


class MultipleChoiceConverter(AbstractQuestionConverter):
    """Converts questions to QuestionMultipleChoice format."""

    @property
    def target_type(self) -> str:
        return "QuestionMultipleChoice"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to multiple choice."""
        # Check if the analysis suggests multiple choice type
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionMultipleChoice"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for multiple choice conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }

        # Try to extract options from various sources
        options = self._determine_options(question, analysis)
        if options:
            params["question_options"] = options
        else:
            # This conversion should probably fail if we can't determine options
            raise ValueError(
                f"Cannot convert {question.question_name} to MultipleChoice: no options available"
            )

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionMultipleChoice with extracted parameters."""
        return QuestionMultipleChoice(**params)

    def _determine_options(self, question: Question, analysis: Dict[str, Any]) -> list:
        """Determine the best options for the multiple choice question."""
        # First, check if analysis provides improved options
        improved_options = analysis.get("improved_options")
        if improved_options:
            return improved_options

        # If the original question has options, use those
        if hasattr(question, "question_options") and question.question_options:
            return question.question_options

        # For QuestionMatrix conversion, extract from matrix structure
        if hasattr(question, "question_items") and hasattr(
            question, "question_options"
        ):
            # For matrix questions, we might want to flatten the structure
            # But this is complex - for now, use the column options
            if question.question_options:
                return question.question_options

        # If no options can be determined, return None to trigger failure
        return None
