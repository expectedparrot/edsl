"""
Survey Vibe Add Helper: Add new questions to surveys using natural language.

This module provides a VibeAdd class that can add new questions to existing surveys
based on natural language instructions. It can add simple questions, questions with
skip logic, or multiple related questions.
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
    Schema for a single question to be added to a survey.

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


class SkipRuleDefinition(BaseModel):
    """
    Schema for a skip rule to be applied to a question.

    Attributes
    ----------
    target_question : str
        The question_name of the question to apply the skip rule to
    condition : str
        The condition expression that determines if the question should be skipped
    """

    target_question: str = Field(
        description="The question_name of the question to apply the skip rule to"
    )
    condition: str = Field(
        description=(
            "The condition expression that determines if the question should be skipped. "
            "Use template syntax to reference previous questions' answers. "
            'Examples: "{{ q0.answer }} == \'yes\'", "{{ age.answer }} > 18", '
            "\"{{ satisfaction.answer }} == 'Very satisfied'\""
        )
    )


class AddedQuestionsSchema(BaseModel):
    """
    Schema for questions to be added to a survey.

    Attributes
    ----------
    questions : List[QuestionDefinition]
        List of questions to add to the survey
    skip_rules : List[SkipRuleDefinition]
        List of skip rules to apply to the added questions
    """

    questions: List[QuestionDefinition] = Field(
        description="List of questions to add to the survey"
    )
    skip_rules: List[SkipRuleDefinition] = Field(
        default=[],
        description="List of skip rules to apply to the added questions (optional)",
    )


# ---------- 2) The main adder class ----------
@dataclass
class VibeAdd:
    """
    Add new questions to surveys using natural language instructions.

    This class uses an LLM to generate new questions to add to an existing survey
    based on natural language instructions. It can add simple questions, questions
    with skip logic, or multiple related questions.

    Parameters
    ----------
    model : str
        The OpenAI model to use for generation (default: "gpt-4o")
    temperature : float
        Temperature for generation (default: 0.7)

    Examples
    --------
    >>> adder = VibeAdd()  # doctest: +SKIP
    >>> current_questions = [{"question_name": "q0", "question_text": "Do you like our product?", "question_type": "yes_no"}]  # doctest: +SKIP
    >>> result = adder.add_questions(current_questions, "Add a question asking their age")  # doctest: +SKIP
    >>> print(json.dumps(result, indent=2))  # doctest: +SKIP
    """

    model: str = "gpt-4o"
    temperature: float = 0.7

    def __post_init__(self):
        self.client = create_openai_client()  # reads OPENAI_API_KEY from env with proper error handling

    def add_questions(
        self,
        current_questions: List[Dict[str, Any]],
        add_instructions: str,
    ) -> Dict[str, Any]:
        """
        Add new questions to a survey based on natural language instructions.

        Parameters
        ----------
        current_questions : List[Dict[str, Any]]
            List of current question dictionaries from the survey. Each question
            dict should have keys: question_name, question_text, question_type,
            and optionally question_options, min_value, max_value.
        add_instructions : str
            Natural language description of what questions to add.
            Examples:
            - "Add a question asking their age"
            - "Add a follow-up question about satisfaction if they answered yes to q0"
            - "Add questions about demographics: age, gender, and location"
            - "Add a question asking about income, but only show it if age > 18"

        Returns
        -------
        dict
            Dictionary with keys:
            - "questions": List of question dictionaries to add
            - "skip_rules": List of skip rule dictionaries (optional)

        Examples
        --------
        >>> adder = VibeAdd(model="gpt-4o", temperature=0.7)  # doctest: +SKIP
        >>> current = [  # doctest: +SKIP
        ...     {  # doctest: +SKIP
        ...         "question_name": "liked_product",  # doctest: +SKIP
        ...         "question_text": "Do you like our product?",  # doctest: +SKIP
        ...         "question_type": "yes_no"  # doctest: +SKIP
        ...     }  # doctest: +SKIP
        ... ]  # doctest: +SKIP
        >>> result = adder.add_questions(current, "Add a question asking their age")  # doctest: +SKIP
        >>> result["questions"][0]["question_name"]  # doctest: +SKIP
        'age'
        """
        system = (
            "You are an expert survey designer. "
            "Given an existing survey and instructions for adding new questions, "
            "create appropriate new questions to add to the survey. "
            "\n\n"
            "Your task is to:\n"
            "1. Understand the current survey structure and question names\n"
            "2. Generate new questions based on the instructions\n"
            "3. Assign appropriate question_name variables (valid Python names)\n"
            "4. Select appropriate question types and options\n"
            "5. If the instructions mention conditional logic, create skip rules\n"
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
            "Skip rule syntax:\n"
            "- Use template syntax: {{ question_name.answer }} to reference previous answers\n"
            "- Examples:\n"
            "  * \"{{ q0.answer }} == 'yes'\" - skip if q0 answer is 'yes'\n"
            '  * "{{ age.answer }} > 18" - skip if age is greater than 18\n'
            "  * \"{{ satisfaction.answer }} == 'Very satisfied'\" - skip if satisfaction is 'Very satisfied'\n"
            "- Skip rules make the question NOT show if the condition is True\n"
            "- You can reference ANY existing question by its question_name\n"
            "\n"
            "Important guidelines:\n"
            "- Generate descriptive question_name values (e.g., 'age', 'income', 'purchase_frequency')\n"
            "- If adding multiple questions, ensure question_name values are unique\n"
            "- If the instructions mention 'only if', 'when', 'conditional', create appropriate skip rules\n"
            "- For skip rules, negate the condition (e.g., if they say 'only show if yes', use skip rule for 'no')\n"
            "- Skip rules should reference questions by their exact question_name from the current survey\n"
            "- Provide question_options for all choice-based questions\n"
            "- Keep questions clear, unbiased, and professional\n"
        )

        user_prompt = {
            "task": "Add new questions to the survey",
            "current_survey": current_questions,
            "add_instructions": add_instructions,
            "instructions": (
                "Generate the new questions to add to the survey based on the instructions. "
                "If the instructions mention conditional logic (e.g., 'only if', 'when'), "
                "create appropriate skip rules. Remember that skip rules prevent a question "
                "from showing when the condition is True, so you may need to negate the logic "
                "from the instructions."
            ),
        }

        resp = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            text_format=AddedQuestionsSchema,
            temperature=self.temperature,
        )

        out = resp.output_parsed
        # Convert Pydantic models to dicts
        return {
            "questions": [q.model_dump() for q in out.questions],
            "skip_rules": [r.model_dump() for r in out.skip_rules],
        }


# ---------- 3) Example usage ----------
if __name__ == "__main__":
    adder = VibeAdd(model="gpt-4o", temperature=0.7)

    # Example survey to add to
    current_survey = [
        {
            "question_name": "liked_product",
            "question_text": "Do you like our product?",
            "question_type": "yes_no",
        },
        {
            "question_name": "satisfaction",
            "question_text": "How satisfied are you?",
            "question_type": "multiple_choice",
            "question_options": [
                "Very satisfied",
                "Satisfied",
                "Neutral",
                "Dissatisfied",
                "Very dissatisfied",
            ],
        },
    ]

    # Example 1: Add a simple question
    print("Example 1: Add a question asking their age")
    result1 = adder.add_questions(current_survey, "Add a question asking their age")
    print(json.dumps(result1, indent=2))
    print()

    # Example 2: Add a question with skip logic
    print("Example 2: Add a follow-up question with skip logic")
    result2 = adder.add_questions(
        current_survey,
        "Add a question about purchase frequency, but only show it if they liked the product",
    )
    print(json.dumps(result2, indent=2))
    print()

    # Example 3: Add multiple related questions
    print("Example 3: Add demographic questions")
    result3 = adder.add_questions(
        current_survey, "Add demographic questions: age, gender, and location"
    )
    print(json.dumps(result3, indent=2))
