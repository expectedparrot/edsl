"""
Numerical question converter implementation.
"""

from typing import Dict, Any, Tuple
from edsl.questions import Question, QuestionNumerical
from .base import AbstractQuestionConverter


class NumericalConverter(AbstractQuestionConverter):
    """Converts questions to QuestionNumerical format."""

    @property
    def target_type(self) -> str:
        return "QuestionNumerical"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to numerical."""
        # Check if the analysis suggests numerical type
        suggested_type = analysis.get("suggested_type")
        return suggested_type == "QuestionNumerical"

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for numerical conversion."""
        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
        }

        # Infer constraints from question text
        min_val, max_val = self._infer_numerical_constraints(question)
        if min_val is not None:
            params["min_value"] = min_val
        if max_val is not None:
            params["max_value"] = max_val

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionNumerical with extracted parameters."""
        return QuestionNumerical(**params)

    def _infer_numerical_constraints(self, question: Question) -> Tuple[float, float]:
        """Infer min/max constraints for numerical questions."""
        text = question.question_text.lower()
        min_val, max_val = None, None

        # Look for year constraints
        if "year" in text:
            if "birth" in text:
                min_val, max_val = 1900, 2024  # Birth year range
            else:
                min_val, max_val = 1900, 2100  # General year range

        # Look for percentage constraints
        elif "percentage" in text or "%" in text:
            min_val, max_val = 0, 100

        # Look for rating constraints
        elif any(word in text for word in ["rate", "rating", "scale"]):
            if "1 to 10" in text or "1-10" in text:
                min_val, max_val = 1, 10
            elif "1 to 5" in text or "1-5" in text:
                min_val, max_val = 1, 5

        # Look for count constraints (assignment, contract counts, etc.)
        elif "count" in text:
            min_val = 0  # Counts are non-negative

        return min_val, max_val
