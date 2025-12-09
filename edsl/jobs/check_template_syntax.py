"""Module for validating template syntax in surveys."""

import re
from typing import TYPE_CHECKING
from .exceptions import JobsCompatibilityError

if TYPE_CHECKING:
    from ..surveys.survey import Survey


class CheckTemplateSyntax:
    """Validates that templates use correct syntax for scenario and agent references."""

    def __init__(self, survey: "Survey"):
        self.survey = survey

    def check(self) -> None:
        """Check if templates use correct syntax ({{scenario.field}}, {{agent.field}}, or {{question_name.field}}).

        Raises:
            JobsCompatibilityError: If incorrect template syntax is found
        """
        # Pattern to find any {{variable.field}} syntax
        pattern = re.compile(r"\{\{\s*(\w+)\.(\w+)\s*\}\}")

        # Get all question names in the survey
        question_names = {q.question_name for q in self.survey.questions}

        for question in self.survey.questions:
            # Get all text that might contain templates
            text_to_check = question._all_text()

            # Find all matches of {{variable.field}} pattern
            matches = pattern.findall(text_to_check)

            for var_name, field_name in matches:
                # Check if the variable name is not 'scenario', 'agent', and not a question name
                if (
                    var_name not in {"scenario", "agent"}
                    and var_name not in question_names
                ):
                    # Try to find a similar question name (likely misspelled)
                    closest_question = self._find_closest_question_name(
                        var_name, question_names
                    )

                    if closest_question:
                        error_msg = (
                            f"Invalid template syntax in question '{question.question_name}':\n\n"
                            f"Found: '{{{{{var_name}.{field_name}}}}}'\n"
                            f"Did you mean: '{{{{{closest_question}.{field_name}}}}}'?\n\n"
                            f"Make sure question names are spelled correctly."
                        )
                    else:
                        error_msg = (
                            f"Invalid template syntax in question '{question.question_name}':\n\n"
                            f"Found: '{{{{{var_name}.{field_name}}}}}'\n"
                            f"Problem: '{var_name}' is not a valid reference.\n\n"
                            f"If you're trying to reference a scenario field:\n"
                            f"  Use: '{{{{scenario.{field_name}}}}}'\n\n"
                            f"If you're trying to reference an agent field:\n"
                            f"  Use: '{{{{agent.{field_name}}}}}'\n\n"
                            f"If you're trying to reference a question answer:\n"
                            f"  Make sure the question name is spelled correctly and exists in the survey.\n"
                            f"  Available questions: {sorted(question_names)}"
                        )

                    raise JobsCompatibilityError(error_msg)

    def _find_closest_question_name(
        self, misspelled_name: str, question_names: set
    ) -> str:
        """Find the closest matching question name using simple string similarity."""
        import difflib

        # Use difflib to find the closest match
        closest_matches = difflib.get_close_matches(
            misspelled_name, question_names, n=1, cutoff=0.6  # Similarity threshold
        )

        return closest_matches[0] if closest_matches else None
