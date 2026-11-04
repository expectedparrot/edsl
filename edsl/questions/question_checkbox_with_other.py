from __future__ import annotations

from typing import Any, Optional

from jinja2 import Template
from pydantic import BaseModel, Field, model_validator

from .decorators import inject_exception
from .descriptors import OtherOptionTextDescriptor
from .question_check_box import CheckBoxResponseValidator, QuestionCheckBox


def create_checkbox_with_other_response_model(
    choices: list[Any],
    other_option_text: str,
    min_selections: Optional[int] = None,
    max_selections: Optional[int] = None,
    permissive: bool = False,
    exclusive_choices: Optional[list[Any]] = None,
):
    """Create a response model accepting choices and ``Other: value`` entries."""

    class CheckboxWithOtherResponse(BaseModel):
        answer: list[Any] = Field(description="List of selected choices")
        comment: Optional[str] = None
        generated_tokens: Optional[Any] = None

        @model_validator(mode="after")
        def validate_answer(self):
            has_exclusive_choice = any(
                choice in (exclusive_choices or []) for choice in self.answer
            )
            if has_exclusive_choice:
                if len(self.answer) != 1:
                    raise ValueError("Exclusive options must be selected by themselves")
            if not permissive:
                if (
                    not has_exclusive_choice
                    and min_selections is not None
                    and len(self.answer) < min_selections
                ):
                    raise ValueError(f"Must select at least {min_selections} option(s)")
                if max_selections is not None and len(self.answer) > max_selections:
                    raise ValueError(f"Must select at most {max_selections} option(s)")

            for choice in self.answer:
                if choice in choices or choice == other_option_text:
                    continue
                if isinstance(choice, str):
                    prefix, separator, custom_value = choice.partition(":")
                    if (
                        separator
                        and prefix.strip().casefold() == other_option_text.casefold()
                        and custom_value.strip()
                    ):
                        continue
                raise ValueError(
                    f"Invalid choice: {choice}. Must be one of: {choices}, "
                    f"or '{other_option_text}: <custom response>'"
                )
            return self

    return CheckboxWithOtherResponse


class CheckboxWithOtherResponseValidator(CheckBoxResponseValidator):
    """Validate checkbox responses that may contain custom ``Other`` values."""

    required_params = CheckBoxResponseValidator.required_params + ["other_option_text"]

    valid_examples = [
        (
            {"answer": ["Good", "Other: Fantastic"]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "use_code": False,
                "other_option_text": "Other",
                "exclusive_options": [],
            },
        )
    ]
    invalid_examples = [
        (
            {"answer": ["Unknown"]},
            {
                "question_options": ["Good", "Great", "OK", "Bad"],
                "use_code": False,
                "other_option_text": "Other",
                "exclusive_options": [],
            },
            "Invalid choice",
        )
    ]


class QuestionCheckBoxWithOther(QuestionCheckBox):
    """A checkbox question that also accepts one or more custom responses.

    Custom responses use the form ``"Other: response text"`` and may appear
    in the same answer list as predefined options.
    """

    question_type = "checkbox_with_other"
    purpose = "When multiple options can be selected and custom responses are allowed"
    other_option_text = OtherOptionTextDescriptor()
    _response_model = None
    response_validator_class = CheckboxWithOtherResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        min_selections: Optional[int] = None,
        max_selections: Optional[int] = None,
        include_comment: bool = True,
        use_code: bool = False,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
        other_option_text: str = "Other",
        exclusive_options: Optional[list[str]] = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_options=question_options,
            min_selections=min_selections,
            max_selections=max_selections,
            include_comment=include_comment,
            use_code=use_code,
            question_presentation=question_presentation,
            answering_instructions=answering_instructions,
            permissive=permissive,
            exclusive_options=exclusive_options,
        )
        self.other_option_text = other_option_text

    def create_response_model(self):
        choices: list[Any]
        if self._use_code:
            choices = list(range(len(self.question_options)))
        else:
            choices = list(self.question_options)
        return create_checkbox_with_other_response_model(
            choices=choices,
            other_option_text=self.other_option_text,
            min_selections=self.min_selections,
            max_selections=self.max_selections,
            permissive=self.permissive,
            exclusive_choices=(
                [
                    self.question_options.index(option)
                    for option in self.exclusive_options
                ]
                if self._use_code
                else self.exclusive_options
            ),
        )

    @property
    def question_html_content(self) -> str:
        """Return checkbox inputs plus a text field for a custom response."""
        return Template(
            """
        {% for option in question_options %}
        <div>
        <input type="checkbox" id="{{ question_name }}_{{ loop.index0 }}"
               name="{{ question_name }}" value="{{ option }}">
        <label for="{{ question_name }}_{{ loop.index0 }}">{{ option }}</label>
        </div>
        {% endfor %}
        <div>
        <input type="checkbox" id="{{ question_name }}_other"
               name="{{ question_name }}" value="{{ other_option_text }}">
        <label for="{{ question_name }}_other">{{ other_option_text }}</label>
        <input type="text" id="{{ question_name }}_other_text"
               name="{{ question_name }}_other_text" placeholder="Please specify">
        </div>
        """
        ).render(
            question_name=self.question_name,
            question_options=self.question_options,
            other_option_text=self.other_option_text,
        )

    @classmethod
    @inject_exception
    def example(
        cls, include_comment: bool = False, use_code: bool = False
    ) -> "QuestionCheckBoxWithOther":
        return cls(
            question_name="foods",
            question_text="Which foods do you enjoy?",
            question_options=["Pizza", "Pasta", "Salad"],
            min_selections=1,
            max_selections=3,
            include_comment=include_comment,
            use_code=use_code,
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
