"""Budget question instructions."""
import textwrap

from edsl.prompts.QuestionInstructionsBase import QuestionInstuctionsBase


class Budget(QuestionInstuctionsBase):
    """Budget question instructions."""

    question_type = "budget"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted as follows, with a dictionary for your "answer"
        where the keys are the option numbers and the values are the amounts you want 
        to allocate to the options, and the sum of the values is {{budget_sum}}:
        {"answer": {<put dict of option numbers and allocation amounts here>},
        "comment": "<put explanation here>"}
        Example response for a budget of 100 and 4 options: 
        {"answer": {"0": 25, "1": 25, "2": 25, "3": 25},
        "comment": "I allocated 25 to each option."}
        There must be an allocation listed for each item (including 0).
        """
    )
