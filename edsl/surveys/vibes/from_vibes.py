"""Module for generating surveys from natural language descriptions."""

from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from ..survey import Survey


def generate_survey_from_vibes(
    survey_cls: type,
    description: str,
    *,
    num_questions: Optional[int] = None,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> "Survey":
    """Generate a survey from a natural language description.

    This function uses an LLM to generate a complete survey based on a description
    of what the survey should cover. It automatically selects appropriate question
    types and formats.

    Args:
        survey_cls: The Survey class to instantiate
        description: Natural language description of the survey topic
        num_questions: Optional number of questions to generate
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Returns:
        Survey: A new Survey instance with the generated questions
    """
    from .survey_generator import SurveyGenerator

    # Create the generator
    generator = SurveyGenerator(model=model, temperature=temperature)

    # Generate the survey schema
    survey_data = generator.generate_survey(description, num_questions=num_questions)

    # Convert each question definition to a question object
    questions = []
    for i, q_data in enumerate(survey_data["questions"]):
        question_obj = survey_cls._create_question_from_dict(q_data, f"q{i}")
        questions.append(question_obj)

    return survey_cls(questions)
