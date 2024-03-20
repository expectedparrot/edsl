"""Numerical question type."""
import textwrap

from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class Numerical(QuestionInstuctionsBase):
    """Numerical question type."""

    question_type = "numerical"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked a question that requires a numerical response
        in the form of an integer or decimal (e.g., -12, 0, 1, 2, 3.45, ...).
        Your response must be in the following format:
        {"answer": "<your numerical answer here>", "comment": "<your explanation here"}
        You must only include an integer or decimal in the quoted "answer" part of your response.
        Here is an example of a valid response:
        {"answer": "100", "comment": "This is my explanation..."}
        Here is an example of a response that is invalid because the "answer" includes words:
        {"answer": "I don't know.", "comment": "This is my explanation..."}
        If your response is equivalent to zero, your formatted response should look like this:
        {"answer": "0", "comment": "This is my explanation..."}

        You are being asked the following question: {{question_text}}
        {% if min_value is not none %}
        Minimum answer value: {{min_value}}
        {% endif %}
        {% if max_value is not none %}
        Maximum answer value: {{max_value}}
        {% endif %}
        """
    )
