"""
Matrix question combination utilities.

This module provides functionality for combining multiple choice questions
into matrix questions, which is useful when importing surveys from platforms
like Qualtrics or SurveyMonkey where matrix questions are sometimes broken
down into separate multiple choice questions.
"""

import re
from typing import List, Optional, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from ..survey import Survey


def _find_common_prefix_and_items(question_texts: List[str]) -> Tuple[str, List[str]]:
    """
    Find the common prefix in question texts and extract individual items.

    Args:
        question_texts: List of question texts to analyze

    Returns:
        Tuple of (common_prefix, individual_items)

    Examples:
        >>> texts = [
        ...     "Overall, how much would you trust: - A freelancer without AI",
        ...     "Overall, how much would you trust: - A freelancer with AI"
        ... ]
        >>> prefix, items = _find_common_prefix_and_items(texts)
        >>> prefix
        'Overall, how much would you trust'
        >>> items
        ['A freelancer without AI', 'A freelancer with AI']
    """
    if not question_texts:
        return "", []

    if len(question_texts) == 1:
        # Single question - try to split on common separators
        text = question_texts[0]
        # Look for patterns like ": - " or " - "
        separators = [": - ", " - ", ": ", " – ", "- "]
        for sep in separators:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) == 2:
                    return parts[0].strip(), [parts[1].strip()]
        # If no separator found, use whole text as prefix and question name as item
        return text, [text]

    # Find longest common prefix
    common_prefix = question_texts[0]
    for text in question_texts[1:]:
        # Find common prefix character by character
        i = 0
        while i < len(common_prefix) and i < len(text) and common_prefix[i] == text[i]:
            i += 1
        common_prefix = common_prefix[:i]

    # Clean up the prefix - remove trailing separators and whitespace
    common_prefix = common_prefix.strip()

    # Find the best place to cut off the prefix by looking for word boundaries
    # after removing trailing separators
    words = common_prefix.split()
    if len(words) > 1:
        # Try different cutoff points, preferring complete meaningful phrases
        potential_cutoffs = []

        # Try cutting after punctuation followed by space
        for i, char in enumerate(common_prefix):
            if char in ":.-" and i < len(common_prefix) - 1:
                if common_prefix[i + 1] == " ":
                    potential_cutoffs.append(i)

        # If we found good cutoff points, use the last one
        if potential_cutoffs:
            best_cutoff = max(potential_cutoffs)
            common_prefix = common_prefix[:best_cutoff].strip()

    # Remove common trailing patterns
    patterns_to_remove = [
        r":\s*-?\s*$",  # ": -" or ": " or ":" at the end
        r"-\s*$",  # "- " at the end
        r"–\s*$",  # "– " at the end (em dash)
        r":\s*$",  # ": " at the end
    ]

    for pattern in patterns_to_remove:
        common_prefix = re.sub(pattern, "", common_prefix).strip()

    # Extract individual items
    items = []
    for text in question_texts:
        remaining = text[len(common_prefix) :].strip()

        # Remove leading separators from the remaining part
        leading_patterns = [
            r"^:\s*-\s*",  # ": - "
            r"^-\s*",  # "- "
            r"^–\s*",  # "– "
            r"^:\s*",  # ": "
        ]

        for pattern in leading_patterns:
            remaining = re.sub(pattern, "", remaining).strip()

        if remaining:
            items.append(remaining)
        else:
            # Fallback: use the original text if we can't extract a meaningful item
            items.append(text)

    # If the common prefix is too short or empty, use a generic one
    if len(common_prefix) < 10:  # Arbitrary threshold
        common_prefix = "Please rate each of the following"

    return common_prefix, items


def combine_multiple_choice_to_matrix(
    survey: "Survey",
    question_names: List[str],
    matrix_question_name: str,
    matrix_question_text: Optional[str] = None,
    use_question_text_as_items: bool = True,
    remove_original_questions: bool = True,
    index: Optional[int] = None,
    **kwargs,
) -> "Survey":
    """
    Combine multiple choice questions into a single matrix question.

    This is useful when importing surveys from platforms like Qualtrics or SurveyMonkey
    where matrix questions are sometimes broken down into separate multiple choice questions.

    Args:
        survey: The Survey object containing the questions to combine
        question_names: List of question names to combine into a matrix
        matrix_question_name: Name for the new matrix question
        matrix_question_text: Text for the new matrix question. If None, will attempt to
                              infer from the common prefix of existing question texts.
        use_question_text_as_items: If True, uses question_text as matrix items.
                                   If False, uses question_name as matrix items.
                                   When matrix_question_text is None and this is True,
                                   the items will be auto-extracted from question texts.
        remove_original_questions: If True, removes the original questions after combining
        index: Position to insert the matrix question. If None, adds at the end.
        **kwargs: Additional arguments to pass to QuestionMatrix constructor

    Returns:
        Survey: A new Survey object with the matrix question

    Raises:
        ValueError: If questions don't exist, aren't multiple choice, or have incompatible options

    Examples:
        >>> from edsl import Survey, QuestionMultipleChoice
        >>> from edsl.surveys.survey_helpers.matrix_combiner import combine_multiple_choice_to_matrix

        # Example 1: Explicit matrix question text
        >>> q1 = QuestionMultipleChoice("satisfaction_work", "How satisfied are you with work?", ["Very satisfied", "Somewhat satisfied", "Not satisfied"])
        >>> q2 = QuestionMultipleChoice("satisfaction_pay", "How satisfied are you with pay?", ["Very satisfied", "Somewhat satisfied", "Not satisfied"])
        >>> survey = Survey().add_question(q1).add_question(q2)
        >>> new_survey = combine_multiple_choice_to_matrix(
        ...     survey=survey,
        ...     question_names=["satisfaction_work", "satisfaction_pay"],
        ...     matrix_question_name="satisfaction_matrix",
        ...     matrix_question_text="How satisfied are you with each aspect?"
        ... )

        # Example 2: Auto-inferred matrix question text
        >>> q1 = QuestionMultipleChoice("trust1", "Overall, how much would you trust: - A freelancer without AI", ["High", "Medium", "Low"])
        >>> q2 = QuestionMultipleChoice("trust2", "Overall, how much would you trust: - A freelancer with AI", ["High", "Medium", "Low"])
        >>> survey = Survey().add_question(q1).add_question(q2)
        >>> new_survey = combine_multiple_choice_to_matrix(
        ...     survey=survey,
        ...     question_names=["trust1", "trust2"],
        ...     matrix_question_name="trust_matrix"
        ...     # matrix_question_text will be inferred as "Overall, how much would you trust"
        ...     # matrix items will be ["A freelancer without AI", "A freelancer with AI"]
        ... )
    """
    from ...questions import QuestionMultipleChoice, QuestionMatrix

    # Validate that all question names exist
    question_names_in_survey = survey.question_names
    missing_questions = [q for q in question_names if q not in question_names_in_survey]
    if missing_questions:
        raise ValueError(f"Questions not found in survey: {missing_questions}")

    # Get the questions and validate they're all multiple choice
    questions = []
    for q_name in question_names:
        question = survey.get(q_name)
        if not isinstance(question, QuestionMultipleChoice):
            raise ValueError(
                f"Question '{q_name}' is not a multiple choice question. Found type: {type(question).__name__}"
            )
        questions.append(question)

    # Validate that all questions have the same options
    first_question = questions[0]
    first_options = first_question.question_options
    for question in questions[1:]:
        if question.question_options != first_options:
            raise ValueError(
                f"All questions must have the same options. "
                f"Question '{question.question_name}' has options {question.question_options} "
                f"but expected {first_options}"
            )

    # Handle matrix question text and items - infer if needed
    if matrix_question_text is None and use_question_text_as_items:
        # Infer both question text and items from existing question texts
        question_texts = [q.question_text for q in questions]
        inferred_text, inferred_items = _find_common_prefix_and_items(question_texts)
        matrix_question_text = inferred_text
        matrix_items = inferred_items
    elif matrix_question_text is None:
        # No inference possible when using question names - use generic text
        matrix_question_text = "Please rate each of the following"
        matrix_items = [q.question_name for q in questions]
    else:
        # Use provided matrix_question_text and create items normally
        if use_question_text_as_items:
            matrix_items = [q.question_text for q in questions]
        else:
            matrix_items = [q.question_name for q in questions]

    # Extract option labels if they exist from the first question
    option_labels = getattr(first_question, "option_labels", None)

    # Create the matrix question
    matrix_question = QuestionMatrix(
        question_name=matrix_question_name,
        question_text=matrix_question_text,
        question_items=matrix_items,
        question_options=first_options,
        option_labels=option_labels,
        **kwargs,
    )

    # Create a new survey with the matrix question
    new_survey = survey.copy()

    # Remove original questions if requested
    if remove_original_questions:
        # Remove in reverse order to maintain indices
        for q_name in reversed(question_names):
            new_survey = new_survey.delete_question(q_name)

    # Add the matrix question
    new_survey = new_survey.add_question(matrix_question, index)

    return new_survey
