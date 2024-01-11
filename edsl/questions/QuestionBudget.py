import random
import textwrap
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question
from edsl.questions.descriptors import IntegerDescriptor, QuestionOptionsDescriptor
from edsl.utilities import random_string


class QuestionBudget(Question):
    """QuestionBudget"""

    question_type = "budget"

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

    budget_sum: int = IntegerDescriptor(none_allowed=False)
    question_options: list[str] = QuestionOptionsDescriptor()

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        budget_sum: int,
        short_names_dict: dict[str, str] = None,
        instructions: str = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.budget_sum = budget_sum
        self.short_names_dict = short_names_dict or dict({})
        self.instructions = instructions or self.default_instructions

    def validate_answer(self, answer_raw):
        budget_sum = self.budget_sum
        acceptable_answer_keys = set(range(len(self.question_options)))

        answer = answer_raw["answer"]
        if answer is None:
            raise QuestionAnswerValidationError("Answer cannot be None.")
        if not isinstance(answer, dict):
            raise QuestionAnswerValidationError(
                f"Answer must be a dictionary, but got {type(answer)}."
            )
        answer_keys = set([int(k) for k in answer.keys()])
        current_sum = sum(answer.values())
        if not current_sum == budget_sum:
            raise QuestionAnswerValidationError(
                f"Budget sum must be {budget_sum}, but got {current_sum}."
            )
        if any(v < 0 for v in answer.values()):
            raise QuestionAnswerValidationError(
                f"Budget values must be positive, but got {answer_keys}."
            )
        if any([int(key) not in acceptable_answer_keys for key in answer.keys()]):
            raise QuestionAnswerValidationError(
                f"Budget keys must be in {acceptable_answer_keys}, but got {answer_keys}"
            )
        if acceptable_answer_keys != answer_keys:
            missing_keys = acceptable_answer_keys - answer_keys
            raise QuestionAnswerValidationError(
                f"All but keys must be represented in the answer. Missing: {missing_keys}"
            )
        return answer_raw

    ################
    # Less important
    ################

    def translate_answer_code_to_answer(
        self, answer_codes: dict[str, int], scenario=None
    ):
        """Translates the answer codes to the actual answers.
        For example, for a budget question with options ["a", "b", "c"],
        the answer codes are 0, 1, and 2. The LLM will respond with 0.
        This code will translate that to "a".
        """
        translated_codes = []
        for answer_code, response in answer_codes.items():
            translated_codes.append({self.question_options[int(answer_code)]: response})

        return translated_codes

    def simulate_answer(self, human_readable=True):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        if human_readable:
            keys = self.question_options
        else:
            keys = range(len(self.question_options))
        values = [random.randint(0, 100) for _ in range(len(self.question_options))]
        current_sum = sum(values)
        modified_values = [v * self.budget_sum / current_sum for v in values]
        answer = dict(zip(keys, modified_values))
        return {
            "answer": answer,
            "comment": random_string(),
        }


# if __name__ == "__main__":
#     # for testing
#     from edsl.questions import QuestionBudget

#     q = QuestionBudget(
#         question_text="How would you allocate $100?",
#         question_options=["Pizza", "Ice Cream", "Burgers", "Salad"],
#         budget_sum=100,
#         question_name="food_budget",
#     )

#     q.formulate_prompt()
#     q.question_options
#     q.simulate_answer()

#     results = q.run()
