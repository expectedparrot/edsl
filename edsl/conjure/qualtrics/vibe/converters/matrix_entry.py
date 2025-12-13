"""
QuestionMatrixEntry converter implementation.
"""

from typing import Dict, Any
from edsl.questions import Question, QuestionMatrixEntry
from .base import AbstractQuestionConverter


class MatrixEntryConverter(AbstractQuestionConverter):
    """Converts questions to QuestionMatrixEntry format."""

    @property
    def target_type(self) -> str:
        return "QuestionMatrixEntry"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to matrix entry."""
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionMatrixEntry"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for matrix entry conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }

        # Extract matrix structure from the original question
        if hasattr(question, 'question_items'):
            params["question_items"] = question.question_items
        else:
            # Fallback for non-matrix questions
            params["question_items"] = ["Item 1", "Item 2"]

        if hasattr(question, 'question_columns'):
            params["question_columns"] = question.question_columns
        elif hasattr(question, 'question_options'):
            params["question_columns"] = question.question_options
        else:
            # Only use generic fallback as absolute last resort and warn about it
            print(f"❌ WARNING: Using generic columns for {question.question_name} - no columns or options available")
            params["question_columns"] = ["Column 1", "Column 2", "Column 3"]

        # Set default rating scale
        params["min_value"] = 1
        params["max_value"] = 7

        # Try to infer rating scale from analysis or question context
        if "1-10" in question.question_text or "1 to 10" in question.question_text:
            params["max_value"] = 10
        elif "1-5" in question.question_text or "1 to 5" in question.question_text:
            params["max_value"] = 5

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionMatrixEntry with extracted parameters."""
        return QuestionMatrixEntry(**params)