from __future__ import annotations
from typing import Union, Literal, Optional, List, Any

from jinja2 import Template
from pydantic import BaseModel, Field

from edsl.scenarios.Scenario import Scenario
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import QuestionOptionsDescriptor
from edsl.questions.decorators import inject_exception
from edsl.questions.ResponseValidatorABC import ResponseValidatorABC


def create_response_model(choices: List[str], permissive: bool = False):
    """
    Create a ChoiceResponse model class with a predefined list of choices.

    :param choices: A list of allowed values for the answer field.
    :param permissive: If True, any value will be accepted as an answer.
    :return: A new Pydantic model class.
    """
    choice_tuple = tuple(choices)

    if not permissive:

        class ChoiceResponse(BaseModel):
            answer: Literal[choice_tuple] = Field(description="Selected choice")
            comment: Optional[str] = Field(None, description="Optional comment field")
            generated_tokens: Optional[Any] = Field(
                None, description="Generated tokens"
            )

            class Config:
                @staticmethod
                def json_schema_extra(schema: dict, model: BaseModel) -> None:
                    for prop in schema.get("properties", {}).values():
                        if prop.get("title") == "answer":
                            prop["enum"] = choices

    else:

        class ChoiceResponse(BaseModel):
            answer: Any = Field(description="Selected choice (can be any value)")
            comment: Optional[str] = Field(None, description="Optional comment field")
            generated_tokens: Optional[Any] = Field(
                None, description="Generated tokens"
            )

            class Config:
                @staticmethod
                def json_schema_extra(schema: dict, model: BaseModel) -> None:
                    for prop in schema.get("properties", {}).values():
                        if prop.get("title") == "answer":
                            prop["description"] += f". Suggested choices are: {choices}"
                    schema["title"] += " (Permissive)"

    return ChoiceResponse


class MultipleChoiceResponseValidator(ResponseValidatorABC):
    required_params = ["question_options", "use_code"]

    def fix(self, response, verbose=False):
        response_text = str(response.get("answer"))
        if response_text is None:
            response_text = response.get("generated_tokens", "")

        if verbose:
            print(f"Invalid generated tokens was: {response_text}")

        matches = []
        for idx, option in enumerate(self.question_options):
            if verbose:
                print("The options are: ", self.question_options)
            if str(option) in response_text:
                if verbose:
                    print("Match found with option ", option)
                if option not in matches:
                    matches.append(option)

        if verbose:
            print("The matches are: ", matches)
        if len(matches) == 1:
            proposed_data = {
                "answer": matches[0],
                "generated_tokens": response.get("generated_tokens", None),
            }
            try:
                self.response_model(**proposed_data)
                return proposed_data
            except Exception as e:
                if verbose:
                    print(f"Proposed solution {proposed_data} is invalid. Error: {e}")
            return response

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


class QuestionMultipleChoice(QuestionBase):
    """This question prompts the agent to select one option from a list of options.

    https://docs.expectedparrot.com/en/latest/questions.html#questionmultiplechoice-class

    """

    question_type = "multiple_choice"
    purpose = "When options are known and limited"
    question_options: Union[
        list[str], list[list], list[float], list[int]
    ] = QuestionOptionsDescriptor()
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
        permissive: bool = False,
    ):
        """Instantiate a new QuestionMultipleChoice.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param question_options: The options the agent should select from.
        :param include_comment: Whether to include a comment field.
        :param use_code: Whether to use code for the options.
        :param answering_instructions: Instructions for the question.
        :param question_presentation: The presentation of the question.
        :param permissive: Whether to force the answer to be one of the options.

        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options

        self._include_comment = include_comment
        self.use_code = use_code
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    ################
    # Answer methods
    ################

    def create_response_model(self, replacement_dict: dict = None):
        if replacement_dict is None:
            replacement_dict = {}
            # The replacement dict that could be from scenario, current answers, etc. to populate the response model

        if self.use_code:
            return create_response_model(
                list(range(len(self.question_options))), self.permissive
            )
        else:
            return create_response_model(self.question_options, self.permissive)

    def _translate_answer_code_to_answer(
        self, answer_code: int, scenario: Optional["Scenario"] = None
    ):
        """Translate the answer code to the actual answer.

        It is used to translate the answer code to the actual answer.
        The question options might be templates, so they need to be rendered with the scenario.

        >>> q = QuestionMultipleChoice.example()
        >>> q._translate_answer_code_to_answer('Good', {})
        'Good'

        >>> q = QuestionMultipleChoice(question_name="how_feeling", question_text="How are you?", question_options=["{{emotion[0]}}", "emotion[1]"])
        >>> q._translate_answer_code_to_answer('Happy', {"emotion": ["Happy", "Sad"]})
        'Happy'

        """

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
    def example(cls, include_comment=False, use_code=False) -> QuestionMultipleChoice:
        """Return an example instance."""
        return cls(
            question_text="How are you?",
            question_options=["Good", "Great", "OK", "Bad"],
            question_name="how_feeling",
            include_comment=include_comment,
            use_code=use_code,
        )


# def main():
#     """Create an example QuestionMultipleChoice and test its methods."""
#     from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice

#     q = QuestionMultipleChoice.example()
#     q.question_text
#     q.question_options
#     q.question_name
#     # validate an answer
#     q._validate_answer({"answer": 0, "comment": "I like custard"})
#     # translate answer code
#     q._translate_answer_code_to_answer(0, {})
#     # simulate answer
#     q._simulate_answer()
#     q._simulate_answer(human_readable=False)
#     # serialization (inherits from Question)
#     q.to_dict()
#     assert q.from_dict(q.to_dict()) == q


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
