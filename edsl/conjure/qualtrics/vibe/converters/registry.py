"""
Converter registry for managing question type converters.
"""

from typing import Dict, Optional
from .base import AbstractQuestionConverter, ConversionResult
from edsl.questions import Question


class ConverterRegistry:
    """
    Registry for managing question type converters.

    Uses Strategy pattern to allow dynamic converter selection.
    """

    def __init__(self):
        self._converters: Dict[str, AbstractQuestionConverter] = {}

    def register(self, target_type: str, converter: AbstractQuestionConverter) -> None:
        """Register a converter for a specific question type."""
        self._converters[target_type] = converter

    def unregister(self, target_type: str) -> None:
        """Unregister a converter."""
        self._converters.pop(target_type, None)

    def get_converter(self, target_type: str) -> Optional[AbstractQuestionConverter]:
        """Get a converter for the specified target type."""
        return self._converters.get(target_type)

    def has_converter(self, target_type: str) -> bool:
        """Check if a converter is registered for the target type."""
        return target_type in self._converters

    def convert(
        self, question: Question, target_type: str, analysis: dict
    ) -> ConversionResult:
        """
        Convert a question using the appropriate converter.

        Args:
            question: Question to convert
            target_type: Target question type
            analysis: Analysis results from AI

        Returns:
            ConversionResult with success/failure and converted question
        """
        converter = self.get_converter(target_type)
        if not converter:
            return ConversionResult(
                success=False, error=f"No converter registered for {target_type}"
            )

        return converter.convert(question, analysis)

    def get_supported_types(self) -> list[str]:
        """Get list of supported conversion target types."""
        return list(self._converters.keys())

    def clear(self) -> None:
        """Clear all registered converters."""
        self._converters.clear()


# Global registry instance
_default_registry = ConverterRegistry()


def get_default_registry() -> ConverterRegistry:
    """Get the default global converter registry."""
    return _default_registry


def register_converter(target_type: str, converter: AbstractQuestionConverter) -> None:
    """Register a converter in the default registry."""
    _default_registry.register(target_type, converter)


def convert_question(
    question: Question, target_type: str, analysis: dict
) -> ConversionResult:
    """Convert a question using the default registry."""
    return _default_registry.convert(question, target_type, analysis)
