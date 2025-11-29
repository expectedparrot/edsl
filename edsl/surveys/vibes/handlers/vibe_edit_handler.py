"""
VibeEdit Handler Registration

Registers the Survey.vibe_edit() method with the vibes registry system.
This handler enables both local and remote execution of survey editing
using natural language instructions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..vibes_handler_base import VibesHandlerBase
from ..vibe_editor import VibeEdit
from ..schemas import VibeEditRequest, EditedSurveySchema
from ..vibe_edit_handler import edit_survey_with_vibes

if TYPE_CHECKING:
    from ...survey import Survey


class VibeEditHandler(VibesHandlerBase):
    """
    Handler registration for Survey.vibe_edit() method.

    This class registers the vibe_edit functionality with the vibes registry,
    enabling it to be called through the generic dispatch system and potentially
    executed remotely through the server package.

    Attributes
    ----------
    vibes_target : str
        Target object type ("survey")
    vibes_method : str
        Method name ("vibe_edit")
    handler_class : type
        Handler class (VibeEdit)
    handler_function : callable
        Handler function (edit_survey_with_vibes)
    request_schema : type
        Pydantic request schema (VibeEditRequest)
    response_schema : type
        Pydantic response schema (EditedSurveySchema)
    is_classmethod : bool
        False (vibe_edit is an instance method)
    """

    # Registry configuration
    vibes_target = "survey"
    vibes_method = "vibe_edit"
    handler_class = VibeEdit
    handler_function = edit_survey_with_vibes
    request_schema = VibeEditRequest
    response_schema = EditedSurveySchema
    is_classmethod = False
    metadata = {
        "description": "Edit an existing survey using natural language instructions",
        "supports_remote": True,
        "supports_local": True,
    }

    @classmethod
    def execute_local(
        cls,
        survey: "Survey",
        edit_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        **kwargs
    ) -> "Survey":
        """
        Execute the vibe_edit method locally.

        This method calls the existing edit_survey_with_vibes function
        with the provided arguments and returns the result.

        Args:
            survey: The Survey instance to edit
            edit_instructions: Natural language description of the edits to apply
            model: OpenAI model to use for editing (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            Survey: A new Survey instance with the edited questions

        Raises:
            Various exceptions from edit_survey_with_vibes function
        """
        return cls.handler_function(
            survey=survey,
            edit_instructions=edit_instructions,
            model=model,
            temperature=temperature,
        )

    @classmethod
    def to_remote_request(
        cls,
        survey: "Survey",
        edit_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        **kwargs
    ) -> dict[str, Any]:
        """
        Convert local method arguments to remote request format.

        For vibe_edit, we need to serialize the survey to a dictionary
        format that can be sent to the remote server.

        Args:
            survey: The Survey instance to edit
            edit_instructions: Natural language description of the edits to apply
            model: OpenAI model to use for editing
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
            edit_instructions=edit_instructions,
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

        For vibe_edit, the remote response contains edited survey data that
        needs to be converted back to a Survey instance.

        Args:
            response_data: Raw response data from remote server
            survey: Original survey instance (used to get the Survey class)

        Returns:
            Survey: A new Survey instance with the edited questions

        Raises:
            ValidationError: If response doesn't match response schema
            ValueError: If survey is not provided
        """
        if survey is None:
            raise ValueError("survey is required to construct Survey from remote response")

        # Validate response using response schema
        response_obj = cls.response_schema(**response_data)

        # Convert question definitions to Survey instance
        # (This matches the logic from edit_survey_with_vibes)
        questions = []
        for i, q_data in enumerate(response_obj.questions):
            question_dict = q_data.model_dump()
            question_obj = survey._create_question_from_dict(question_dict, f"q{i}")
            questions.append(question_obj)

        return survey.__class__(questions)

    @classmethod
    def get_request_example(cls) -> dict[str, Any]:
        """
        Get an example request for the vibe_edit handler.

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
                    },
                    {
                        "question_name": "recommendation",
                        "question_text": "Would you recommend us to a friend?",
                        "question_type": "yes_no"
                    }
                ]
            },
            "edit_instructions": "Translate all questions to Spanish",
            "model": "gpt-4o",
            "temperature": 0.7
        }

    @classmethod
    def get_response_example(cls) -> dict[str, Any]:
        """
        Get an example response for the vibe_edit handler.

        Returns:
            dict: Example response data that would be valid for this handler
        """
        return {
            "questions": [
                {
                    "question_name": "satisfaction",
                    "question_text": "¿Qué tan satisfecho está con nuestro producto?",
                    "question_type": "multiple_choice",
                    "question_options": ["Muy satisfecho", "Satisfecho", "Neutral", "Insatisfecho", "Muy insatisfecho"]
                },
                {
                    "question_name": "recommendation",
                    "question_text": "¿Recomendaría nuestros servicios a un amigo?",
                    "question_type": "yes_no"
                }
            ]
        }


# The handler is automatically registered when this module is imported
# due to the RegisterVibesMethodsMeta metaclass