"""Checkbox question type."""
import textwrap
from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class Matrix(QuestionInstuctionsBase):
    """Checkbox question type."""

    question_type = "matrix"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The items are:
        {% for option in question_items %}
        - {{option}}
        {% endfor %}
        For each of theses items choose one of the following options:
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        """
    )

