"""Package for analyzing answer distributions by question type.

This package provides tools for analyzing and visualizing how respondents
answered individual questions across a survey. It includes:

- ByQuestionAnswers: Abstract base class for question-specific analysis
- Question type-specific analyzers (MultipleChoiceAnswers, NumericalAnswers, etc.)
- Terminal-based visualizations using termplotlib (optional dependency)
"""

from .by_question_answers import (
    ByQuestionAnswers,
    MultipleChoiceAnswers,
    CheckboxAnswers,
    NumericalAnswers,
    LinearScaleAnswers,
    FreeTextAnswers,
    YesNoAnswers,
    LikertFiveAnswers,
    RankAnswers,
    DefaultAnswers,
)

__all__ = [
    "ByQuestionAnswers",
    "MultipleChoiceAnswers",
    "CheckboxAnswers",
    "NumericalAnswers",
    "LinearScaleAnswers",
    "FreeTextAnswers",
    "YesNoAnswers",
    "LikertFiveAnswers",
    "RankAnswers",
    "DefaultAnswers",
]
