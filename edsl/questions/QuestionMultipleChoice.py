import random
import textwrap
from jinja2 import Template

from typing import Optional, Type
from edsl.questions import Question
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string
from edsl.utilities.utilities import is_valid_variable_name

MAX_OPTIONS = 10
MIN_OPTIONS = 2


class QuestionMultipleChoice(Question):
    """QuestionMultipleChoice"""

    question_type = "multiple_choice"

    def __init__(
        self, question_text, question_options, question_name, short_names_dict=None
    ):
        self.question_text = question_text
        self.question_options = question_options
        self.question_name = question_name
        self.short_names_dict = short_names_dict or dict()

    @property
    def question_name(self):
        return self._question_name

    @question_name.setter
    def question_name(self, new_question_name):
        "Validates the question name"
        if not is_valid_variable_name(new_question_name):
            raise Exception("Question name is not a valid variable name!")
        self._question_name = new_question_name

    @property
    def question_options(self):
        return self._question_options

    @question_options.setter
    def question_options(self, new_question_options):
        "Validates the question options"
        if not isinstance(new_question_options, list):
            raise Exception("Question options must be a list!")
        if len(new_question_options) > MAX_OPTIONS:
            raise Exception("Question options are too long!")
        if len(new_question_options) < MIN_OPTIONS:
            raise Exception("Question options are too short!")
        if not all(isinstance(x, str) for x in new_question_options):
            raise Exception("Question options must be strings!")
        if len(new_question_options) != len(set(new_question_options)):
            raise Exception("Question options must be unique!")
        if not all([len(option) > 1 for option in new_question_options]):
            raise Exception("All question options must be at least 2 characters long!")
        self._question_options = new_question_options

    @property
    def question_text(self):
        return self._question_text

    @question_text.setter
    def question_text(self, new_question_text):
        "Validates the question text"
        if len(new_question_text) > 1000:
            raise Exception("Question is too long!")
        if len(new_question_text) < 1:
            raise Exception("Question is too short!")
        if not isinstance(new_question_text, str):
            raise Exception("Question must be a string!")
        self._question_text = new_question_text

    @property
    def short_names_dict(self):
        return self._short_names_dict

    @short_names_dict.setter
    def short_names_dict(self, new_short_names_dict):
        "Validates the short names dictionary"
        if not isinstance(new_short_names_dict, dict):
            raise Exception("Short names dictionary must be a dictionary!")
        if not all(isinstance(x, str) for x in new_short_names_dict.keys()):
            raise Exception("Short names dictionary keys must be strings!")
        if not all(isinstance(x, str) for x in new_short_names_dict.values()):
            raise Exception("Short names dictionary values must be strings!")
        self._short_names_dict = new_short_names_dict

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

    @property
    def instructions(self) -> str:
        return textwrap.dedent(
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
