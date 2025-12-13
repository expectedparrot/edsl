"""
Linear scale question converter implementation.
"""

import re
from typing import Dict, Any, List, Optional
from edsl.questions import Question, QuestionLinearScale
from .base import AbstractQuestionConverter


class LinearScaleConverter(AbstractQuestionConverter):
    """Converts questions to QuestionLinearScale format."""

    @property
    def target_type(self) -> str:
        return "QuestionLinearScale"

    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Check if question should be converted to linear scale."""
        suggested_type = analysis.get("suggested_type")
        return (
            suggested_type == "QuestionLinearScale"
            and hasattr(question, "question_options")
            and question.question_options
        )

    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for linear scale conversion."""
        options = question.question_options

        # Extract numeric scale and labels
        numeric_options, option_labels = self._parse_scale_options(options)

        params = {
            "question_name": question.question_name,
            "question_text": question.question_text,
            "question_options": numeric_options,
        }

        # Only include option_labels if we have labels for all endpoints (min and max)
        if option_labels and self._has_complete_endpoint_labels(
            numeric_options, option_labels
        ):
            params["option_labels"] = option_labels

        return params

    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Create QuestionLinearScale with extracted parameters."""
        return QuestionLinearScale(**params)

    def _parse_scale_options(
        self, options: List[str]
    ) -> tuple[List[int], Dict[int, str]]:
        """
        Parse scale options to extract numeric values and labels.

        Returns:
            Tuple of (numeric_options, option_labels)
        """
        numeric_options = []
        option_labels = {}

        for option in options:
            option_str = str(option).strip()

            # Try to extract number and optional label
            match = re.match(
                r"^(.+?)\s*[-–—]\s*(\d+)$|^(\d+)\s*[-–—]\s*(.+)$|^(\d+)$", option_str
            )

            if match:
                if match.group(5):  # Pure number: "5"
                    num = int(match.group(5))
                elif match.group(1) and match.group(2):  # "Label - 5"
                    label, num = match.group(1).strip(), int(match.group(2))
                    option_labels[num] = label
                elif match.group(3) and match.group(4):  # "5 - Label"
                    num, label = int(match.group(3)), match.group(4).strip()
                    option_labels[num] = label
                else:
                    continue

                numeric_options.append(num)

        # Sort numeric options and create complete sequence if needed
        if numeric_options:
            numeric_options.sort()
            min_val, max_val = min(numeric_options), max(numeric_options)
            # Create complete sequence from min to max
            numeric_options = list(range(min_val, max_val + 1))

        return numeric_options, option_labels

    def _has_complete_endpoint_labels(
        self, numeric_options: List[int], option_labels: Dict[int, str]
    ) -> bool:
        """Check if we have labels for both endpoints of the scale."""
        if not numeric_options or not option_labels:
            return False

        min_val, max_val = min(numeric_options), max(numeric_options)
        return min_val in option_labels and max_val in option_labels

    def _validate_converted_question(self, question: Question) -> bool:
        """Validate the converted LinearScale question."""
        if not super()._validate_converted_question(question):
            return False

        # Ensure question_options is a list of integers
        if not hasattr(question, "question_options"):
            return False

        options = question.question_options
        return (
            isinstance(options, list)
            and len(options) > 1
            and all(isinstance(opt, int) for opt in options)
        )
