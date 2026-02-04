"""
Custom exceptions for the vibe system.
"""

from .vibe_exceptions import (
    VibeException,
    QuestionAnalysisError,
    ConversionError,
    ValidationError,
    ConverterRegistrationError,
    ConfigurationError,
    TimeoutError,
    BatchProcessingError,
)

__all__ = [
    "VibeException",
    "QuestionAnalysisError",
    "ConversionError",
    "ValidationError",
    "ConverterRegistrationError",
    "ConfigurationError",
    "TimeoutError",
    "BatchProcessingError",
]
