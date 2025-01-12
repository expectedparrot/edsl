from __future__ import annotations
from typing import Union, Optional, Dict, List, Any, Type
from pydantic import BaseModel, Field, field_validator
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pathlib import Path

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import (
    AnswerKeysDescriptor,
    ValueTypesDescriptor,
    ValueDescriptionsDescriptor,
    QuestionTextDescriptor,
)
from edsl.questions.response_validator_abc import ResponseValidatorABC
from edsl.exceptions.questions import QuestionCreationValidationError
from edsl.questions.decorators import inject_exception


def create_dict_response(
    answer_keys: List[str],
    value_types: Optional[List[str]] = None,
    permissive: bool = False,
):
    """Create a response model for dict questions."""
    class DictResponse(BaseModel):
        answer: Dict[str, Union[int, str, float, List[Union[int, str, float]]]]
        comment: Optional[str] = None

        @field_validator("answer")
        def validate_answer(cls, v, values, **kwargs):
            # Ensure all keys exist
            missing_keys = set(answer_keys) - set(v.keys())
            if missing_keys:
                raise ValueError(f"Missing required keys: {missing_keys}")
            # Validate value types if not permissive
            if not permissive and value_types:
                for key, expected_type in zip(answer_keys, value_types):
                    if key in v and not isinstance(v[key], eval(expected_type)):
                        raise ValueError(
                            f"Key '{key}' has value of type {type(v[key]).__name__}, expected {expected_type}"
                        )
            return v

    return DictResponse


class DictResponseValidator(ResponseValidatorABC):
    required_params = ["answer_keys", "permissive"]

    valid_examples = [
        (
            {"answer": {"name": "Hot Chocolate", "num_ingredients": 5}},
            {"answer_keys": ["name", "num_ingredients"], "value_types": ["str", "int"]},
        )
    ]
    invalid_examples = [
        (
            {"answer": {"name": 123}},  # Name should be a string
            {"answer_keys": ["name"], "value_types": ["str"]},
            "Key 'name' has value of type int, expected str",
        )
    ]


class QuestionDict(QuestionBase):
    question_type = "dict"
    question_text: str = QuestionTextDescriptor()
    answer_keys: List[str] = AnswerKeysDescriptor()
    value_types: Optional[List[str]] = ValueTypesDescriptor()
    value_descriptions: Optional[List[str]] = ValueDescriptionsDescriptor()

    _response_model = None
    response_validator_class = DictResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answer_keys: List[str],
        value_types: Optional[List[Union[str, type]]] = None,
        value_descriptions: Optional[List[str]] = None,
        include_comment: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.answer_keys = answer_keys
        self.value_types = self._normalize_value_types(value_types)
        self.value_descriptions = value_descriptions
        self.include_comment = include_comment
        self.question_presentation = question_presentation or self._render_template(
            "question_presentation.jinja"
        )
        self.answering_instructions = answering_instructions or self._render_template(
            "answering_instructions.jinja"
        )
        self.permissive = permissive

        # Validation
        if self.value_types and len(self.value_types) != len(self.answer_keys):
            raise QuestionCreationValidationError(
                "Length of value_types must match length of answer_keys."
            )
        if self.value_descriptions and len(self.value_descriptions) != len(self.answer_keys):
            raise QuestionCreationValidationError(
                "Length of value_descriptions must match length of answer_keys."
            )

        # Response model generation
        self._response_model = create_dict_response(
            answer_keys=self.answer_keys,
            value_types=self.value_types,
            permissive=self.permissive,
        )

    @staticmethod
    def _normalize_value_types(value_types: Optional[List[Union[str, type]]]) -> Optional[List[str]]:
        """Convert all value_types to string representations, including type hints."""
        if not value_types:
            return None
        normalized = []
        for t in value_types:
            if isinstance(t, str):
                normalized.append(t)
            elif hasattr(t, "__name__"):  # Standard types like `str` or `int`
                normalized.append(t.__name__)
            elif hasattr(t, "__origin__"):  # Handle generics like `list[str]`
                origin = t.__origin__.__name__
                args = ", ".join(arg.__name__ if hasattr(arg, "__name__") else str(arg) for arg in t.__args__)
                normalized.append(f"{origin}[{args}]")
            else:
                raise QuestionCreationValidationError(
                    f"Invalid type in value_types: {t}. Must be a type or string."
                )
        return normalized

    def _render_template(self, template_name: str) -> str:
        """Render a template using Jinja."""
        try:
            template_dir = Path(__file__).parent / "templates" / "dict"
            env = Environment(loader=FileSystemLoader(template_dir))
            template = env.get_template(template_name)
            return template.render(
                question_name=self.question_name,
                question_text=self.question_text,
                answer_keys=self.answer_keys,
                value_types=self.value_types,
                value_descriptions=self.value_descriptions,
                include_comment=self.include_comment,
            )
        except TemplateNotFound:
            return f"Template {template_name} not found in {template_dir}."

    def to_dict(self, add_edsl_version: bool = True) -> dict:
        """Serialize to JSON-compatible dictionary."""
        return {
            "question_type": self.question_type,
            "question_name": self.question_name,
            "question_text": self.question_text,
            "answer_keys": self.answer_keys,
            "value_types": self.value_types or [],
            "value_descriptions": self.value_descriptions or [],
            "include_comment": self.include_comment,
            "permissive": self.permissive,
        }

    @classmethod
    def from_dict(cls, data: dict) -> QuestionDict:
        """Recreate from a dictionary."""
        return cls(
            question_name=data["question_name"],
            question_text=data["question_text"],
            answer_keys=data["answer_keys"],
            value_types=data.get("value_types"),
            value_descriptions=data.get("value_descriptions"),
            include_comment=data.get("include_comment", True),
            permissive=data.get("permissive", False),
        )

    @classmethod
    @inject_exception
    def example(cls) -> QuestionDict:
        """Return an example question."""
        return cls(
            question_name="example",
            question_text="Please provide a description of your favorite book.",
            answer_keys=["title", "author", "year"],
            value_types=["str", "str", "int"],
            value_descriptions=[
                "The title of the book.",
                "The author of the book.",
                "The year it was published.",
            ],
        )


if __name__ == "__main__":
    q = QuestionDict.example()
    print(q.to_dict())
