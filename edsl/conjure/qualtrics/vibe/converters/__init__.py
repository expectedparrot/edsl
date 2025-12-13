"""
Question converter system using Strategy and Template Method patterns.

This module provides a pluggable converter system where new question type
converters can be easily added without modifying existing code.
"""

from .base import AbstractQuestionConverter, ConversionResult
from .registry import (
    ConverterRegistry,
    get_default_registry,
    register_converter,
    convert_question,
)
from .numerical import NumericalConverter
from .linear_scale import LinearScaleConverter
from .yes_no import YesNoConverter
from .multiple_choice_with_other import MultipleChoiceWithOtherConverter
from .multiple_choice import MultipleChoiceConverter
from .matrix_entry import MatrixEntryConverter
from .matrix import MatrixConverter
from .checkbox import CheckBoxConverter


# Auto-register converters in the default registry
def _register_default_converters():
    """Register all built-in converters with the default registry."""
    registry = get_default_registry()

    # Register built-in converters
    registry.register("QuestionNumerical", NumericalConverter())
    registry.register("QuestionLinearScale", LinearScaleConverter())
    registry.register("QuestionYesNo", YesNoConverter())
    registry.register("QuestionMultipleChoiceWithOther", MultipleChoiceWithOtherConverter())
    registry.register("QuestionMultipleChoice", MultipleChoiceConverter())
    registry.register("QuestionMatrixEntry", MatrixEntryConverter())
    registry.register("QuestionMatrix", MatrixConverter())
    registry.register("QuestionCheckBox", CheckBoxConverter())

    # TODO: Add other converters as they are implemented
    # registry.register('QuestionLikertFive', LikertFiveConverter())


# Initialize default converters on module import
_register_default_converters()

__all__ = [
    "AbstractQuestionConverter",
    "ConversionResult",
    "ConverterRegistry",
    "get_default_registry",
    "register_converter",
    "convert_question",
    "NumericalConverter",
    "LinearScaleConverter",
    "YesNoConverter",
    "MultipleChoiceWithOtherConverter",
    "MultipleChoiceConverter",
    "MatrixEntryConverter",
    "MatrixConverter",
    "CheckBoxConverter",
]
