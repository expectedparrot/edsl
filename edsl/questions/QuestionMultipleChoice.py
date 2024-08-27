from __future__ import annotations
from typing import Union, Literal, Optional
from jinja2 import Template

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.decorators import inject_exception

from pydantic import field_validator
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse

from edsl.exceptions import QuestionAnswerValidationError

from pydantic import BaseModel, Field, create_model


def create_response_model_code(
    min_value: int, max_value: int, include_comment: bool = True
):
    """
    Dynamically create a RestrictedMultipleChoiceResponse model with custom min and max values.

    :param min_value: The minimum allowed value for the answer field.
    :param max_value: The maximum allowed value for the answer field.
    :return: A new Pydantic model class.
    """
    if include_comment:
        return create_model(
            "DynamicRestrictedMultipleChoiceResponse",
            answer=(int, Field(..., ge=min_value, le=max_value)),
            comment=(str, ""),
            __base__=BaseModel,
        )
    else:
        return create_model(
            "DynamicRestrictedMultipleChoiceResponse",
            answer=(int, Field(..., ge=min_value, le=max_value)),
            __base__=BaseModel,
        )


def create_response_model_no_code(choices: list, include_comment: bool = True):
    """
    Dynamically create a MultipleChoiceResponse model with a predefined list of choices.

    :param choices: A list of allowed values for the answer field.
    :return: A new Pydantic model class.
    """
    # Convert the choices list to a tuple for use with Literal
    choice_tuple = tuple(choices)

    class MultipleChoiceResponse(BaseModel):
        answer: Literal[choice_tuple] = Field(
            ..., description="Must be one of the predefined choices"
        )
        comment: Optional[str] = Field(None, description="Optional comment field")

        class Config:
            @staticmethod
            def json_schema_extra(schema: dict, model: BaseModel) -> None:
                # Add the list of choices to the schema for better documentation
                for prop in schema.get("properties", {}).values():
                    if "allOf" in prop:
                        prop["enum"] = choices

        @classmethod
        def with_comment(cls):
            return cls

        @classmethod
        def without_comment(cls):
            return cls.model_exclude({"comment"})

    if include_comment:
        return MultipleChoiceResponse.with_comment()
    else:
        return MultipleChoiceResponse.without_comment()


class MultipleChoiceResponseValidator(ResponseValidatorABC):
    required_params = ["question_options"]

    valid_examples = [
        ({"answer": 1}, {"question_options": ["Good", "Great", "OK", "Bad"]})
    ]

    invalid_examples = [
        (
            {"answer": -1},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Answer code must be a non-negative integer",
        ),
        (
            {"answer": None},
            {"question_options": ["Good", "Great", "OK", "Bad"]},
            "Answer code must not be missing.",
        ),
    ]

    def custom_validate(self, response) -> BaseResponse:
        return response.dict()


class QuestionMultipleChoice(QuestionBase):
    """This question prompts the agent to select one option from a list of options.

    https://docs.expectedparrot.com/en/latest/questions.html#questionmultiplechoice-class

    """

    question_type = "multiple_choice"
    purpose = "When options are known and limited"
    question_options: Union[list[str], list[list], list[float], list[int]] = (
        QuestionOptionsDescriptor()
    )
    _response_model = None
    response_validator_class = MultipleChoiceResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: Union[list[str], list[list], list[float], list[int]],
        include_comment: bool = True,
        use_code: bool = False,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """Instantiate a new QuestionMultipleChoice.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the agent should select from.

        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options

        self._include_comment = include_comment
        self.use_code = use_code
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    ################
    # Answer methods
    ################

    def create_response_model(self):
        if self._use_code:
            response_model = create_response_model_code(
                0, len(self.question_options) - 1, self._include_comment
            )
        else:
            response_model = create_response_model_no_code(
                self.question_options, self._include_comment
            )
        return response_model

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
        if self._use_code:
            return translated_options[int(answer_code)]
        else:
            # return translated_options[answer_code]
            return answer_code

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
    @inject_exception
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
