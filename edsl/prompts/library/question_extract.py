"""Extract question type."""
import textwrap

from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class Extract(QuestionInstuctionsBase):
    """Extract question type."""

    question_type = "extract"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are given the following input: "{{question_text}}".
        Create an ANSWER should be formatted like this: "{{ answer_template }}",
        and it should have the same keys but values extracted from the input.
        If the value of a key is not present in the input, fill with "null".
        Return a valid JSON formatted like this:
        {"answer": <put your ANSWER here>}
        ONLY RETURN THE JSON, AND NOTHING ELSE.
        """
    )
