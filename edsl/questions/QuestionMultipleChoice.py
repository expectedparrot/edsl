from __future__ import annotations
import time
from typing import Union
import random
from typing import Optional
from jinja2 import Template

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import QuestionOptionsDescriptor


class QuestionMultipleChoice(QuestionBase):
    """This question prompts the agent to select one option from a list of options.

    https://docs.expectedparrot.com/en/latest/questions.html#questionmultiplechoice-class

    """

    question_type = "multiple_choice"
    purpose = "When options are known and limited"
    question_options: Union[
        list[str], list[list], list[float], list[int]
    ] = QuestionOptionsDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Union[list[str], list[list], list[float], list[int]],
    ):
        """Instantiate a new QuestionMultipleChoice.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the agent should select from.
        :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionMultipleChoice.default_instructions`.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options

    # @property
    # def question_options(self) -> Union[list[str], list[list], list[float], list[int]]:
    #     """Return the question options."""
    #     return self._question_options

    ################
    # Answer methods
    ################
    def _validate_answer(
        self, answer: dict[str, Union[str, int]]
    ) -> dict[str, Union[str, int]]:
        """Validate the answer.

        >>> q = QuestionMultipleChoice.example()
        >>> q._validate_answer({"answer": 0, "comment": "I like custard"})
        {'answer': 0, 'comment': 'I like custard'}

        >>> q = QuestionMultipleChoice(question_name="how_feeling", question_text="How are you?", question_options=["Good", "Great", "OK", "Bad"])
        >>> q._validate_answer({"answer": -1, "comment": "I like custard"})
        Traceback (most recent call last):
        ...
        edsl.exceptions.questions.QuestionAnswerValidationError: Answer code must be a non-negative integer (got -1).
        """
        self._validate_answer_template_basic(answer)
        self._validate_answer_multiple_choice(answer)
        return answer

    def _translate_answer_code_to_answer(
        self, answer_code: int, scenario: Optional["Scenario"] = None
    ):
        """Translate the answer code to the actual answer.

        It is used to translate the answer code to the actual answer.
        The question options might be templates, so they need to be rendered with the scenario.

        >>> q = QuestionMultipleChoice.example()
        >>> q._translate_answer_code_to_answer(0, {})
        'Good'

        >>> q = QuestionMultipleChoice(question_name="how_feeling", question_text="How are you?", question_options=["{{emotion[0]}}", "emotion[1]"])
        >>> q._translate_answer_code_to_answer(0, {"emotion": ["Happy", "Sad"]})
        'Happy'

        """
        from edsl.scenarios.Scenario import Scenario

        scenario = scenario or Scenario()

        if isinstance(self.question_options, str):
            # If dynamic options are provided like {{ options }}, render them with the scenario
            from jinja2 import Environment, meta

            env = Environment()
            parsed_content = env.parse(self.question_options)
            question_option_key = list(meta.find_undeclared_variables(parsed_content))[
                0
            ]
            translated_options = scenario.get(question_option_key)
        else:
            translated_options = [
                Template(str(option)).render(scenario)
                for option in self.question_options
            ]
        # print("Translated options:", translated_options)
        # breakpoint()
        return translated_options[int(answer_code)]

    def _simulate_answer(
        self, human_readable: bool = True
    ) -> dict[str, Union[int, str]]:
        """Simulate a valid answer for debugging purposes."""
        from edsl.utilities.utilities import random_string

        if human_readable:
            answer = random.choice(self.question_options)
        else:
            answer = random.choice(range(len(self.question_options)))
        return {
            "answer": answer,
            "comment": random_string(),
        }

    @property
    def question_html_content(self) -> str:
        """Return the HTML version of the question."""
        if hasattr(self, "option_labels"):
            option_labels = self.option_labels
        else:
            option_labels = {}
        question_html_content = Template(
            """
        {% for option in question_options %} 
        <div>
        <input type="radio" id="{{ option }}" name="{{ question_name }}" value="{{ option }}">
        <label for="{{ option }}">
        {{ option }}
        {% if option in option_labels %}
        : {{ option_labels[option] }}
        {% endif %}
        </label>
        </div>
        {% endfor %}
        """
        ).render(
            question_name=self.question_name,
            question_options=self.question_options,
            option_labels=option_labels,
        )
        return question_html_content

    ################
    # Example
    ################
    @classmethod
    def example(cls) -> QuestionMultipleChoice:
        """Return an example instance."""
        return cls(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
        )


def main():
    """Create an example QuestionMultipleChoice and test its methods."""
    from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

    q = QuestionMultipleChoice.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer({"answer": 0, "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer(0, {})
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
