"""
QuestionMultipleChoiceWithOther converter implementation.
"""

from typing import Dict, Any
from edsl.questions import Question, QuestionMultipleChoiceWithOther
from .base import AbstractQuestionConverter


class MultipleChoiceWithOtherConverter(AbstractQuestionConverter):
    """Converts questions to QuestionMultipleChoiceWithOther format."""

    @property
    def target_type(self) -> str:
        return "QuestionMultipleChoiceWithOther"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to multiple choice with other."""
        # Check if the analysis suggests multiple choice with other type
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionMultipleChoiceWithOther"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for multiple choice with other conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }

        # Extract options from the original question if it has them
        if hasattr(question, 'question_options') and question.question_options:
            # Use existing options, but remove any existing "Other" options
            # since QuestionMultipleChoiceWithOther adds its own
            options = [opt for opt in question.question_options if 'other' not in opt.lower()]
            params["question_options"] = options
        else:
            # For questions without options (like FreeText), we need to infer options from response data
            # This is common for "Other (specify)" fields that should become MultipleChoiceWithOther
            improved_options = analysis.get("improved_options")
            if improved_options:
                params["question_options"] = improved_options
            else:
                # Try to extract options from the question context or fail the conversion
                # The AI should have provided improved_options based on response data analysis
                raise ValueError(f"Cannot convert {question.question_name} to MultipleChoiceWithOther: no options available from analysis. The AI should analyze response data to suggest options.")

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionMultipleChoiceWithOther with extracted parameters."""
        return QuestionMultipleChoiceWithOther(**params)