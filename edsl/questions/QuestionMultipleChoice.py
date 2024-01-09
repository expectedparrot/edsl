import random
import textwrap
from jinja2 import Template

from typing import Optional, List, Dict
from edsl.questions import Question
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string

from edsl.questions.ValidatorMixin import ValidatorMixin


class QuestionMultipleChoice(Question, ValidatorMixin):
    """QuestionMultipleChoice"""

    question_type = "multiple_choice"

    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting only the number of the option: 
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )

    def __init__(
        self,
        question_text: str,
        question_options: List[str],
        question_name: str,
        short_names_dict: Optional[Dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        self.question_text = question_text
        self.question_options = question_options
        self.question_name = question_name

        if short_names_dict is None:
            short_names_dict = dict()
            self.set_short_names_dict = False
        else:
            self.set_short_names_dict = True
            self.short_names_dict = short_names_dict

        if instructions is None:
            self.instructions = self.default_instructions
            # used to decide if instructions should be serialized
            self.set_instructions = False
        else:
            self.instructions = instructions
            self.set_instructions = True

    #############
    ## Validators
    #############

    @property
    def question_name(self):
        return self._question_name

    @question_name.setter
    def question_name(self, value):
        self._question_name = self.validate_question_name(value)

    @property
    def question_text(self):
        return self._question_text

    @question_text.setter
    def question_text(self, value):
        self._question_text = self.validate_question_text(value)

    @property
    def question_options(self):
        return self._question_options

    @question_options.setter
    def question_options(self, value):
        self._question_options = self.validate_question_options(value)

    @property
    def short_names_dict(self):
        return self._short_names_dict

    @short_names_dict.setter
    def short_names_dict(self, value):
        self._short_names_dict = self.validate_short_names_dict(value)

    @property
    def instructions(self):
        return self._instructions

    @instructions.setter
    def instructions(self, value):
        self._instructions = self.validate_instructions(value)

    def validate_answer(self, answer: dict[str, str]):
        """Validates the answer"""
        try:
            answer_code = int(answer["answer"])
        except:
            raise QuestionAnswerValidationError(
                f"Answer {answer} is not a valid option."
            )
        if int(answer["answer"]) not in range(len(self.question_options)):
            raise QuestionAnswerValidationError(
                f"Answer {answer} is not a valid option."
            )
        return answer

    ################
    # Less important
    ################

    def translate_answer_code_to_answer(self, answer_code, scenario=None):
        """
        Translates the answer code to the actual answer.
        For example, for question_options ["a", "b", "c"], the answer codes are 0, 1, and 2.
        The LLM will respond with 0, and this code will translate that to "a".
        # TODO: REMOVE
        >>> q = QuestionMultipleChoice(question_text = "How are you?", question_options = ["Good", "Great", "OK", "Bad"], question_name = "how_feeling")
        >>> q.translate_answer_code_to_answer(0, {})
        'Good'
        """
        scenario = scenario or dict()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        return translated_options[int(answer_code)]

    def simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Simulates a valid answer for debugging purposes"""
        if human_readable:
            answer = random.choice(self.question_options)
        else:
            answer = random.choice(range(len(self.question_options)))
        return {
            "answer": answer,
            "comment": random_string(),
        }


if __name__ == "__main__":
    q = QuestionMultipleChoice(
        question_text="How are you?",
        question_options={"OK": "OK", "BAD": "BAD"},
        question_name="how_feeling",
    )
    # q = QuestionMultipleChoice(
    #     question_text="Do you enjoying eating custard while skydiving?",
    #     question_options=["yes, somtimes", "no", "only on Tuesdays"],
    #     question_name="goose_fight",
    # )
    # results = q.run()
    # results.select("goose_fight").print()

    # q_dict = q.to_dict()
    # print(f"Serialized dictionary:{q_dict}")
    # new_q = Question.from_dict(q_dict)
