"""Checkbox question type."""
import textwrap
from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class Matrix(QuestionInstuctionsBase):
    """Matrix question type."""

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
        Your response should be ONLY be a valid JSON in the following format:
        {"answer": [<list of comma-separated integer options>], "comment": "<put explanation here>"}
        The list must contain exactly the same number of answers as items.
        """
    )

