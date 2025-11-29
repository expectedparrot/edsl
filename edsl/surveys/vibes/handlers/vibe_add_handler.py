"""
VibeAdd Handler Registration

Registers the Survey.vibe_add() method with the vibes registry system.
This handler enables both local and remote execution of adding new questions
to surveys using natural language instructions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..vibes_handler_base import VibesHandlerBase
from ..vibe_add_helper import VibeAdd
from ..schemas import VibeAddRequest, AddedQuestionsSchema
from ..vibe_add_handler import add_questions_with_vibes

if TYPE_CHECKING:
    from ...survey import Survey


class VibeAddHandler(VibesHandlerBase):
    """
    Handler registration for Survey.vibe_add() method.

    This class registers the vibe_add functionality with the vibes registry,
    enabling it to be called through the generic dispatch system and potentially
    executed remotely through the server package.

    Attributes
    ----------
    vibes_target : str
        Target object type ("survey")
    vibes_method : str
        Method name ("vibe_add")
    handler_class : type
        Handler class (VibeAdd)
    handler_function : callable
        Handler function (add_questions_with_vibes)
    request_schema : type
        Pydantic request schema (VibeAddRequest)
    response_schema : type
        Pydantic response schema (AddedQuestionsSchema)
    is_classmethod : bool
        False (vibe_add is an instance method)
    """

    # Registry configuration
    vibes_target = "survey"
    vibes_method = "vibe_add"
    handler_class = VibeAdd
    handler_function = add_questions_with_vibes
    request_schema = VibeAddRequest
    response_schema = AddedQuestionsSchema
    is_classmethod = False
    metadata = {
        "description": "Add new questions to an existing survey using natural language instructions",
        "supports_remote": True,
        "supports_local": True,
    }

    @classmethod
    def execute_local(
        cls,
        survey: "Survey",
        add_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        **kwargs
    ) -> "Survey":
        """
        Execute the vibe_add method locally.

        This method calls the existing add_questions_with_vibes function
        with the provided arguments and returns the result.

        Args:
            survey: The Survey instance to add questions to
            add_instructions: Natural language description of what to add
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            Survey: A new Survey instance with the original questions plus the new ones

        Raises:
            Various exceptions from add_questions_with_vibes function
        """
        return cls.handler_function(
            survey=survey,
            add_instructions=add_instructions,
            model=model,
            temperature=temperature,
        )

    @classmethod
    def to_remote_request(
        cls,
        survey: "Survey",
        add_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        **kwargs
    ) -> dict[str, Any]:
        """
        Convert local method arguments to remote request format.

        For vibe_add, we need to serialize the survey to a dictionary
        format that can be sent to the remote server.

        Args:
            survey: The Survey instance to add questions to
            add_instructions: Natural language description of what to add
            model: OpenAI model to use for generation
            temperature: Temperature for generation
            **kwargs: Additional arguments (ignored)

        Returns:
            dict: Validated request data for remote execution
        """
        # Convert survey to dictionary format
        survey_dict = survey.to_dict()

        # Create and validate the request using the schema
        request_obj = cls.request_schema(
            survey_dict=survey_dict,
            add_instructions=add_instructions,
            model=model,
            temperature=temperature
        )

        return request_obj.model_dump()

    @classmethod
    def from_remote_response(
        cls,
        response_data: dict[str, Any],
        survey: "Survey" = None,
    ) -> Any:
        """
        Convert remote response data to local return format.

        For vibe_add, the remote response contains new questions and skip rules
        that need to be added to the original survey to create a new Survey instance.

        Args:
            response_data: Raw response data from remote server
            survey: Original survey instance (used to get existing questions and survey class)

        Returns:
            Survey: A new Survey instance with the original questions plus the new ones

        Raises:
            ValidationError: If response doesn't match response schema
            ValueError: If survey is not provided
        """
        if survey is None:
            raise ValueError("survey is required to construct Survey from remote response")

        # Validate response using response schema
        response_obj = cls.response_schema(**response_data)

        # Convert new questions to question objects
        # (This matches the logic from add_questions_with_vibes)
        new_questions = []
        base_index = len(survey.questions)
        for i, q_data in enumerate(response_obj.questions):
            question_dict = q_data.model_dump()
            question_obj = survey._create_question_from_dict(question_dict, f"q{base_index + i}")
            new_questions.append(question_obj)

        # Create new survey with all questions AND preserve existing rule_collection
        all_questions = list(survey.questions) + new_questions
        new_survey = survey.__class__(
            questions=all_questions,
            rule_collection=survey.rule_collection,  # Preserves existing skip logic!
        )

        # Add skip logic for newly added questions if specified
        for skip_rule in response_obj.skip_rules:
            target_question = skip_rule.target_question
            condition = skip_rule.condition
            new_survey = new_survey.add_skip_rule(target_question, condition)

        return new_survey

    @classmethod
    def get_request_example(cls) -> dict[str, Any]:
        """
        Get an example request for the vibe_add handler.

        Returns:
            dict: Example request data that would be valid for this handler
        """
        return {
            "survey_dict": {
                "questions": [
                    {
                        "question_name": "satisfaction",
                        "question_text": "How satisfied are you with our product?",
                        "question_type": "multiple_choice",
                        "question_options": ["Very satisfied", "Satisfied", "Neutral", "Dissatisfied", "Very dissatisfied"]
                    }
                ]
            },
            "add_instructions": "Add a demographic question asking for age, and only show it if they are satisfied with the product",
            "model": "gpt-4o",
            "temperature": 0.7
        }

    @classmethod
    def get_response_example(cls) -> dict[str, Any]:
        """
        Get an example response for the vibe_add handler.

        Returns:
            dict: Example response data that would be valid for this handler
        """
        return {
            "questions": [
                {
                    "question_name": "age",
                    "question_text": "What is your age?",
                    "question_type": "numerical",
                    "min_value": 18,
                    "max_value": 100
                }
            ],
            "skip_rules": [
                {
                    "target_question": "age",
                    "condition": "{{ satisfaction.answer }} != 'Very satisfied' and {{ satisfaction.answer }} != 'Satisfied'"
                }
            ]
        }


# The handler is automatically registered when this module is imported
# due to the RegisterVibesMethodsMeta metaclass