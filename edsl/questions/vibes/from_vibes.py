"""Module for generating questions from natural language descriptions."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..question_base import QuestionBase


def generate_question_from_vibes(
    question_cls: type,
    description: str,
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> "QuestionBase":
    """Generate a question from a natural language description.

    This function uses an LLM to generate an appropriate EDSL question based on a
    description of what the question should ask. It automatically selects appropriate
    question types and formats.

    Args:
        question_cls: The Question class to use (should be the Question factory)
        description: Natural language description of what the question should ask
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Returns:
        QuestionBase: A new Question instance with the appropriate type

    Examples:
        >>> from edsl.questions import Question
        >>> q = Question.from_vibes("Ask what their favorite color is")  # doctest: +SKIP
        >>> print(q.question_name, q.question_type)  # doctest: +SKIP
    """
    from .question_generator import QuestionGenerator

    # Create the generator
    generator = QuestionGenerator(model=model, temperature=temperature)

    # Generate the question schema
    question_data = generator.generate_question(description)

    # Create the question object using the Question factory
    # Extract the question_type and other parameters
    question_type = question_data.pop("question_type")

    # Handle special conversions for certain question types
    if question_type in ("linear_scale", "linearscale"):
        # Convert min_value/max_value to question_options if needed
        if (
            "question_options" not in question_data
            or not question_data["question_options"]
        ):
            min_val = question_data.get("min_value")
            max_val = question_data.get("max_value")
            # Use defaults if not provided
            if min_val is None:
                min_val = 1
            if max_val is None:
                max_val = 5
            question_data["question_options"] = list(
                range(int(min_val), int(max_val) + 1)
            )
        # Remove min_value and max_value as they're not used by QuestionLinearScale
        question_data.pop("min_value", None)
        question_data.pop("max_value", None)

    # Filter out None values and irrelevant parameters
    filtered_data = {}
    for key, value in question_data.items():
        if value is not None:
            filtered_data[key] = value

    # Create and return the question
    return question_cls(question_type, **filtered_data)
