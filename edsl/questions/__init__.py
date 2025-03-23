"""
EDSL Questions Module: The core system for creating and processing questions.

The questions module provides a comprehensive framework for creating, validating,
and processing various types of questions that can be asked to language models.
It is one of the foundational components of EDSL and enables the creation of 
surveys, interviews, and other question-based interactions.

Key Features:
-------------
- A wide variety of question types including free text, multiple choice, checkbox, etc.
- Consistent interface for asking questions to language models
- Robust validation of responses
- Support for question templates and parameterization with scenarios
- Integration with the rest of the EDSL framework
- Extensible architecture for creating custom question types

Question Types:
--------------
Core Question Types:
- QuestionFreeText: Free-form text responses without constraints
- QuestionMultipleChoice: Selection from a predefined list of options
- QuestionCheckBox: Selection of multiple options from a predefined list
- QuestionNumerical: Numeric responses within an optional range
- QuestionList: Responses in the form of lists or arrays
- QuestionDict: Responses with key-value pairs
- QuestionMatrix: Grid-based responses with rows and columns
- QuestionBudget: Allocation of a budget across multiple options
- QuestionRank: Ordering of items by preference or other criteria
- QuestionExtract: Extraction of specific information from text or data

Derived Question Types:
- QuestionLikertFive: Standard 5-point Likert scale (agree/disagree)
- QuestionLinearScale: Linear scale with customizable range and labels
- QuestionYesNo: Simple binary yes/no response
- QuestionTopK: Selection of top K items from a list of options

Technical Architecture:
---------------------
1. Base Classes and Mixins:
   - QuestionBase: Abstract base class for all question types
   - SimpleAskMixin: Basic asking functionality to models and agents
   - AnswerValidatorMixin: Validation of responses
   - QuestionBasePromptsMixin: Template-based prompt generation
   - QuestionBaseGenMixin: Integration with language models
   
2. Validation System:
   - Response validators ensure answers conform to expected formats
   - Pydantic models provide schema validation
   - Repair functionality attempts to fix invalid responses
   
3. Template System:
   - Jinja2 templates for consistent prompt generation
   - Separate templates for answering instructions and question presentation
   - Support for dynamic content through scenario variables

4. Registry System:
   - RegisterQuestionsMeta metaclass for automatic registration
   - Question types are automatically available for serialization
   - Registry enables runtime lookup of question types

Example Usage:
-------------
    >>> from edsl import QuestionFreeText
    >>> question = QuestionFreeText(
    ...     question_name="greeting",
    ...     question_text="Say hello to the user."
    ... )
    >>> from edsl.language_models import Model
    >>> model = Model()
    >>> # result = question.by(model).run()
    
    >>> from edsl import QuestionMultipleChoice
    >>> choice_q = QuestionMultipleChoice(
    ...     question_name="preference",
    ...     question_text="Which color do you prefer?",
    ...     question_options=["Red", "Blue", "Green", "Yellow"]
    ... )
    >>> # result = choice_q.by(model).run()

Integration with Surveys:
-----------------------
Questions can be combined into surveys for more complex interactions:

    # Note: Actual survey usage in code
    # from edsl import Survey
    # survey = Survey()
    # survey.add_question(question)
    # survey.add_question(choice_q)
    # results = survey.by(model).run()

Extension Points:
---------------
The questions module is designed to be extensible:
- Create custom question types by subclassing QuestionBase
- Implement custom validators for specialized validation
- Define custom templates for unique presentation needs
- Combine questions in surveys with custom flow logic
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
from .question_likert_five import QuestionLikertFive
from .question_linear_scale import QuestionLinearScale
from .question_yes_no import QuestionYesNo
from .question_top_k import QuestionTopK

from .exceptions import QuestionScenarioRenderError

__all__ = [
    # Exceptions
    "QuestionScenarioRenderError",
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
