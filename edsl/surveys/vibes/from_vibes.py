"""Module for generating surveys from natural language descriptions."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..survey import Survey


def generate_survey_from_vibes(
    survey_cls: type,
    description: str,
    *,
    num_questions: Optional[int] = None,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    remote: bool = False,
) -> "Survey":
    """Generate a survey from a natural language description.

    This function uses an LLM to generate a complete survey based on a description
    of what the survey should cover. It can execute in two modes:
    - Local: Uses your OPENAI_API_KEY to generate surveys locally
    - Remote: Delegates to a FastAPI server (used when no key or remote=True)

    The function automatically determines which mode to use based on:
    1. If remote=True, always use remote generation
    2. If OPENAI_API_KEY is not set, automatically use remote generation
    3. Otherwise, use local generation

    Args:
        survey_cls: The Survey class to instantiate
        description: Natural language description of the survey topic
        num_questions: Optional number of questions to generate
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)
        remote: Force remote generation even if OPENAI_API_KEY is available
            (default: False)

    Returns:
        Survey: A new Survey instance with the generated questions

    Raises:
        RemoteSurveyGenerationError: If remote generation fails
        SurveyGenerationError: If survey generation itself fails
        Various OpenAI exceptions: If local generation fails
    """
    from .remote_survey_generator import should_use_remote, RemoteSurveyGenerator

    # Determine execution path based on conditions
    use_remote = should_use_remote(remote)

    if use_remote:
        # Remote execution path
        generator = RemoteSurveyGenerator()
        survey_data = generator.generate_survey(
            description=description,
            num_questions=num_questions,
            model=model,
            temperature=temperature
        )
    else:
        # Local execution path (existing code)
        from .survey_generator import SurveyGenerator

        # Create the generator
        generator = SurveyGenerator(model=model, temperature=temperature)

        # Generate the survey schema
        survey_data = generator.generate_survey(description, num_questions=num_questions)

    # Convert each question definition to a question object (same for both paths)
    questions = []
    for i, q_data in enumerate(survey_data["questions"]):
        question_obj = survey_cls._create_question_from_dict(q_data, f"q{i}")
        questions.append(question_obj)

    return survey_cls(questions)
