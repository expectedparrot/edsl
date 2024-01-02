import random
import textwrap
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Type, Union
from edsl.questions import Question, QuestionData, AnswerData, Settings
from edsl.exceptions import QuestionAnswerValidationError
from edsl.utilities.utilities import random_string


class QuestionBudget(QuestionData):
    """Pydantic data model for QuestionBudget"""

    question_options: list[str] = Field(
        ...,
        min_length=Settings.MIN_NUM_OPTIONS,
        max_length=Settings.MAX_NUM_OPTIONS,
    )
    budget_sum: int

    def __new__(cls, *args, **kwargs) -> "QuestionBudgetEnhanced":
        # see QuestionFreeText for an explanation of how __new__ works
        instance = super(QuestionBudget, cls).__new__(cls)
        instance.__init__(*args, **kwargs)
        return QuestionBudgetEnhanced(instance)

    def __init__(self, **data):
        super().__init__(**data)

    @field_validator("question_options")
    def check_unique(cls, value):
        return cls.base_validator_check_unique(value)

    @field_validator("question_options")
    def check_option_string_lengths(cls, value):
        return cls.base_validator_check_option_string_lengths(value)


class QuestionBudgetEnhanced(Question):
    question_type = "budget"

    def __init__(self, question: BaseModel):
        super().__init__(question)

    @property
    def instructions(self):
        return textwrap.dedent(
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

    def construct_answer_data_model(self) -> Type[BaseModel]:
        budget_sum = self.budget_sum
        acceptable_answer_keys = set(range(len(self.question_options)))

        class QuestionBudgetAnswerDataModel(AnswerData):
            answer: dict[int, Union[int, float]]

            @model_validator(mode="after")
            def check_answer(self):
                current_sum = sum(self.answer.values())
                if not current_sum == budget_sum:
                    raise QuestionAnswerValidationError(
                        f"Budget sum must be {budget_sum}, but got {current_sum}."
                    )
                if any(v < 0 for v in self.answer.values()):
                    raise QuestionAnswerValidationError(
                        f"Budget values must be positive, but got {self.answer.keys()}."
                    )
                if any(
                    [key not in acceptable_answer_keys for key in self.answer.keys()]
                ):
                    raise QuestionAnswerValidationError(
                        f"Budget keys must be in {acceptable_answer_keys}, but got {self.answer.keys()}"
                    )
                if acceptable_answer_keys != set(self.answer.keys()):
                    missing_keys = acceptable_answer_keys - set(self.answer.keys())
                    raise QuestionAnswerValidationError(
                        f"All but keys must be represented in the answer. Missing: {missing_keys}"
                    )
                return self

        return QuestionBudgetAnswerDataModel

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

    def form_elements(self):
        html_output = f"""
        <label>{self.question_text}</label>
        <p>Total Budget: {self.budget_sum}</p>\n"""
        for index, option in enumerate(self.question_options):
            html_output += f"""
            <div id="{self.question_name}_div_{index}">
                <label for="{self.question_name}_{index}">{option}</label>
                <input type="number" id="{self.question_name}_{index}" 
                    name="{self.question_name}_{index}" 
                    min="0" max="{self.budget_sum}" 
                    oninput="validateBudget(this, {self.budget_sum})">
            </div>\n"""

        html_output += f"""
        <script>
            function validateBudget(input, maxBudget) {{
                let total = 0;
                let inputs = document.querySelectorAll('input[type=number]');
                inputs.forEach(el => total += Number(el.value));
                if (total > maxBudget) {{
                    alert('Total allocation exceeds the budget!');
                    input.value = '';
                }}
            }}
        </script>
        """
        return html_output


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
