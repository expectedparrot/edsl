"""Module for editing surveys using natural language instructions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..survey import Survey


def edit_survey_with_vibes(
    survey: "Survey",
    edit_instructions: str,
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> "Survey":
    """Edit a survey using natural language instructions.

    This function uses an LLM to modify an existing survey based on natural language
    instructions. It can translate questions, change wording, drop questions, or
    make other modifications as requested.

    Args:
        survey: The Survey instance to edit
        edit_instructions: Natural language description of the edits to apply
        model: OpenAI model to use for editing (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Returns:
        Survey: A new Survey instance with the edited questions
    """
    from .vibe_editor import VibeEdit

    # Convert current questions to dict format
    current_questions = []
    for question in survey.questions:
        q_dict = question.to_dict()
        # Extract the relevant fields for the editor
        question_data = {
            "question_name": q_dict.get("question_name"),
            "question_text": q_dict.get("question_text"),
            "question_type": q_dict.get("question_type"),
        }
        if "question_options" in q_dict and q_dict["question_options"]:
            question_data["question_options"] = q_dict["question_options"]
        if "min_value" in q_dict and q_dict["min_value"] is not None:
            question_data["min_value"] = q_dict["min_value"]
        if "max_value" in q_dict and q_dict["max_value"] is not None:
            question_data["max_value"] = q_dict["max_value"]
        current_questions.append(question_data)

    # Create the editor
    editor = VibeEdit(model=model, temperature=temperature)

    # Edit the survey
    edited_data = editor.edit_survey(current_questions, edit_instructions)

    # Convert each edited question definition to a question object
    questions = []
    for i, q_data in enumerate(edited_data["questions"]):
        question_obj = survey._create_question_from_dict(q_data, f"q{i}")
        questions.append(question_obj)

    return survey.__class__(questions)
