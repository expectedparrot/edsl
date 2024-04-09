"""Checkbox question type."""
import textwrap
from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class CheckBox(QuestionInstuctionsBase):
    """Checkbox question type."""

    question_type = "checkbox"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        {% if min_selections != None and max_selections != None and min_selections == max_selections %}
        You must select exactly {{min_selections}} options.
        {% elif min_selections != None and max_selections != None %}
        Minimum number of options that must be selected: {{min_selections}}.
        Maximum number of options that must be selected: {{max_selections}}.
        {% elif min_selections != None %}
        Minimum number of options that must be selected: {{min_selections}}.
        {% elif max_selections != None %}
        Maximum number of options that must be selected: {{max_selections}}.
        {% endif %}
        """
    )


class TopK(CheckBox):
    """Top K question type."""

    question_type = "top_k"
