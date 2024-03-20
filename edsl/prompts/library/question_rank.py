"""Rank question type."""
import textwrap

from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class Rank(QuestionInstuctionsBase):
    """Rank question type."""

    question_type = "rank"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting the numbers of the options in order of preference,
        with the most preferred option first, and the least preferred option last:
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        Exactly {{num_selections}} options must be selected.
        """
    )
