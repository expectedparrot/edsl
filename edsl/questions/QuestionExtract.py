from __future__ import annotations
import json
import re

from typing import Any, Optional, Dict
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import AnswerTemplateDescriptor

from edsl.questions.ResponseValidatorABC import ResponseValidatorABC
from edsl.questions.ResponseValidatorABC import BaseResponse
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions.decorators import inject_exception

from typing import Dict, Any
from pydantic import create_model, Field


def extract_json(text, expected_keys, verbose=False):
    # Escape special regex characters in keys
    escaped_keys = [re.escape(key) for key in expected_keys]

    # Create a pattern that looks for all expected keys
    pattern = r"\{[^}]*" + r"[^}]*".join(escaped_keys) + r"[^}]*\}"

    json_match = re.search(pattern, text)

    if json_match:
        json_str = json_match.group(0)
        try:
            # Parse the extracted string as JSON
            json_data = json.loads(json_str)

            # Verify that all expected keys are present
            if all(key in json_data for key in expected_keys):
                return json_data
            else:
                if verbose:
                    print(
                        "Error: Not all expected keys were found in the extracted JSON."
                    )
                return None
        except json.JSONDecodeError:
            if verbose:
                print("Error: The extracted content is not valid JSON.")
            return None
    else:
        if verbose:
            print("Error: No JSON-like structure found with all expected keys.")
        return None


def dict_to_pydantic_model(input_dict: Dict[str, Any]) -> Any:
    field_definitions = {
        key: (str, Field(default=str(value))) for key, value in input_dict.items()
    }

    DynamicModel = create_model("DynamicModel", **field_definitions)

    class AnswerModel(BaseResponse):
        answer: DynamicModel
        generated_tokens: Optional[str] = None
        comment: Optional[str] = None

    return AnswerModel


class ExtractResponseValidator(ResponseValidatorABC):
    required_params = ["answer_template"]
    valid_examples = [({"answer": "This is great"}, {})]
    invalid_examples = [
        (
            {"answer": None},
            {"answer_template": {"name": "John Doe", "profession": "Carpenter"}},
            "Result cannot be empty",
        ),
    ]

    def custom_validate(self, response) -> BaseResponse:
        return response.dict()

    def fix(self, response, verbose=False):
        raw_tokens = response["generated_tokens"]
        if verbose:
            print(f"Invalid response of QuestionExtract was: {raw_tokens}")
        extracted_json = extract_json(raw_tokens, self.answer_template.keys(), verbose)
        if verbose:
            print("Proposed solution is: ", extracted_json)
        return {
            "answer": extracted_json,
            "comment": response.get("comment", None),
            "generated_tokens": raw_tokens,
        }


class QuestionExtract(QuestionBase):
    """This question prompts the agent to extract information from a string and return it in a given template."""

    question_type = "extract"
    answer_template: dict[str, Any] = AnswerTemplateDescriptor()
    _response_model = None
    response_validator_class = ExtractResponseValidator

    def __init__(
        self,
        question_text: str,
        answer_template: dict[str, Any],
        question_name: str,
        answering_instructions: str = None,
        question_presentation: str = None,
    ):
        """Initialize the question.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param answer_template: The template for the answer.
        """
        self.question_name = question_name
        self.question_text = question_text
        self.answer_template = answer_template
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    def create_response_model(self):
        return dict_to_pydantic_model(self.answer_template)

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        question_html_content = Template(
            """
        {% for field, placeholder in answer_template.items() %}
        <div>
        <label for="{{ field }}">{{ field }}</label>
        <input type="text" id="{{ field }}" name="{{ question_name }}[{{ field }}]" placeholder="{{ placeholder }}">
        </div>
        {% endfor %}
        """
        ).render(
            question_name=self.question_name,
            answer_template=self.answer_template,
        )
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    @inject_exception
    def example(cls) -> QuestionExtract:
        """Return an example question."""
        return cls(
            question_name="extract_name",
            question_text="My name is Moby Dick. I have a PhD in astrology, but I'm actually a truck driver",
            answer_template={"name": "John Doe", "profession": "Carpenter"},
        )


def main():
    """Administer a question and validate the answer."""
    from edsl.questions.QuestionExtract import QuestionExtract

    q = QuestionExtract.example()
    q.question_text
    q.question_name
    q.answer_template
    q._validate_answer({"answer": {"name": "Moby", "profession": "truck driver"}})
    q._translate_answer_code_to_answer(
        {"answer": {"name": "Moby", "profession": "truck driver"}}
    )
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
