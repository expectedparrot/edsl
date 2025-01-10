from __future__ import annotations
from typing import Union, Optional, Dict, List, Any

from pydantic import BaseModel, Field, validator
from jinja2 import Template
import random
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import (
    QuestionOptionsDescriptor,
    OptionLabelDescriptor,
    QuestionTextDescriptor,
)
from edsl.questions.response_validator_abc import ResponseValidatorABC
from edsl.questions.decorators import inject_exception
from edsl.exceptions.questions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)



def create_dict_response(answer_keys: List[str], permissive: bool = False):
    """Create a response model for dict questions, handling types according to permissiveness."""

    class DictResponse(BaseModel):
        answer: Dict[str, Union[int, str, float, List[Union[int, str, float]]]]
        comment: Optional[str] = None
        generated_tokens: Optional[Any] = None

        @validator('answer', pre=True, each_item=False)
        def validate_answer(cls, value, values, **kwargs):
            # Example validation logic
            for key, item in value.items():
                if key == 'num_ingredients' and not isinstance(item, int):
                    raise TypeError(f"Expected integer for 'num_ingredients', got {type(item).__name__}")
                if isinstance(item, List) and not all(isinstance(x, (int, str)) for x in item):
                    raise TypeError(f"All items in list for key '{key}' must be either int or str")
            return value

    return DictResponse


class DictResponseValidator(ResponseValidatorABC):
    required_params = ["answer_keys", "permissive"]

    valid_examples = [
        (
            {"answer": {"Item1": 1, "Item2": 2}},
            {
                "answer_keys": ["Item1", "Item2"]
            },
        )
    ]

    invalid_examples = [
        (
            {"answer": {"Item1": 1}},
            {
                "answer_keys": ["Item1", "Item2"]
            },
            "Missing required keys: {'Item2'}",
        )
    ]

    def fix(self, response, verbose=False):
        if verbose:
            print(f"Fixing dict response: {response}")

        # If we have generated tokens, try to parse them
        if "generated_tokens" in response:
            try:
                import json

                fixed = json.loads(response["generated_tokens"])
                if isinstance(fixed, dict):
                    # Map numeric keys to answer_keys
                    mapped_answer = {}
                    for idx, item in enumerate(self.answer_keys):
                        if str(idx) in fixed:
                            mapped_answer[item] = fixed[str(idx)]
                    if (
                        mapped_answer
                    ):  # Only return if we successfully mapped some answers
                        return {"answer": mapped_answer}
            except:
                pass

        # If answer uses numeric keys, map them to answer_keys
        if "answer" in response and isinstance(response["answer"], dict):
            if all(str(key).isdigit() for key in response["answer"].keys()):
                mapped_answer = {}
                for idx, item in enumerate(self.question_items):
                    if str(idx) in response["answer"]:
                        mapped_answer[item] = response["answer"][str(idx)]
                if mapped_answer:  # Only update if we successfully mapped some answers
                    response["answer"] = mapped_answer

        return response


class QuestionDict(QuestionBase):
    """A question that prompts a model to format a response as a dictionary using specified keys."""

    question_type = "dict"
    question_text: str = QuestionTextDescriptor()
    answer_keys: List[Union[int, str, float]] = QuestionOptionsDescriptor()

    _response_model = None
    response_validator_class = DictResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answer_keys: List[Union[int, str, float]],
        value_types: Optional[List[type]] = None,
        value_descriptions: Optional[List[str]] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
    ):
        """Initialize a new QuestionDict.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param answer_keys: List of keys for the answer dictionary.
        :param value_types: Optional list of types for each value.
        :param value_descriptions: Optional list of descriptions for each value.
        :param include_comment: Whether to include a comment field.
        :param answering_instructions: Optional custom instructions.
        :param question_presentation: Optional custom presentation.
        :param permissive: Whether to strictly validate responses.
        """
        self.question_name = question_name

        try:
            self.question_text = question_text
        except Exception as e:
            raise QuestionCreationValidationError(
                "question_text cannot be empty or too short!"
            ) from e

        self.answer_keys = answer_keys

        self.value_types = value_types or [str] * len(answer_keys)
        self.value_descriptions = value_descriptions or [""] * len(answer_keys)
        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
        self.permissive = permissive

    def create_response_model(self):
        return create_dict_response(
            self.answer_keys, self.permissive
        )

    @property
    def question_html_content(self) -> str:
        """Generate HTML representation of the dict question."""
        # TBD


    @classmethod
    @inject_exception
    def example(cls) -> QuestionDict:
        """Return an example dict question."""
        return cls(
            question_name="recipe",
            question_text="""
            Please provide a recipe for basic hot chocolate.
            """,
            answer_keys=[
                "recipe_name",
                "ingredients",
                "num_ingredients"
            ],
            value_types=[str, str, List[str], int],
            value_descriptions=[
                "The name of the recipe.",
                "List of ingredients.",
                "The number of ingredients."
            ]
        )

    def _simulate_answer(self) -> dict:
        """Simulate a random valid answer."""
        # TBD


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
