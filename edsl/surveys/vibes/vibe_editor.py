"""
Survey Vibe Editor: Edit existing surveys using natural language instructions.

This module provides a VibeEdit class that can modify existing surveys
based on natural language instructions. It can translate questions, change
wording, drop questions, or make other edits as requested.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI
import os
import json
from dotenv import load_dotenv
from pathlib import Path


def find_dotenv_upwards(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Search for .env file starting from start_path and moving up the directory tree.

    Parameters
    ----------
    start_path : str, optional
        Starting directory for the search. Defaults to current working directory.

    Returns
    -------
    Path or None
        Path to the .env file if found, None otherwise.
    """
    if start_path is None:
        start_path = os.getcwd()

    current = Path(start_path).resolve()

    # Search upwards until we find .env or reach the root
    while True:
        env_file = current / ".env"
        if env_file.is_file():
            return env_file

        # Check if we've reached the root
        parent = current.parent
        if parent == current:
            # We've reached the root directory
            return None

        current = parent


# Load environment variables from .env file (search upwards from current directory)
env_path = find_dotenv_upwards()
if env_path:
    load_dotenv(env_path)


# ---------- 1) Pydantic schema for question definition ----------
class QuestionDefinition(BaseModel):
    """
    Schema for a single question in a survey.

    Attributes
    ----------
    question_name : str
        A valid Python variable name to identify the question
    question_text : str
        The actual text of the question to be asked
    question_type : str
        The type of question (e.g., 'multiple_choice', 'free_text', 'likert_five', etc.)
    question_options : Optional[List[str]]
        List of options for choice-based questions (required for multiple_choice, checkbox, etc.)
    min_value : Optional[float]
        Minimum value for numerical questions
    max_value : Optional[float]
        Maximum value for numerical questions
    """

    question_name: str = Field(
        description="A valid Python variable name to identify the question (e.g., 'age', 'satisfaction_rating')"
    )
    question_text: str = Field(
        description="The actual text of the question to be asked"
    )
    question_type: str = Field(
        description=(
            "The type of question. Must be one of: "
            "'free_text' (open-ended text), "
            "'multiple_choice' (select one option), "
            "'checkbox' (select multiple options), "
            "'numerical' (numeric answer), "
            "'likert_five' (5-point agree/disagree scale), "
            "'linear_scale' (numeric scale with labels), "
            "'yes_no' (simple yes/no), "
            "'rank' (rank items in order), "
            "'budget' (allocate budget across options), "
            "'list' (list of items), "
            "'matrix' (grid of questions)"
        )
    )
    question_options: Optional[List[str]] = Field(
        None,
        description="List of options for choice-based questions (required for multiple_choice, checkbox, rank, budget)",
    )
    min_value: Optional[float] = Field(
        None, description="Minimum value for numerical or linear_scale questions"
    )
    max_value: Optional[float] = Field(
        None, description="Maximum value for numerical or linear_scale questions"
    )


class EditedSurveySchema(BaseModel):
    """
    Schema for an edited survey definition.

    Attributes
    ----------
    questions : List[QuestionDefinition]
        List of questions that make up the edited survey
    """

    questions: List[QuestionDefinition] = Field(
        description="List of questions in the edited survey"
    )


# ---------- 2) The main editor class ----------
@dataclass
class VibeEdit:
    """
    Edit existing surveys using natural language instructions.

    This class uses an LLM to modify an existing survey based on natural language
    instructions. It can translate questions, change wording, drop questions, or
    make other modifications as requested.

    Parameters
    ----------
    model : str
        The OpenAI model to use for editing (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> editor = VibeEdit()  # doctest: +SKIP
    >>> edited_survey = editor.edit_survey(original_questions, "Translate all questions to Spanish")  # doctest: +SKIP
    >>> print(json.dumps(edited_survey, indent=2))  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = OpenAI()  # reads OPENAI_API_KEY from env

    def edit_survey(
        self,
        current_questions: List[Dict[str, Any]],
        edit_instructions: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Edit a survey based on natural language instructions.

        Parameters
        ----------
        current_questions : List[Dict[str, Any]]
            List of current question dictionaries from the survey. Each question
            dict should have keys: question_name, question_text, question_type,
            and optionally question_options, min_value, max_value.
        edit_instructions : str
            Natural language description of the edits to apply.
            Examples:
            - "Translate all questions to Spanish"
            - "Make the language more formal"
            - "Remove question 3"
            - "Change all likert scales to multiple choice"
            - "Add more casual tone to all questions"

        Returns
        -------
        dict
            Dictionary with a "questions" key containing a list of edited question
            dictionaries. Each question dict has keys: question_name, question_text,
            question_type, and optionally question_options, min_value, max_value.

        Examples
        --------
        >>> editor = VibeEdit(model="gpt-4o", temperature=0.7)  # doctest: +SKIP
        >>> original = [  # doctest: +SKIP
        ...     {  # doctest: +SKIP
        ...         "question_name": "satisfaction",  # doctest: +SKIP
        ...         "question_text": "How satisfied are you?",  # doctest: +SKIP
        ...         "question_type": "likert_five"  # doctest: +SKIP
        ...     }  # doctest: +SKIP
        ... ]  # doctest: +SKIP
        >>> result = editor.edit_survey(original, "Translate to Spanish")  # doctest: +SKIP
        >>> result["questions"][0]["question_text"]  # doctest: +SKIP
        '¿Qué tan satisfecho está?'
        """
        system = (
            "You are an expert survey editor. "
            "Given a set of existing survey questions and instructions for editing them, "
            "apply the requested changes while maintaining survey quality and coherence. "
            "\n\n"
            "Your task is to:\n"
            "1. Understand the current survey structure\n"
            "2. Apply the requested edits carefully\n"
            "3. Maintain question integrity (proper question_name, question_text, question_type, options)\n"
            "4. Preserve question_options for choice-based questions unless explicitly asked to change them\n"
            "5. Keep question_name variables valid (Python variable names)\n"
            "6. Return ONLY the questions that should remain in the edited survey\n"
            "\n"
            "Available question types:\n"
            "- 'free_text': Open-ended text responses\n"
            "- 'multiple_choice': Select exactly one option from a list\n"
            "- 'checkbox': Select one or more options from a list\n"
            "- 'numerical': Numeric answer (with optional min/max)\n"
            "- 'likert_five': 5-point scale from 'Strongly disagree' to 'Strongly agree'\n"
            "- 'linear_scale': Numeric scale with labeled endpoints (e.g., 1-10)\n"
            "- 'yes_no': Simple yes/no question\n"
            "- 'rank': Rank items in order of preference\n"
            "- 'budget': Allocate a budget across multiple options\n"
            "- 'list': Response as a list of items\n"
            "- 'matrix': Grid of related questions\n"
            "\n"
            "Important guidelines:\n"
            "- If asked to drop/remove a question, exclude it from the output\n"
            "- If asked to translate, translate question_text AND question_options (if present)\n"
            "- If asked to change tone, modify the question_text appropriately\n"
            "- If asked to change question types, update both question_type and question_options as needed\n"
            "- Maintain consistency across all questions\n"
            "- Preserve the original question_name unless explicitly asked to change it\n"
        )

        user_prompt = {
            "task": "Edit the following survey",
            "current_survey": current_questions,
            "edit_instructions": edit_instructions,
            "instructions": (
                "Apply the requested edits to the survey questions. "
                "Return the complete edited survey with all questions that should remain. "
                "Ensure all questions maintain proper structure with appropriate question_type, "
                "question_options (where needed), and valid question_name variables."
            ),
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=EditedSurveySchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic models to dicts
        return {"questions": [q.model_dump() for q in out.questions]}


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    editor = VibeEdit(model="gpt-4o", temperature=0.7)

    # Example survey to edit
    original_survey = [
        {
            "question_name": "satisfaction",
            "question_text": "How satisfied are you with our product?",
            "question_type": "multiple_choice",
            "question_options": [
                "Very satisfied",
                "Satisfied",
                "Neutral",
                "Dissatisfied",
                "Very dissatisfied",
            ],
        },
        {
            "question_name": "recommendation",
            "question_text": "Would you recommend us to a friend?",
            "question_type": "yes_no",
        },
        {
            "question_name": "feedback",
            "question_text": "Please provide any additional feedback",
            "question_type": "free_text",
        },
    ]

    # Example 1: Translate to Spanish
    print("Example 1: Translate to Spanish")
    result1 = editor.edit_survey(original_survey, "Translate all questions to Spanish")
    print(json.dumps(result1, indent=2))
    print()

    # Example 2: Make more formal
    print("Example 2: Make language more formal")
    result2 = editor.edit_survey(
        original_survey, "Make the language more formal and professional"
    )
    print(json.dumps(result2, indent=2))
    print()

    # Example 3: Drop a question
    print("Example 3: Remove the recommendation question")
    result3 = editor.edit_survey(
        original_survey, "Remove the question about recommendation"
    )
    print(json.dumps(result3, indent=2))
