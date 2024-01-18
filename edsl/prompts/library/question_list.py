import textwrap

from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class ListQuestion(QuestionInstuctionsBase):
    question_type = "list"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        {{question_text}}

        Your response should be only a valid JSON of the following format:
        {
            "answer": <list of comma-separated words or phrases >,
            "comment": "<put comment here>"
        }
        {% if max_list_items is not none %}
        The list must not contain more than {{ max_list_items }} items.
        {% endif %}
    """
    )
