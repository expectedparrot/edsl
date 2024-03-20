"""Multiple choice question type."""
import textwrap
from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class MultipleChoiceTurbo(QuestionInstuctionsBase):
    """Multiple choice question type."""

    question_type = "multiple_choice"
    model = "gpt-3.5-turbo"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )


class MultipleChoice(QuestionInstuctionsBase):
    """Multiple choice question type."""

    question_type = "multiple_choice"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )


class LikertFive(MultipleChoice):
    """Likert five question type."""

    question_type = "likert_five"


class YesNo(MultipleChoice):
    """Yes/No question type."""

    question_type = "yes_no"
