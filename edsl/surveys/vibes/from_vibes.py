"""Module for generating surveys from natural language descriptions or pasted survey text."""

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
    """Generate a survey from a natural language description or parse pasted survey text.

    This function now supports two types of input:
    1. **Survey Description**: Natural language description of what the survey should cover
    2. **Pasted Survey Text**: Actual survey content copied from elsewhere that needs to be parsed

    The function automatically detects the input type using LLM analysis and handles appropriately:
    - For descriptions: Uses existing survey generation logic
    - For pasted text: Parses and infers question types to recreate the survey

    Execution modes:
    - Local: Uses your OPENAI_API_KEY to generate/parse surveys locally
    - Remote: Delegates to a FastAPI server (used when no key or remote=True)

    Args:
        survey_cls: The Survey class to instantiate
        description: Either a natural language description of the survey topic OR
                    pasted text of an existing survey to be parsed and recreated
        num_questions: Optional number of questions to generate (only used for descriptions)
        model: OpenAI model to use for generation/parsing (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)
        remote: Force remote generation even if OPENAI_API_KEY is available
            (default: False)

    Returns:
        Survey: A new Survey instance with generated or parsed questions

    Examples:
        # Survey description (original behavior)
        >>> survey = Survey.from_vibes("Customer satisfaction survey for a restaurant")  # doctest: +SKIP

        # Pasted survey text (new behavior)
        >>> pasted_text = '''
        ... 1. What is your name?
        ...
        ... 2. How would you rate our service?
        ... a) Excellent
        ... b) Good
        ... c) Fair
        ... d) Poor
        ...
        ... 3. Would you recommend us to others? (Yes/No)
        ... '''
        >>> survey = Survey.from_vibes(pasted_text)  # doctest: +SKIP

    Raises:
        RemoteSurveyGenerationError: If remote generation fails
        SurveyGenerationError: If survey generation itself fails
        Various OpenAI exceptions: If local generation/parsing fails
    """
    from .remote_survey_generator import should_use_remote, RemoteSurveyGenerator
    from .survey_text_analyzer import SurveyTextAnalyzer

    # Determine execution path based on conditions
    use_remote = should_use_remote(remote)

    if use_remote:
        # Remote execution path - for now, use existing remote generator
        # TODO: Enhance remote generator to handle text analysis
        generator = RemoteSurveyGenerator()
        survey_data = generator.generate_survey(
            description=description,
            num_questions=num_questions,
            model=model,
            temperature=temperature,
        )
        # Convert each question definition to a question object
        questions = []
        for i, q_data in enumerate(survey_data["questions"]):
            question_obj = survey_cls._create_question_from_dict(q_data, f"q{i}")
            questions.append(question_obj)

        return survey_cls(questions)
    else:
        # Local execution path with enhanced text analysis
        analyzer = SurveyTextAnalyzer(model=model, temperature=temperature)

        # Process input - analyzer will detect if it's description or pasted text
        return analyzer.process_survey_input(
            text=description, survey_cls=survey_cls, num_questions=num_questions
        )
