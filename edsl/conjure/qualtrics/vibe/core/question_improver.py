"""
Question improvement coordinator that orchestrates analysis and conversion.
"""

from typing import Dict, Any, Optional, List
from edsl.questions import Question
from ..config import VibeChange, VibeConfig
from ..analysis import QuestionAnalyzer
from ..converters import convert_question
from ..logging import VibeLogger
from .change_tracker import ChangeTracker


class QuestionImprover:
    """
    Coordinates the improvement of individual questions.

    This class orchestrates the analysis and conversion pipeline for a single question.
    """

    def __init__(
        self,
        config: VibeConfig,
        analyzer: QuestionAnalyzer,
        change_tracker: ChangeTracker,
        logger: Optional[VibeLogger] = None,
    ):
        self.config = config
        self.analyzer = analyzer
        self.change_tracker = change_tracker
        self.logger = logger
        self.response_data: Optional[Dict[str, List[str]]] = None

    def set_response_data(self, response_data: Dict[str, List[str]]) -> None:
        """Set response data for use in question analysis."""
        self.response_data = response_data

    async def improve_question(self, question: Question) -> Question:
        """
        Improve a single question through analysis and conversion.

        Args:
            question: Question to improve

        Returns:
            Improved question (or original if no improvements made)
        """
        try:
            # Get AI analysis of the question with response data
            analysis = await self.analyzer.analyze_question(
                question, self.response_data
            )

            # Apply improvements based on analysis
            improved_question = self._apply_improvements(question, analysis)

            return improved_question

        except Exception as e:
            if self.logger:
                print(f"Error processing question {question.question_name}: {e}")
            return question  # Return original on error

    def _apply_improvements(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Question:
        """
        Apply improvements to a question based on analysis results.

        Args:
            question: Original question
            analysis: Analysis results from AI

        Returns:
            Improved question
        """
        changes_made = []

        # Apply text improvements
        improved_question = self._apply_text_improvements(
            question, analysis, changes_made
        )

        # Apply option improvements
        improved_question = self._apply_option_improvements(
            improved_question, analysis, changes_made
        )

        # Apply type conversions (if needed)
        final_question = self._apply_type_conversion(
            improved_question, analysis, changes_made
        )

        # Record all changes
        for change in changes_made:
            self.change_tracker.record_change(change)

        # Log results
        if self.logger:
            had_changes = len(changes_made) > 0
            self.logger.log_question_result(question.question_name, had_changes)

        return final_question

    def _apply_text_improvements(
        self, question: Question, analysis: Dict[str, Any], changes_made: list
    ) -> Question:
        """Apply text improvements if suggested."""
        improved_text = analysis.get("improved_text")
        if improved_text and improved_text != question.question_text:
            # Create change record
            change = VibeChange(
                question_name=question.question_name,
                change_type="text",
                original_value=question.question_text,
                new_value=improved_text,
                reasoning=analysis.get("reasoning", "Text improvement"),
                confidence=analysis.get("confidence", 0.5),
            )
            changes_made.append(change)

            if self.logger and self.config.enable_logging:
                print("    🔧 Text: Removed conversion artifacts")

            # Create new question with improved text
            question_dict = question.to_dict()
            question_dict["question_text"] = improved_text

            # Filter out invalid parameters
            clean_dict = {
                k: v
                for k, v in question_dict.items()
                if k
                not in [
                    "question_type",
                    "response_validator_class",
                    "edsl_version",
                    "edsl_class_name",
                ]
            }

            try:
                return question.__class__(**clean_dict)
            except Exception:
                return question  # Return original if recreation fails

        return question

    def _apply_option_improvements(
        self, question: Question, analysis: Dict[str, Any], changes_made: list
    ) -> Question:
        """Apply option improvements if suggested."""
        improved_options = analysis.get("improved_options")
        if (
            improved_options
            and hasattr(question, "question_options")
            and improved_options != question.question_options
        ):

            # Create change record
            change = VibeChange(
                question_name=question.question_name,
                change_type="options",
                original_value=question.question_options,
                new_value=improved_options,
                reasoning=analysis.get("reasoning", "Option improvement"),
                confidence=analysis.get("confidence", 0.5),
            )
            changes_made.append(change)

            if self.logger and self.config.enable_logging:
                print("    ⚙️ Options: Fixed corrupted choice list")

            # Create new question with improved options
            question_dict = question.to_dict()
            question_dict["question_options"] = improved_options

            # Filter out invalid parameters
            clean_dict = {
                k: v
                for k, v in question_dict.items()
                if k
                not in [
                    "question_type",
                    "response_validator_class",
                    "edsl_version",
                    "edsl_class_name",
                ]
            }

            try:
                return question.__class__(**clean_dict)
            except Exception:
                return question  # Return original if recreation fails

        return question

    def _apply_type_conversion(
        self, question: Question, analysis: Dict[str, Any], changes_made: list
    ) -> Question:
        """Apply type conversion if suggested and supported."""
        suggested_type = analysis.get("suggested_type")
        if suggested_type and suggested_type != question.__class__.__name__:

            # Attempt conversion using converter registry
            conversion_result = convert_question(question, suggested_type, analysis)

            if conversion_result.success:
                # Log successful conversion
                change = VibeChange(
                    question_name=question.question_name,
                    change_type="type",
                    original_value=question.__class__.__name__,
                    new_value=suggested_type,
                    reasoning=analysis.get("reasoning", "Type conversion"),
                    confidence=analysis.get("confidence", 0.5),
                )
                changes_made.append(change)

                if self.logger and self.config.enable_logging:
                    print(
                        f"    🔄 Type: {question.__class__.__name__} → {suggested_type} (converted)"
                    )

                return conversion_result.question
            else:
                # Log failed conversion with detailed error
                if self.logger and self.config.enable_logging:
                    error_detail = conversion_result.error or "Unknown error"
                    print(
                        f"    💡 Type: {question.__class__.__name__} → {suggested_type} (suggested - conversion failed)"
                    )
                    print(f"      ❌ Reason: {error_detail}")

        return question
