"""
Unified Pydantic Schemas for EDSL Vibes System

This module consolidates all Pydantic schemas used throughout the vibes system,
providing a single source of truth for request/response formats and ensuring
consistency across handlers and remote dispatch.

All vibes handlers and the server package import schemas from this module.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Core Question and Survey Schemas
# ============================================================================


class QuestionDefinition(BaseModel):
    """
    Schema for a single question in a survey.

    This is the core schema used throughout the vibes system for representing
    individual survey questions. It consolidates the previously duplicated
    schemas from survey_generator.py, vibe_editor.py, and vibe_add_helper.py.

    Attributes
    ----------
    question_name : str
        A valid Python variable name to identify the question
    question_text : str
        The actual text of the question to be asked
    question_type : str
        The type of question (e.g., 'multiple_choice', 'free_text', 'likert_five', etc.)
    question_options : Optional[List[str]]
        List of options for choice-based questions (required for multiple_choice, checkbox, etc.)
    min_value : Optional[float]
        Minimum value for numerical questions
    max_value : Optional[float]
        Maximum value for numerical questions
    """

    question_name: str = Field(
        description="A valid Python variable name to identify the question (e.g., 'age', 'satisfaction_rating')"
    )
    question_text: str = Field(
        description="The actual text of the question to be asked"
    )
    question_type: str = Field(
        description=(
            "The type of question. Must be one of: "
            "'free_text' (open-ended text), "
            "'multiple_choice' (select one option), "
            "'checkbox' (select multiple options), "
            "'numerical' (numeric answer), "
            "'likert_five' (5-point agree/disagree scale), "
            "'linear_scale' (numeric scale with labels), "
            "'yes_no' (simple yes/no), "
            "'rank' (rank items in order), "
            "'budget' (allocate budget across options), "
            "'list' (list of items), "
            "'matrix' (grid of questions)"
        )
    )
    question_options: Optional[List[str]] = Field(
        None,
        description="List of options for choice-based questions (required for multiple_choice, checkbox, rank, budget)",
    )
    min_value: Optional[float] = Field(
        None, description="Minimum value for numerical or linear_scale questions"
    )
    max_value: Optional[float] = Field(
        None, description="Maximum value for numerical or linear_scale questions"
    )


class SkipRuleDefinition(BaseModel):
    """
    Schema for a skip rule to be applied to a question.

    Skip rules determine when a question should be hidden based on
    previous answers in the survey.

    Attributes
    ----------
    target_question : str
        The question_name of the question to apply the skip rule to
    condition : str
        The condition expression that determines if the question should be skipped
    """

    target_question: str = Field(
        description="The question_name of the question to apply the skip rule to"
    )
    condition: str = Field(
        description=(
            "The condition expression that determines if the question should be skipped. "
            "Use template syntax to reference previous questions' answers. "
            'Examples: "{{ q0.answer }} == \'yes\'", "{{ age.answer }} > 18", '
            "\"{{ satisfaction.answer }} == 'Very satisfied'\""
        )
    )


# ============================================================================
# Survey-level Schemas
# ============================================================================


class SurveySchema(BaseModel):
    """
    Schema for a complete survey definition.

    Used by the from_vibes method to represent a newly generated survey.

    Attributes
    ----------
    questions : List[QuestionDefinition]
        List of questions that make up the survey
    """

    questions: List[QuestionDefinition] = Field(
        description="List of questions in the survey"
    )


class EditedSurveySchema(BaseModel):
    """
    Schema for an edited survey definition.

    Used by the vibe_edit method to represent a survey after modifications.

    Attributes
    ----------
    questions : List[QuestionDefinition]
        List of questions that make up the edited survey
    """

    questions: List[QuestionDefinition] = Field(
        description="List of questions in the edited survey"
    )


class AddedQuestionsSchema(BaseModel):
    """
    Schema for questions to be added to a survey.

    Used by the vibe_add method to represent new questions and any
    associated skip rules to be added to an existing survey.

    Attributes
    ----------
    questions : List[QuestionDefinition]
        List of questions to add to the survey
    skip_rules : List[SkipRuleDefinition]
        List of skip rules to apply to the added questions
    """

    questions: List[QuestionDefinition] = Field(
        description="List of questions to add to the survey"
    )
    skip_rules: List[SkipRuleDefinition] = Field(
        default=[],
        description="List of skip rules to apply to the added questions (optional)",
    )


class SurveyDescriptionSchema(BaseModel):
    """
    Schema for a survey description.

    Used by the vibe_describe method to provide a title and description
    for an existing survey based on its questions.

    Attributes
    ----------
    proposed_title : str
        A single sentence title that captures the essence of the survey
    description : str
        A paragraph-length description of what the survey is about
    """

    proposed_title: str = Field(
        description="A single sentence title that captures the essence of the survey"
    )
    description: str = Field(
        description="A paragraph-length description explaining what the survey is about, its purpose, and what topics it covers"
    )


# ============================================================================
# Method-specific Request Schemas
# ============================================================================


class FromVibesRequest(BaseModel):
    """
    Request schema for Survey.from_vibes() method.

    Attributes
    ----------
    description : str
        Natural language description of the survey to generate
    num_questions : Optional[int]
        Number of questions to generate (if not provided, determined automatically)
    model : str
        OpenAI model to use for generation
    temperature : float
        Temperature for generation
    """

    description: str = Field(
        description="Natural language description of the survey to generate"
    )
    num_questions: Optional[int] = Field(
        None,
        description="Number of questions to generate (if not provided, determined automatically)",
    )
    model: str = Field(
        default="gpt-4o", description="OpenAI model to use for generation"
    )
    temperature: float = Field(default=0.7, description="Temperature for generation")


class VibeEditRequest(BaseModel):
    """
    Request schema for Survey.vibe_edit() method.

    Attributes
    ----------
    survey_dict : Dict[str, Any]
        Dictionary representation of the current survey
    edit_instructions : str
        Natural language description of the edits to apply
    model : str
        OpenAI model to use for editing
    temperature : float
        Temperature for generation
    """

    survey_dict: Dict[str, Any] = Field(
        description="Dictionary representation of the current survey"
    )
    edit_instructions: str = Field(
        description="Natural language description of the edits to apply"
    )
    model: str = Field(default="gpt-4o", description="OpenAI model to use for editing")
    temperature: float = Field(default=0.7, description="Temperature for generation")


class VibeAddRequest(BaseModel):
    """
    Request schema for Survey.vibe_add() method.

    Attributes
    ----------
    survey_dict : Dict[str, Any]
        Dictionary representation of the current survey
    add_instructions : str
        Natural language description of what questions to add
    model : str
        OpenAI model to use for generation
    temperature : float
        Temperature for generation
    """

    survey_dict: Dict[str, Any] = Field(
        description="Dictionary representation of the current survey"
    )
    add_instructions: str = Field(
        description="Natural language description of what questions to add"
    )
    model: str = Field(
        default="gpt-4o", description="OpenAI model to use for generation"
    )
    temperature: float = Field(default=0.7, description="Temperature for generation")


class VibeDescribeRequest(BaseModel):
    """
    Request schema for Survey.vibe_describe() method.

    Attributes
    ----------
    survey_dict : Dict[str, Any]
        Dictionary representation of the survey to describe
    model : str
        OpenAI model to use for generation
    temperature : float
        Temperature for generation
    """

    survey_dict: Dict[str, Any] = Field(
        description="Dictionary representation of the survey to describe"
    )
    model: str = Field(
        default="gpt-4o", description="OpenAI model to use for generation"
    )
    temperature: float = Field(default=0.7, description="Temperature for generation")


# ============================================================================
# Generic Dispatch Schemas
# ============================================================================


class VibesDispatchRequest(BaseModel):
    """
    Generic request schema for the vibes dispatch system.

    This is the main request format for the remote server's dispatch endpoint.
    It wraps any vibes method call with its target, method name, and parameters.

    Attributes
    ----------
    target : str
        Target object type (e.g., "survey", "agent", "question")
    method : str
        Method name (e.g., "from_vibes", "vibe_edit", "vibe_add", "vibe_describe")
    request_data : Dict[str, Any]
        Method-specific request parameters (validated against method's request schema)
    """

    target: str = Field(
        description="Target object type (e.g., 'survey', 'agent', 'question')"
    )
    method: str = Field(
        description="Method name (e.g., 'from_vibes', 'vibe_edit', 'vibe_add', 'vibe_describe')"
    )
    request_data: Dict[str, Any] = Field(
        description="Method-specific request parameters (validated against method's request schema)"
    )


class VibesDispatchResponse(BaseModel):
    """
    Generic response schema for the vibes dispatch system.

    This is the main response format from the remote server's dispatch endpoint.
    It wraps the result of any vibes method execution.

    Attributes
    ----------
    target : str
        Target object type that was processed
    method : str
        Method name that was executed
    success : bool
        Whether the method execution was successful
    result : Optional[Dict[str, Any]]
        Method-specific response data (validated against method's response schema)
    error : Optional[str]
        Error message if success is False
    """

    target: str = Field(description="Target object type that was processed")
    method: str = Field(description="Method name that was executed")
    success: bool = Field(description="Whether the method execution was successful")
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Method-specific response data (validated against method's response schema)",
    )
    error: Optional[str] = Field(None, description="Error message if success is False")


# ============================================================================
# Utility Functions
# ============================================================================


def get_request_schema(method: str) -> type[BaseModel]:
    """
    Get the request schema class for a specific vibes method.

    Args:
        method: Method name (e.g., "from_vibes", "vibe_edit")

    Returns:
        The appropriate request schema class

    Raises:
        ValueError: If method is not recognized
    """
    schema_map = {
        "from_vibes": FromVibesRequest,
        "vibe_edit": VibeEditRequest,
        "vibe_add": VibeAddRequest,
        "vibe_describe": VibeDescribeRequest,
    }

    if method not in schema_map:
        raise ValueError(
            f"Unknown vibes method: {method}. Available methods: {list(schema_map.keys())}"
        )

    return schema_map[method]


def get_response_schema(method: str) -> type[BaseModel]:
    """
    Get the response schema class for a specific vibes method.

    Args:
        method: Method name (e.g., "from_vibes", "vibe_edit")

    Returns:
        The appropriate response schema class

    Raises:
        ValueError: If method is not recognized
    """
    schema_map = {
        "from_vibes": SurveySchema,
        "vibe_edit": EditedSurveySchema,
        "vibe_add": AddedQuestionsSchema,
        "vibe_describe": SurveyDescriptionSchema,
    }

    if method not in schema_map:
        raise ValueError(
            f"Unknown vibes method: {method}. Available methods: {list(schema_map.keys())}"
        )

    return schema_map[method]


def validate_dispatch_request(request: Dict[str, Any]) -> VibesDispatchRequest:
    """
    Validate a generic dispatch request.

    Args:
        request: Raw request dictionary

    Returns:
        Validated VibesDispatchRequest object

    Raises:
        ValidationError: If request format is invalid
    """
    return VibesDispatchRequest(**request)


def validate_method_request(
    target: str, method: str, request_data: Dict[str, Any]
) -> BaseModel:
    """
    Validate method-specific request data.

    Args:
        target: Target object type
        method: Method name
        request_data: Method-specific request parameters

    Returns:
        Validated request object for the specific method

    Raises:
        ValueError: If target/method combination is invalid
        ValidationError: If request data doesn't match schema
    """
    if target != "survey":
        raise ValueError(
            f"Unsupported target: {target}. Currently only 'survey' is supported."
        )

    request_schema = get_request_schema(method)
    return request_schema(**request_data)


# ============================================================================
# Schema Export for Backward Compatibility
# ============================================================================

# Export all schemas for easy importing by other modules
__all__ = [
    # Core schemas
    "QuestionDefinition",
    "SkipRuleDefinition",
    # Survey schemas
    "SurveySchema",
    "EditedSurveySchema",
    "AddedQuestionsSchema",
    "SurveyDescriptionSchema",
    # Request schemas
    "FromVibesRequest",
    "VibeEditRequest",
    "VibeAddRequest",
    "VibeDescribeRequest",
    # Dispatch schemas
    "VibesDispatchRequest",
    "VibesDispatchResponse",
    # Utility functions
    "get_request_schema",
    "get_response_schema",
    "validate_dispatch_request",
    "validate_method_request",
]


if __name__ == "__main__":
    # Example usage and testing
    print("EDSL Vibes Schemas")
    print("=" * 50)

    # Test creating a sample question
    question = QuestionDefinition(
        question_name="satisfaction",
        question_text="How satisfied are you with our product?",
        question_type="multiple_choice",
        question_options=[
            "Very satisfied",
            "Satisfied",
            "Neutral",
            "Dissatisfied",
            "Very dissatisfied",
        ],
    )
    print(f"Sample question: {question.question_name} - {question.question_text}")

    # Test from_vibes request
    from_vibes_req = FromVibesRequest(
        description="Survey about customer satisfaction with a new product",
        num_questions=5,
        model="gpt-4o",
        temperature=0.7,
    )
    print(f"From vibes request: {from_vibes_req.description}")

    # Test dispatch request
    dispatch_req = VibesDispatchRequest(
        target="survey", method="from_vibes", request_data=from_vibes_req.model_dump()
    )
    print(f"Dispatch request: {dispatch_req.target}.{dispatch_req.method}")

    # Test schema retrieval
    try:
        req_schema = get_request_schema("from_vibes")
        resp_schema = get_response_schema("from_vibes")
        print(f"Schema mapping works: {req_schema.__name__} -> {resp_schema.__name__}")
    except Exception as e:
        print(f"Schema error: {e}")
