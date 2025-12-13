"""
Base classes for question converters using Template Method pattern.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from edsl.questions import Question


class ConversionResult:
    """Result of a question conversion attempt."""

    def __init__(
        self,
        success: bool,
        question: Optional[Question] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.success = success
        self.question = question
        self.error = error
        self.metadata = metadata or {}


class AbstractQuestionConverter(ABC):
    """
    Abstract base class for question converters.

    Uses Template Method pattern to ensure consistent logging and error handling
    while allowing subclasses to implement specific conversion logic.
    """

    def __init__(self, logger=None):
        self.logger = logger

    def convert(self, question: Question, analysis: Dict[str, Any]) -> ConversionResult:
        """
        Template method for converting questions.

        This method defines the conversion workflow and delegates specific
        conversion logic to subclasses.
        """
        self._log_conversion_start(question)

        try:
            # Validate that conversion is appropriate
            if not self._should_convert(question, analysis):
                return ConversionResult(
                    success=False,
                    error=f"Conversion to {self.target_type} not appropriate for this question",
                )

            # Extract conversion parameters
            params = self._extract_conversion_params(question, analysis)
            self._log_conversion_params(params)

            # Perform the actual conversion
            converted_question = self._perform_conversion(question, params)

            # Validate the result
            if not self._validate_converted_question(converted_question):
                return ConversionResult(
                    success=False,
                    error=f"Validation failed for converted {self.target_type}",
                )

            self._log_conversion_success(converted_question)
            return ConversionResult(
                success=True, question=converted_question, metadata={"params": params}
            )

        except Exception as e:
            error_msg = f"{self.target_type} conversion failed: {str(e)}"
            self._log_conversion_error(error_msg)
            return ConversionResult(success=False, error=error_msg)

    @property
    @abstractmethod
    def target_type(self) -> str:
        """Return the target question type name (e.g., 'QuestionNumerical')."""
        pass

    @abstractmethod
    def _should_convert(self, question: Question, analysis: Dict[str, Any]) -> bool:
        """Determine if this question should be converted to the target type."""
        pass

    @abstractmethod
    def _extract_conversion_params(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters needed for conversion from question and analysis."""
        pass

    @abstractmethod
    def _perform_conversion(
        self, question: Question, params: Dict[str, Any]
    ) -> Question:
        """Perform the actual conversion logic."""
        pass

    def _validate_converted_question(self, question: Question) -> bool:
        """Validate the converted question. Override for custom validation."""
        return question is not None

    # Logging methods (can be overridden for custom logging)
    def _log_conversion_start(self, question: Question) -> None:
        if self.logger:
            self.logger.log_conversion_start(question.question_name, self.target_type)

    def _log_conversion_params(self, params: Dict[str, Any]) -> None:
        if self.logger:
            self.logger.log_conversion_params(self.target_type, params)

    def _log_conversion_success(self, question: Question) -> None:
        if self.logger:
            self.logger.log_conversion_success(self.target_type)

    def _log_conversion_error(self, error_msg: str) -> None:
        if self.logger:
            self.logger.log_conversion_error(self.target_type, error_msg)
