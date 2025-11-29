"""
FromVibes Handler Registration

Registers the Survey.from_vibes() method with the vibes registry system.
This handler enables both local and remote execution of survey generation
from natural language descriptions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

try:
    from ..vibes_handler_base import VibesHandlerBase
    from ..survey_generator import SurveyGenerator
    from ..schemas import FromVibesRequest, SurveySchema
    from ..from_vibes import generate_survey_from_vibes
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from vibes_handler_base import VibesHandlerBase
    from survey_generator import SurveyGenerator
    from schemas import FromVibesRequest, SurveySchema
    from from_vibes import generate_survey_from_vibes

if TYPE_CHECKING:
    from ...survey import Survey


class FromVibesHandler(VibesHandlerBase):
    """
    Handler registration for Survey.from_vibes() method.

    This class registers the from_vibes functionality with the vibes registry,
    enabling it to be called through the generic dispatch system and potentially
    executed remotely through the server package.

    Attributes
    ----------
    vibes_target : str
        Target object type ("survey")
    vibes_method : str
        Method name ("from_vibes")
    handler_class : type
        Handler class (SurveyGenerator)
    handler_function : callable
        Handler function (generate_survey_from_vibes)
    request_schema : type
        Pydantic request schema (FromVibesRequest)
    response_schema : type
        Pydantic response schema (SurveySchema)
    is_classmethod : bool
        True (from_vibes is a classmethod)
    """

    # Registry configuration
    vibes_target = "survey"
    vibes_method = "from_vibes"
    handler_class = SurveyGenerator
    handler_function = generate_survey_from_vibes
    request_schema = FromVibesRequest
    response_schema = SurveySchema
    is_classmethod = True
    metadata = {
        "description": "Generate a survey from a natural language description",
        "supports_remote": True,
        "supports_local": True,
    }

    @classmethod
    def execute_local(
        cls,
        survey_cls: type,
        description: str,
        *,
        num_questions: Optional[int] = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        remote: bool = False,
        **kwargs
    ) -> "Survey":
        """
        Execute the from_vibes method locally.

        This method calls the existing generate_survey_from_vibes function
        with the provided arguments and returns the result.

        Args:
            survey_cls: The Survey class to instantiate
            description: Natural language description of the survey topic
            num_questions: Optional number of questions to generate
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            remote: Force remote generation even if OPENAI_API_KEY is available
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            Survey: A new Survey instance with the generated questions

        Raises:
            Various exceptions from generate_survey_from_vibes function
        """
        return cls.handler_function(
            survey_cls=survey_cls,
            description=description,
            num_questions=num_questions,
            model=model,
            temperature=temperature,
            remote=remote,
        )

    @classmethod
    def to_remote_request(
        cls,
        survey_cls: type,
        description: str,
        *,
        num_questions: Optional[int] = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        remote: bool = False,
        **kwargs
    ) -> dict[str, Any]:
        """
        Convert local method arguments to remote request format.

        For from_vibes, we don't need to send the survey_cls since the
        server will return the raw survey data that can be used to
        construct any Survey class.

        Args:
            survey_cls: Survey class (not included in remote request)
            description: Natural language description of the survey topic
            num_questions: Optional number of questions to generate
            model: OpenAI model to use for generation
            temperature: Temperature for generation
            remote: Force remote generation (ignored for remote requests)
            **kwargs: Additional arguments (ignored)

        Returns:
            dict: Validated request data for remote execution
        """
        # Create and validate the request using the schema
        request_obj = cls.request_schema(
            description=description,
            num_questions=num_questions,
            model=model,
            temperature=temperature
        )

        return request_obj.model_dump()

    @classmethod
    def from_remote_response(
        cls,
        response_data: dict[str, Any],
        survey_cls: type = None,
    ) -> Any:
        """
        Convert remote response data to local return format.

        For from_vibes, the remote response contains survey data that
        needs to be converted back to a Survey instance.

        Args:
            response_data: Raw response data from remote server
            survey_cls: Survey class to construct (provided by dispatcher)

        Returns:
            Survey: A new Survey instance with the generated questions

        Raises:
            ValidationError: If response doesn't match response schema
            ValueError: If survey_cls is not provided
        """
        if survey_cls is None:
            raise ValueError("survey_cls is required to construct Survey from remote response")

        # Validate response using response schema
        response_obj = cls.response_schema(**response_data)

        # Convert question definitions to Survey instance
        # (This matches the logic from generate_survey_from_vibes)
        questions = []
        for i, q_data in enumerate(response_obj.questions):
            question_dict = q_data.model_dump()
            question_obj = survey_cls._create_question_from_dict(question_dict, f"q{i}")
            questions.append(question_obj)

        return survey_cls(questions)

    @classmethod
    def get_request_example(cls) -> dict[str, Any]:
        """
        Get an example request for the from_vibes handler.

        Returns:
            dict: Example request data that would be valid for this handler
        """
        return {
            "description": "Survey about customer satisfaction with a new mobile app",
            "num_questions": 5,
            "model": "gpt-4o",
            "temperature": 0.7
        }

    @classmethod
    def get_response_example(cls) -> dict[str, Any]:
        """
        Get an example response for the from_vibes handler.

        Returns:
            dict: Example response data that would be valid for this handler
        """
        return {
            "questions": [
                {
                    "question_name": "app_usage_frequency",
                    "question_text": "How often do you use the app?",
                    "question_type": "multiple_choice",
                    "question_options": ["Daily", "Weekly", "Monthly", "Rarely", "Never"]
                },
                {
                    "question_name": "overall_satisfaction",
                    "question_text": "The app meets my needs",
                    "question_type": "likert_five",
                    "question_options": None
                },
                {
                    "question_name": "recommendation",
                    "question_text": "Would you recommend this app to others?",
                    "question_type": "yes_no",
                    "question_options": None
                }
            ]
        }


# The handler is automatically registered when this module is imported
# due to the RegisterVibesMethodsMeta metaclass