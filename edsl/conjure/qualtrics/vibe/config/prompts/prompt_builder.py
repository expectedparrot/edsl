"""
Prompt builder for loading and constructing AI prompts from package resources.
"""

import importlib.resources
from typing import Dict, Any
from pathlib import Path


class PromptBuilder:
    """Builds AI prompts from template files and dynamic content."""

    def __init__(self):
        self._system_prompt = None

    @property
    def system_prompt(self) -> str:
        """Load system prompt from package resources."""
        if self._system_prompt is None:
            try:
                # Use importlib.resources for proper package resource loading
                with importlib.resources.open_text(
                    "edsl.conjure.qualtrics.vibe.config.prompts", "system_prompt.txt"
                ) as f:
                    self._system_prompt = f.read().strip()
            except (FileNotFoundError, ModuleNotFoundError):
                # Fallback for development/testing
                prompt_file = Path(__file__).parent / "system_prompt.txt"
                if prompt_file.exists():
                    self._system_prompt = prompt_file.read_text().strip()
                else:
                    raise FileNotFoundError(
                        "Could not load system prompt from package resources"
                    )

        return self._system_prompt

    def build_analysis_prompt(
        self, question_info: Dict[str, Any], edsl_info: str
    ) -> str:
        """
        Build complete analysis prompt for question analysis.

        Args:
            question_info: Dictionary with question details (name, text, type, options)
            edsl_info: EDSL question type information

        Returns:
            Complete formatted prompt string
        """
        return f"""
Analyze the following survey question for TECHNICAL conversion errors from Qualtrics CSV export:

Question Name: {question_info['name']}
Question Text: {question_info['text']}
Current Question Type: {question_info['type']}
Current Question Options: {question_info['options']}

ANALYSIS FOCUS:
Look ONLY for technical conversion issues such as:
1. HTML tags, entities, or artifacts (e.g., <p>, <b>, &nbsp;, &lt;, etc.)
2. Encoding problems or corrupted characters
3. Question type misclassification due to conversion errors
4. Corrupted or incomplete option lists from CSV export issues
5. Structural problems from matrix question flattening

Do NOT fix grammar, spelling, capitalization, or language style - preserve the original author's wording completely.

Common conversion errors to check:
- Rating scales (1-5, 1-10) should be QuestionLinearScale, not QuestionMultipleChoice
- Agree/disagree statements should be QuestionLikertFive, not QuestionMultipleChoice
- Yes/No questions should be QuestionYesNo, not QuestionMultipleChoice
- Open text should be QuestionFreeText, not QuestionMultipleChoice
- Incomplete option lists (e.g., [3,5] instead of [1,2,3,4,5] for a 1-5 scale)

Provide your analysis focusing only on technical conversion artifacts that need fixing.

IMPORTANT: Only suggest question types that are listed in the EDSL Question Info below. Do not suggest any question types that are not explicitly documented below.

EDSL Question Info:
{edsl_info}

CRITICAL: Your suggested_type field must ONLY contain question types that appear in the "Question Type:" sections above. Do not suggest any other question types.
"""
