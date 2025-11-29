"""
VibeDescribe Handler Registration

Registers the Survey.vibe_describe() method with the vibes registry system.
This handler enables both local and remote execution of survey description
generation using natural language analysis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from ..vibes_handler_base import VibesHandlerBase
from ..vibe_describer import VibeDescribe
from ..schemas import VibeDescribeRequest, SurveyDescriptionSchema
from ..vibe_describe_handler import describe_survey_with_vibes

if TYPE_CHECKING:
    from ...survey import Survey


class VibeDescribeHandler(VibesHandlerBase):
    """
    Handler registration for Survey.vibe_describe() method.

    This class registers the vibe_describe functionality with the vibes registry,
    enabling it to be called through the generic dispatch system and potentially
    executed remotely through the server package.

    Attributes
    ----------
    vibes_target : str
        Target object type ("survey")
    vibes_method : str
        Method name ("vibe_describe")
    handler_class : type
        Handler class (VibeDescribe)
    handler_function : callable
        Handler function (describe_survey_with_vibes)
    request_schema : type
        Pydantic request schema (VibeDescribeRequest)
    response_schema : type
        Pydantic response schema (SurveyDescriptionSchema)
    is_classmethod : bool
        False (vibe_describe is an instance method)
    """

    # Registry configuration
    vibes_target = "survey"
    vibes_method = "vibe_describe"
    handler_class = VibeDescribe
    handler_function = describe_survey_with_vibes
    request_schema = VibeDescribeRequest
    response_schema = SurveyDescriptionSchema
    is_classmethod = False
    metadata = {
        "description": "Generate a title and description for an existing survey",
        "supports_remote": True,
        "supports_local": True,
    }

    @classmethod
    def execute_local(
        cls,
        survey: "Survey",
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, str]:
        """
        Execute the vibe_describe method locally.

        This method calls the existing describe_survey_with_vibes function
        with the provided arguments and returns the result.

        Args:
            survey: The Survey instance to describe
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            **kwargs: Additional arguments (ignored for compatibility)

        Returns:
            dict: Dictionary with keys:
                - "proposed_title": A single sentence title for the survey
                - "description": A paragraph-length description of the survey

        Raises:
            Various exceptions from describe_survey_with_vibes function
        """
        return cls.handler_function(
            survey=survey,
            model=model,
            temperature=temperature,
        )

    @classmethod
    def to_remote_request(
        cls,
        survey: "Survey",
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        **kwargs
    ) -> dict[str, Any]:
        """
        Convert local method arguments to remote request format.

        For vibe_describe, we need to serialize the survey to a dictionary
        format that can be sent to the remote server.

        Args:
            survey: The Survey instance to describe
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

        For vibe_describe, the remote response contains survey description data
        that can be returned directly as a dictionary.

        Args:
            response_data: Raw response data from remote server
            survey: Original survey instance (not needed for describe)

        Returns:
            dict: Dictionary with proposed_title and description

        Raises:
            ValidationError: If response doesn't match response schema
        """
        # Validate response using response schema
        response_obj = cls.response_schema(**response_data)

        # Return as dictionary (matches the return format of describe_survey_with_vibes)
        return response_obj.model_dump()

    @classmethod
    def get_request_example(cls) -> dict[str, Any]:
        """
        Get an example request for the vibe_describe handler.

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
                    },
                    {
                        "question_name": "feedback",
                        "question_text": "Please provide any additional feedback",
                        "question_type": "free_text"
                    }
                ]
            },
            "model": "gpt-4o",
            "temperature": 0.7
        }

    @classmethod
    def get_response_example(cls) -> dict[str, Any]:
        """
        Get an example response for the vibe_describe handler.

        Returns:
            dict: Example response data that would be valid for this handler
        """
        return {
            "proposed_title": "Customer Satisfaction and Recommendation Survey",
            "description": "This survey aims to gather feedback from customers about their satisfaction with our product and their likelihood to recommend our services to others. The survey covers key areas including overall satisfaction levels, recommendation behavior, and open-ended feedback to capture additional insights. This feedback will help us understand customer sentiment and identify areas for improvement in our product offerings and customer experience."
        }


# The handler is automatically registered when this module is imported
# due to the RegisterVibesMethodsMeta metaclass