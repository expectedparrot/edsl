"""Module for generating descriptions of surveys using natural language."""

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from ..survey import Survey


def describe_survey_with_vibes(
    survey: "Survey",
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> Dict[str, str]:
    """Generate a title and description for a survey.

    This function uses an LLM to analyze an existing survey and generate
    a descriptive title and detailed description of what the survey is about.

    Args:
        survey: The Survey instance to describe
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Returns:
        dict: Dictionary with keys:
            - "proposed_title": A single sentence title for the survey
            - "description": A paragraph-length description of the survey
    """
    from .vibe_describer import VibeDescribe

    # Convert current questions to dict format
    questions = []
    for question in survey.questions:
        q_dict = question.to_dict()
        # Extract the relevant fields for the describer
        question_data = {
            "question_name": q_dict.get("question_name"),
            "question_text": q_dict.get("question_text"),
            "question_type": q_dict.get("question_type"),
        }
        if "question_options" in q_dict and q_dict["question_options"]:
            question_data["question_options"] = q_dict["question_options"]
        questions.append(question_data)

    # Create the describer
    describer = VibeDescribe(model=model, temperature=temperature)

    # Generate description
    return describer.describe_survey(questions)
