from __future__ import annotations
import random
from typing import Any, Optional, Union

from jinja2 import Template

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import (
    IntegerDescriptor,
    QuestionOptionsDescriptor,
)

from edsl.questions.decorators import inject_exception

from pydantic import field_validator
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse

from edsl.exceptions import QuestionAnswerValidationError

from pydantic import BaseModel, Field, conlist
from typing import List, Literal, Optional, Annotated


def create_checkbox_response_model(
    choices: list,
    min_selections: Optional[int] = None,
    max_selections: Optional[int] = None,
    permissive: bool = False,
):
    """
    Dynamically create a CheckboxResponse model with a predefined list of choices.

    :param choices: A list of allowed values for the answer field.
    :param include_comment: Whether to include a comment field in the model.
    :return: A new Pydantic model class.
    """
    # Convert the choices list to a tuple for use with Literal
    choice_tuple = tuple(choices)

    field_params = {}
    if min_selections is not None and not permissive:
        field_params["min_items"] = min_selections
    if max_selections is not None and not permissive:
        field_params["max_items"] = max_selections

    class CheckboxResponse(BaseModel):
        answer: Annotated[
            List[Literal[choice_tuple]],
            Field(..., **field_params),
        ] = Field(..., description="List of selected choices")
        comment: Optional[str] = Field(None, description="Optional comment field")
        generated_tokens: Optional[Any] = Field(default=None)

        class Config:
            @staticmethod
            def json_schema_extra(schema: dict, model: BaseModel) -> None:
                # Add the list of choices to the schema for better documentation
                for prop in schema.get("properties", {}).values():
                    if prop.get("title") == "answer":
                        prop["items"] = {"enum": choices}

    return CheckboxResponse


class CheckBoxResponseValidator(ResponseValidatorABC):
    required_params = [
        "question_options",
        "min_selections",
        "max_selections",
        "use_code",
        "permissive",
    ]

    valid_examples = [
        ({"answer": [1, 2]}, {"question_options": ["Good", "Great", "OK", "Bad"]})
    ]

    invalid_examples = [
        (
            {"answer": [-1]},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Answer code must be a non-negative integer",
        ),
        (
            {"answer": 1},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Answer code must be a list",
        ),
        (
            {"answer": [1, 2, 3, 4]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "min_selections": 1,
                "max_selections": 2,
            },
            "Too many options selected",
        ),
    ]

    def fix(self, response, verbose=False):
        if verbose:
            print("Invalid response of QuestionCheckBox was: ", response)
        response_text = response.get("generated_tokens")
        if response_text is None or response_text == "":  # nothing to be done
            return response
        # Maybe it's a comma separated list?
        proposed_list = response_text.split(",")
        proposed_list = [item.strip() for item in proposed_list]
        if verbose:
            print("Using code? ", self.use_code)
        if self.use_code:
            try:
                proposed_list = [int(i) for i in proposed_list]
            except ValueError:
                # print("Could not convert to int")
                pass

        if verbose:
            print("Proposed solution is: ", proposed_list)

        # print(f"Ivalid generated tokens was was: {response_text}")
        if "comment" in response:
            proposed_data = {
                "answer": proposed_list,
                "comment": response["comment"],
                "generated_tokens": response.get("generated_tokens", None),
            }
        else:
            proposed_data = {
                "answer": proposed_list,
                "generated_tokens": response.get("generated_tokens", None),
            }

        try:
            self.response_model(**proposed_data)
            print("Proposed solution is valid")
            print("Returning proposed data: ", proposed_data)
            return proposed_data
        except Exception as e:
            if verbose:
                print(f"Proposed solution {proposed_data} is invalid. Error: {e}")
            # return response
        if verbose:
            print("Now seeing if responses show up in the answer")
        matches = []
        for index, option in enumerate(self.question_options):
            if self.use_code:
                if str(index) in response_text:
                    matches.append(index)
            else:
                if option in response_text:
                    matches.append(index)
        proposed_data = {
            "answer": matches,
            "comment": response.get("comment", None),
            "generated_tokens": response.get("generated_tokens", None),
        }
        try:
            self.response_model(**proposed_data)
            return proposed_data
        except Exception as e:
            if verbose:
                print(f"Proposed solution {proposed_data} is invalid. Error: {e}")
            return response

    def custom_validate(self, response) -> BaseResponse:
        if response.answer is None:
            raise QuestionAnswerValidationError("Answer is missing.")
        return response.dict()


class QuestionCheckBox(QuestionBase):
    """This question prompts the agent to select options from a list."""

    question_type = "checkbox"
    purpose = "When options are known and limited"
    question_options: list[str] = QuestionOptionsDescriptor()
    min_selections = IntegerDescriptor(none_allowed=True)
    max_selections = IntegerDescriptor(none_allowed=True)

    _response_model = None
    response_validator_class = CheckBoxResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        include_comment: bool = True,
        use_code: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
    ):
        """Instantiate a new QuestionCheckBox.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the respondent should select from.
        :param min_selections: The minimum number of options that must be selected.
        :param max_selections: The maximum number of options that must be selected.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.min_selections = min_selections
        self.max_selections = max_selections
        self.question_options = question_options

        self._include_comment = include_comment
        self._use_code = use_code
        self.permissive = permissive

        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions

    def create_response_model(self):
        if not self._use_code:
            return create_checkbox_response_model(
                self.question_options,
                min_selections=self.min_selections,
                max_selections=self.max_selections,  # include_comment=self._include_comment
                permissive=self.permissive,
            )
        else:
            return create_checkbox_response_model(
                list(range(len(self.question_options))),
                min_selections=self.min_selections,
                max_selections=self.max_selections,  # include_comment=self._include_comment
                permissive=self.permissive,
            )

    def _translate_answer_code_to_answer(
        self, answer_codes, scenario: "Scenario" = None
    ):
        """
        Translate the answer code to the actual answer.

        For example, for question options ["a", "b", "c"],the answer codes are 0, 1, and 2.
        The LLM will respond with [0,1] and this code will translate it to ["a","b"].
        """
        from edsl.scenarios.Scenario import Scenario

        scenario = scenario or Scenario()
        translated_options = [
            Template(str(option)).render(scenario) for option in self.question_options
        ]
        translated_codes = []
        for answer_code in answer_codes:
            if self._use_code:
                translated_codes.append(translated_options[int(answer_code)])
            else:
                translated_codes.append(answer_code)
        return translated_codes

    # def _simulate_answer(self, human_readable=True) -> dict[str, Union[int, str]]:
    #     """Simulate a valid answer for debugging purposes."""
    #     from edsl.utilities.utilities import random_string

    #     min_selections = self.min_selections or 1
    #     max_selections = self.max_selections or len(self.question_options)
    #     num_selections = random.randint(min_selections, max_selections)
    #     if human_readable:
    #         # Select a random number of options from self.question_options
    #         selected_options = random.sample(self.question_options, num_selections)
    #         answer = {
    #             "answer": selected_options,
    #             "comment": random_string(),
    #         }
    #     else:
    #         # Select a random number of indices from the range of self.question_options
    #         selected_indices = random.sample(
    #             range(len(self.question_options)), num_selections
    #         )
    #         answer = {
    #             "answer": selected_indices,
    #             "comment": random_string(),
    #         }
    #     return answer

    @property
    def question_html_content(self) -> str:
        instructions = ""
        if self.min_selections is not None:
            instructions += f"Select at least {self.min_selections} option(s). "
        if self.max_selections is not None:
            instructions += f"Select at most {self.max_selections} option(s)."
        question_html_content = Template(
            """
        <p>{{ instructions }}</p>
        {% for option in question_options %} 
        <div>
        <input type="checkbox" id="{{ option }}" name="{{ question_name }}" value="{{ option }}">
        <label for="{{ option }}">{{ option }}</label>
        </div>
        {% endfor %}
        """
        ).render(
            instructions=instructions,
            question_name=self.question_name,
            question_options=self.question_options,
        )
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    @inject_exception
    def example(cls, include_comment=False, use_code=True) -> QuestionCheckBox:
        """Return an example checkbox question."""
        return cls(
            question_name="never_eat",
            question_text="Which of the following foods would you eat if you had to?",
            question_options=[
                "soggy meatpie",
                "rare snails",
                "mouldy bread",
                "panda milk custard",
                "McDonalds",
            ],
            min_selections=2,
            max_selections=5,
            use_code=use_code,
            include_comment=include_comment,
        )


def main():
    """Create an example QuestionCheckBox and test its methods."""
    from edsl.questions.QuestionCheckBox import QuestionCheckBox

    q = QuestionCheckBox.example()
    q.question_text
    q.question_options
    q.question_name
    # validate an answer
    q._validate_answer({"answer": [1, 2], "comment": "I like custard"})
    # translate answer code
    q._translate_answer_code_to_answer([1, 2])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
