"""
Custom exceptions for the vibe system.
"""

from typing import Optional, Dict, Any


class VibeException(Exception):
    """Base exception class for vibe system errors."""

    def __init__(
        self,
        message: str,
        question_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.question_name = question_name
        self.details = details or {}


class QuestionAnalysisError(VibeException):
    """Raised when question analysis fails."""

    def __init__(
        self, question_name: str, message: str, api_error: Optional[Exception] = None
    ):
        super().__init__(
            f"Analysis failed for {question_name}: {message}", question_name
        )
        self.api_error = api_error


class ConversionError(VibeException):
    """Raised when question conversion fails."""

    def __init__(
        self, question_name: str, source_type: str, target_type: str, message: str
    ):
        super().__init__(
            f"Failed to convert {question_name} from {source_type} to {target_type}: {message}",
            question_name,
        )
        self.source_type = source_type
        self.target_type = target_type


class ValidationError(VibeException):
    """Raised when question validation fails."""

    def __init__(self, question_name: str, validation_error: str):
        super().__init__(
            f"Validation failed for {question_name}: {validation_error}", question_name
        )


class ConverterRegistrationError(VibeException):
    """Raised when converter registration fails."""

    def __init__(self, target_type: str, message: str):
        super().__init__(f"Failed to register converter for {target_type}: {message}")
        self.target_type = target_type


class ConfigurationError(VibeException):
    """Raised when configuration is invalid."""

    def __init__(self, config_field: str, message: str):
        super().__init__(f"Configuration error in {config_field}: {message}")
        self.config_field = config_field


class TimeoutError(VibeException):
    """Raised when processing times out."""

    def __init__(
        self, operation: str, timeout_seconds: int, question_name: Optional[str] = None
    ):
        message = f"{operation} timed out after {timeout_seconds} seconds"
        if question_name:
            message += f" for question {question_name}"
        super().__init__(message, question_name)
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class BatchProcessingError(VibeException):
    """Raised when batch processing encounters errors."""

    def __init__(self, batch_index: int, error_count: int, total_questions: int):
        super().__init__(
            f"Batch {batch_index} processing failed: {error_count}/{total_questions} questions had errors"
        )
        self.batch_index = batch_index
        self.error_count = error_count
        self.total_questions = total_questions
