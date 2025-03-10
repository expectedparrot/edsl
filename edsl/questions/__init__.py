"""
EDSL Questions Module: The core system for creating and processing questions.

The questions module provides a comprehensive framework for creating, validating,
and processing various types of questions that can be asked to language models.
It is one of the foundational components of EDSL and enables the creation of 
surveys, interviews, and other question-based interactions.

Key features:
- A wide variety of question types including free text, multiple choice, checkbox, etc.
- Consistent interface for asking questions to language models
- Robust validation of responses
- Support for question templates and parameterization with scenarios
- Integration with the rest of the EDSL framework

The module is organized around the QuestionBase abstract base class, which defines
the core interface all question types must implement. Specific question types are
implemented as subclasses of QuestionBase, each with its own response format and
validation rules.

Example usage:
    >>> from edsl import QuestionFreeText
    >>> question = QuestionFreeText(
    ...     question_name="greeting",
    ...     question_text="Say hello to the user."
    ... )
    >>> from edsl.language_models import Model
    >>> model = Model()
    >>> result = question.by(model).run()
    >>> answer = result.first().answer.greeting
    >>> isinstance(answer, str)
    True
"""

# Schemas and metadata
from .settings import Settings
from .register_questions_meta import RegisterQuestionsMeta

# Base Class and registry
from .question_base import QuestionBase
from .question_registry import Question

# Core Questions
from .question_check_box import QuestionCheckBox
from .question_extract import QuestionExtract
from .question_free_text import QuestionFreeText
from .question_functional import QuestionFunctional
from .question_list import QuestionList
from .question_matrix import QuestionMatrix
from .question_dict import QuestionDict
from .question_multiple_choice import QuestionMultipleChoice
from .question_numerical import QuestionNumerical
from .question_budget import QuestionBudget
from .question_rank import QuestionRank

# Questions derived from core questions
from .derived.question_likert_five import QuestionLikertFive
from .derived.question_linear_scale import QuestionLinearScale
from .derived.question_yes_no import QuestionYesNo
from .derived.question_top_k import QuestionTopK

from .exceptions import QuestionScenarioRenderError

__all__ = [
    # Schema and metadata
    "Settings",
    "RegisterQuestionsMeta",
    
    # Base question class and registry
    "QuestionBase",
    "Question",
    
    # Core question types
    "QuestionFreeText",
    "QuestionMultipleChoice",
    "QuestionCheckBox",
    "QuestionDict",
    "QuestionExtract",
    "QuestionFunctional",
    "QuestionList",
    "QuestionMatrix",
    "QuestionNumerical",
    "QuestionBudget",
    "QuestionRank",
    
    # Derived question types
    "QuestionLinearScale",
    "QuestionTopK",
    "QuestionLikertFive",
    "QuestionYesNo",
]
