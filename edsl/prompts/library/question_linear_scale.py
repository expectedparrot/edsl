"""Linear scale question type."""
import textwrap

from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class LinearScale(QuestionInstuctionsBase):
    """Linear scale question type."""

    question_type = "linear_scale"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting only the code of the option (codes start at 0):
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )
