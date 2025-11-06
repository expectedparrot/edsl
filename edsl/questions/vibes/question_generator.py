"""
Question Generator: Generate questions from natural language descriptions using LLMs.

This module provides a QuestionGenerator class that can create appropriate EDSL questions
with proper question types, text, and options based on a natural language description.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from ...base.openai_utils import create_openai_client


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
    Schema for a single question definition.

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


# ---------- 2) The main generator class ----------
@dataclass
class QuestionGenerator:
    """
    Generate questions from natural language descriptions.

    This class uses an LLM to generate appropriate EDSL questions based on
    a natural language description. It automatically selects appropriate question
    types and formats.

    Parameters
    ----------
    model : str
        The OpenAI model to use for generation (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> gen = QuestionGenerator()  # doctest: +SKIP
    >>> result = gen.generate_question("Ask the user what their favorite color is")  # doctest: +SKIP
    >>> print(json.dumps(result, indent=2))  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = create_openai_client()  # reads OPENAI_API_KEY from env with proper error handling

    def generate_question(self, description: str) -> Dict[str, Any]:
        """
        Generate a question based on a natural language description.

        Parameters
        ----------
        description : str
            Natural language description of what the question should ask.
            Examples:
            - "Ask the user what their favorite color is"
            - "Find out how satisfied they are with the product on a 1-5 scale"
            - "Get their age as a number"
            - "Ask if they would recommend this to a friend"

        Returns
        -------
        dict
            Dictionary with keys: question_name, question_text, question_type,
            and optionally question_options, min_value, max_value.

        Examples
        --------
        >>> gen = QuestionGenerator(model="gpt-4o", temperature=0.7)  # doctest: +SKIP
        >>> result = gen.generate_question("Ask what their favorite color is")  # doctest: +SKIP
        >>> result["question_type"] in ["free_text", "multiple_choice"]  # doctest: +SKIP
        True
        """
        system = (
            "You are an expert survey designer. "
            "Given a description of a question to ask, create an appropriate EDSL question "
            "that captures the intent of the request. "
            "\n\n"
            "For the question, determine:\n"
            "1. An appropriate question_name (valid Python variable name, descriptive)\n"
            "2. Clear, unbiased question_text\n"
            "3. The most appropriate question_type from the available types\n"
            "4. question_options if needed (for multiple_choice, checkbox, rank, budget)\n"
            "5. min_value and max_value if needed (for numerical, linear_scale)\n"
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
            "CRITICAL: Matching Question Phrasing with Response Options\n"
            "=========================================================\n"
            "\n"
            "1. LIKERT_FIVE (Strongly disagree → Strongly agree):\n"
            "   - Use ONLY for STATEMENTS that can be agreed/disagreed with\n"
            "   - Good examples:\n"
            "     * 'The product meets my needs'\n"
            "     * 'I am satisfied with the service'\n"
            "     * 'The website is easy to navigate'\n"
            "   - BAD examples (DO NOT USE):\n"
            "     * 'How easy was it...' (use multiple_choice instead)\n"
            "     * 'How likely are you...' (use multiple_choice instead)\n"
            "     * 'Rate the...' (use linear_scale instead)\n"
            "\n"
            "2. MULTIPLE_CHOICE for 'How' questions:\n"
            "   - 'How easy...': ['Very easy', 'Easy', 'Neutral', 'Difficult', 'Very difficult']\n"
            "   - 'How likely...': ['Very likely', 'Likely', 'Neutral', 'Unlikely', 'Very unlikely']\n"
            "   - 'How satisfied...': ['Very satisfied', 'Satisfied', 'Neutral', 'Dissatisfied', 'Very dissatisfied']\n"
            "   - 'How often...': ['Very often', 'Often', 'Sometimes', 'Rarely', 'Never']\n"
            "   - 'How important...': ['Very important', 'Important', 'Neutral', 'Unimportant', 'Very unimportant']\n"
            "   - 'How clear...': ['Very clear', 'Clear', 'Neutral', 'Unclear', 'Very unclear']\n"
            "   - 'How quickly...': ['Very quickly', 'Quickly', 'Average', 'Slowly', 'Very slowly']\n"
            "\n"
            "3. LINEAR_SCALE for numeric ratings:\n"
            "   - Use for 'Rate...' or 'On a scale of...' questions\n"
            "   - Provide clear endpoint labels\n"
            "   - Example: 'Rate the quality' with options [1,2,3,4,5] (1=Poor, 5=Excellent)\n"
            "\n"
            "4. QUESTION STRUCTURE RULES:\n"
            "   - likert_five: Always phrase as a STATEMENT (no question words)\n"
            "   - multiple_choice: Phrase as a QUESTION ('How...', 'What...', 'Which...')\n"
            "   - Ensure response options semantically match the question structure\n"
            "\n"
            "Best practices:\n"
            "- Keep question_name descriptive but concise\n"
            "- Make question_text clear and unbiased\n"
            "- Provide 3-7 options for choice questions\n"
            "- ALWAYS verify question phrasing matches response format\n"
        )

        user_prompt = {
            "task": "Generate a single EDSL question",
            "description": description,
            "examples": {
                "correct_likert": {
                    "question_text": "The product meets my expectations",
                    "question_type": "likert_five",
                    "question_options": None,
                    "note": "Statement form - can be agreed/disagreed with",
                },
                "correct_multiple_choice": {
                    "question_text": "How easy was it to use the product?",
                    "question_type": "multiple_choice",
                    "question_options": [
                        "Very easy",
                        "Easy",
                        "Neutral",
                        "Difficult",
                        "Very difficult",
                    ],
                    "note": "Question form with matching options",
                },
                "incorrect_example": {
                    "question_text": "How easy was it to use the product?",
                    "question_type": "likert_five",
                    "question_options": None,
                    "note": "WRONG - 'How easy' question cannot use agree/disagree scale",
                },
            },
            "instructions": "Generate a single question that captures the intent of the description. Ensure question phrasing matches response options.",
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=QuestionDefinition,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic model to dict
        return out.model_dump()


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    gen = QuestionGenerator(model="gpt-4o", temperature=0.7)

    # Example 1: Simple text question
    print("Example 1: Ask what their favorite color is")
    result1 = gen.generate_question("Ask what their favorite color is")
    print(json.dumps(result1, indent=2))
    print()

    # Example 2: Satisfaction rating
    print("Example 2: Find out how satisfied they are with the product")
    result2 = gen.generate_question(
        "Find out how satisfied they are with the product on a 1-5 scale"
    )
    print(json.dumps(result2, indent=2))
    print()

    # Example 3: Yes/no question
    print("Example 3: Ask if they would recommend this to a friend")
    result3 = gen.generate_question("Ask if they would recommend this to a friend")
    print(json.dumps(result3, indent=2))
