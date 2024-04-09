"""Free text question type."""
import textwrap
from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class FreeText(QuestionInstuctionsBase):
    """Free text question type."""

    question_type = "free_text"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this:
        {"answer": "<put free text answer here>"}
        """
    )
