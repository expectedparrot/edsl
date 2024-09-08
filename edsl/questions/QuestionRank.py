from __future__ import annotations
import random
import textwrap
from jinja2 import Template
from typing import Any, Optional, Union
from edsl.questions.QuestionBase import QuestionBase
from edsl.exceptions import QuestionAnswerValidationError

from edsl.questions.descriptors import (
    QuestionOptionsDescriptor,
    NumSelectionsDescriptor,
)

from edsl.prompts import Prompt

from pydantic import field_validator
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse
from edsl.exceptions import QuestionAnswerValidationError

from pydantic import BaseModel, Field, create_model
from typing import Optional, Any, List, Annotated, Literal


def create_response_model(
    choices: list,
    num_selections: Optional[int] = None,
    permissive: bool = False,
):
    """
    :param choices: A list of allowed values for the answer field.
    :param include_comment: Whether to include a comment field in the model.
    :return: A new Pydantic model class.
    """
    # Convert the choices list to a tuple for use with Literal
    choice_tuple = tuple(choices)

    field_params = {}
    if num_selections is not None and not permissive:
        field_params["min_items"] = num_selections
        field_params["max_items"] = num_selections

    class RankResponse(BaseModel):
        answer: Annotated[
            List[Literal[choice_tuple]],
            Field(..., **field_params),
        ] = Field(..., description="List of selected choices")
        comment: Optional[str] = Field(None, description="Optional comment field")
        generated_tokens: Optional[Any] = Field(None)

        class Config:
            @staticmethod
            def json_schema_extra(schema: dict, model: BaseModel) -> None:
                # Add the list of choices to the schema for better documentation
                for prop in schema.get("properties", {}).values():
                    if prop.get("title") == "answer":
                        prop["items"] = {"enum": choices}

    return RankResponse


class RankResponseValidator(ResponseValidatorABC):
    required_params = ["num_selections", "permissive", "use_code", "question_options"]
    valid_examples = []
    invalid_examples = []

    def fix(self, response, verbose=False):
        if verbose:
            print("Invalid response of QuestionRank was: ", False)
        response_text = response.get("generated_tokens")
        if response_text is None or response_text == "":  # nothing to be done
            return response
        # Maybe it's a comma separated list?
        response_text = str(response.get("answer"))
        proposed_list = (
            response_text.replace("[", "").replace("]", "").replace("'", "").split(",")
        )
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
                    if index not in matches:
                        matches.append(index)
            else:
                if option in response_text:
                    if option not in matches:
                        matches.append(option)
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


class QuestionRank(QuestionBase):
    """This question prompts the agent to rank options from a list."""

    question_type = "rank"
    question_options: list[str] = QuestionOptionsDescriptor()
    num_selections = NumSelectionsDescriptor()

    _response_model = None
    response_validator_class = RankResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        num_selections: Optional[int] = None,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
        use_code: bool = True,
        include_comment: bool = True,
    ):
        """Initialize the question.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the respondent should select from.
        :param min_selections: The minimum number of options that must be selected.
        :param max_selections: The maximum number of options that must be selected.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.num_selections = num_selections or len(question_options)
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions
        self.permissive = permissive
        self.use_code = use_code
        self.include_comment = include_comment

    def create_response_model(self):
        choices = (
            self.question_options
            if not self.use_code
            else range(len(self.question_options))
        )
        return create_response_model(
            choices=choices,
            num_selections=self.num_selections,
            permissive=self.permissive,
        )

    ################
    # Answer methods
    ################
    # def _validate_answer(self, answer: Any) -> dict[str, list[int]]:
    #     """Validate the answer."""
    #     self._validate_answer_template_basic(answer)
    #     self._validate_answer_key_value(answer, "answer", list)
    #     self._validate_answer_rank(answer)
    #     return answer

    def _translate_answer_code_to_answer(
        self, answer_codes, scenario: Scenario = None
    ) -> list[str]:
        """Translate the answer code to the actual answer."""
        from edsl.scenarios import Scenario

        scenario = scenario or Scenario()
        translated_options = [
            Template(option).render(scenario) for option in self.question_options
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

    #     if human_readable:
    #         selected = random.sample(self.question_options, self.num_selections)
    #     else:
    #         selected = random.sample(
    #             range(len(self.question_options)), self.num_selections
    #         )
    #     answer = {
    #         "answer": selected,
    #         "comment": random_string(),
    #     }
    #     return answer

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        question_html_content = Template(
            """
        <form id="rankForm">
            <p>{{ question_text }}</p>
            {% for option in question_options %}
            <div>
                <label for="{{ option }}">{{ option }}</label>
                <input type="number" id="{{ option }}" name="{{ question_name }}[{{ option }}]" value="0" min="1" max="{{ question_options|length }}" oninput="updateRankings()">
            </div>
            {% endfor %}
        </form>
        <script>
        function updateRankings() {
            let options = {{ question_options|length }};
            let values = [];
            let isValid = true;

            {% for option in question_options %}
            let value = parseInt(document.getElementById("{{ option }}").value) || 0;
            if (value > 0 && value <= options && !values.includes(value)) {
                values.push(value);
            } else if (value !== 0) {
                isValid = false;
            }
            {% endfor %}

            if (!isValid || values.length !== new Set(values).size) {
                document.getElementById("error").innerText = "Please enter unique and valid ranks for each option.";
            } else {
                document.getElementById("error").innerText = "";
            }
        }
        </script>
        <p id="error" style="color: red;"></p>
        """
        ).render(
            question_name=self.question_name,
            question_text=self.question_text,
            question_options=self.question_options,
        )
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls, use_code=False, include_comment=True) -> QuestionRank:
        """Return an example question."""
        return cls(
            question_name="rank_foods",
            question_text="Rank your favorite foods.",
            question_options=["Pizza", "Pasta", "Salad", "Soup"],
            num_selections=2,
            use_code=use_code,
            include_comment=include_comment,
        )


def main():
    """Show example usage."""
    from edsl.questions.QuestionRank import QuestionRank

    q = QuestionRank.example(use_code=True)
    q.question_text
    q.question_name
    q.question_options
    q.num_selections
    # validate an answer
    answer = {"answer": [0, 1], "comment": "I like pizza and pasta."}
    q._validate_answer(answer)
    # translate an answer code to an answer
    # q._translate_answer_code_to_answer([0, 1])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    q = QuestionRank.example(use_code=False)
    answer = {"answer": ["Pizza", "Pasta"], "comment": "I like pizza and pasta."}
    q._validate_answer(answer)

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
