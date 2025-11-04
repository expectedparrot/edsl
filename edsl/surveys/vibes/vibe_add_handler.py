"""Module for adding questions to surveys using natural language instructions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..survey import Survey


def add_questions_with_vibes(
    survey: "Survey",
    add_instructions: str,
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> "Survey":
    """Add new questions to a survey using natural language instructions.

    This function uses an LLM to add new questions to an existing survey based on
    natural language instructions. It can add simple questions, questions with
    skip logic, or multiple related questions. Existing skip logic is preserved.

    Args:
        survey: The Survey instance to add questions to
        add_instructions: Natural language description of what to add
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Returns:
        Survey: A new Survey instance with the original questions plus the new ones
    """
    from .vibe_add_helper import VibeAdd

    # Get current question information for context
    current_questions = []
    for question in survey.questions:
        q_dict = question.to_dict()
        question_data = {
            "question_name": q_dict.get("question_name"),
            "question_text": q_dict.get("question_text"),
            "question_type": q_dict.get("question_type"),
        }
        if "question_options" in q_dict and q_dict["question_options"]:
            question_data["question_options"] = q_dict["question_options"]
        current_questions.append(question_data)

    # Create the adder
    adder = VibeAdd(model=model, temperature=temperature)

    # Generate new questions
    added_data = adder.add_questions(current_questions, add_instructions)

    # Convert new questions to question objects
    new_questions = []
    base_index = len(survey.questions)
    for i, q_data in enumerate(added_data["questions"]):
        question_obj = survey._create_question_from_dict(q_data, f"q{base_index + i}")
        new_questions.append(question_obj)

    # Create new survey with all questions AND preserve existing rule_collection
    all_questions = list(survey.questions) + new_questions
    new_survey = survey.__class__(
        questions=all_questions,
        rule_collection=survey.rule_collection,  # Preserves existing skip logic!
    )

    # Add skip logic for newly added questions if specified
    for skip_rule in added_data.get("skip_rules", []):
        target_question = skip_rule["target_question"]
        condition = skip_rule["condition"]
        new_survey = new_survey.add_skip_rule(target_question, condition)

    return new_survey
