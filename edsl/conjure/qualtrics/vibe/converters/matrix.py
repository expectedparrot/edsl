"""
QuestionMatrix converter implementation.
"""

from typing import Dict, Any
from edsl.questions import Question, QuestionMatrix
from .base import AbstractQuestionConverter


class MatrixConverter(AbstractQuestionConverter):
    """Converts questions to QuestionMatrix format."""

    @property
    def target_type(self) -> str:
        return "QuestionMatrix"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to matrix."""
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionMatrix"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for matrix conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }

        # Extract matrix structure from the original question
        if hasattr(question, "question_items"):
            params["question_items"] = question.question_items
        else:
            # For MatrixEntry -> Matrix conversion, use existing items
            if hasattr(question, "question_columns"):
                # For MatrixEntry, columns become the new items
                params["question_items"] = question.question_columns[
                    :2
                ]  # Limit to reasonable size
            else:
                params["question_items"] = ["Item 1", "Item 2"]

        if hasattr(question, "question_options"):
            params["question_options"] = question.question_options
        elif hasattr(question, "question_columns"):
            # For MatrixEntry -> Matrix, preserve the meaningful column labels as options
            params["question_options"] = question.question_columns
        else:
            # Only use generic fallback as absolute last resort and warn about it
            print(
                f"❌ WARNING: Using generic options for {question.question_name} - no options or columns available"
            )
            params["question_options"] = ["Yes", "No", "Maybe"]

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionMatrix with extracted parameters."""
        return QuestionMatrix(**params)
