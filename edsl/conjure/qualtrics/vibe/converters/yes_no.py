"""
QuestionYesNo converter implementation.
"""

from typing import Dict, Any
from edsl.questions import Question, QuestionYesNo
from .base import AbstractQuestionConverter


class YesNoConverter(AbstractQuestionConverter):
    """Converts questions to QuestionYesNo format."""

    @property
    def target_type(self) -> str:
        return "QuestionYesNo"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to yes/no."""
        # Check if the analysis suggests yes/no type
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionYesNo"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for yes/no conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }
        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionYesNo with extracted parameters."""
        return QuestionYesNo(**params)
