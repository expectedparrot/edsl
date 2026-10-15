"""Matrix questions with optional free-text fields on selected rows."""

import random
from typing import Dict, List, Optional, Union

from jinja2 import Template

from .decorators import inject_exception
from .exceptions import QuestionCreationValidationError
from .question_matrix import QuestionMatrix


class QuestionMatrixWithText(QuestionMatrix):
    """A matrix question where selected rows also accept optional text.

    Rows named in ``items_with_text`` return an object containing ``choice``
    (the selected matrix option) and optional ``text``. Other rows retain the
    ordinary scalar matrix response format.
    """

    question_type = "matrix_with_text"

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_items: List[str],
        question_options: List[Union[int, str, float]],
        option_labels: Optional[Dict[Union[int, str, float], str]] = None,
        include_comment: bool = True,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
        randomize_items: bool = False,
        items_to_pin: Optional[List[str]] = None,
        items_with_text: Optional[List[str]] = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            question_items=question_items,
            question_options=question_options,
            option_labels=option_labels,
            include_comment=include_comment,
            answering_instructions=answering_instructions,
            question_presentation=question_presentation,
            permissive=permissive,
            randomize_items=randomize_items,
            items_to_pin=items_to_pin,
        )
        self._items_with_text = list(items_with_text or [])
        unknown_items = set(self.items_with_text) - set(self.question_items)
        if unknown_items:
            raise QuestionCreationValidationError(
                "items_with_text must contain only values in question_items: "
                + ", ".join(sorted(unknown_items))
            )

    @property
    def items_with_text(self) -> List[str]:
        """Rows with an optional free-text field, serialized with the question."""
        return self._items_with_text

    def _simulate_answer(self) -> dict:
        return {
            "answer": {
                item: (
                    {"choice": random.choice(self.question_options), "text": None}
                    if item in self.items_with_text
                    else random.choice(self.question_options)
                )
                for item in self.question_items
            },
            "comment": "Sample matrix response",
        }

    @property
    def question_html_content(self) -> str:
        template = Template(
            """<table class="matrix-question">
            <tr><th></th>{% for option in question_options %}<th>{{ option }}{% if option in option_labels %}<br><small>{{ option_labels[option] }}</small>{% endif %}</th>{% endfor %}</tr>
            {% for item in question_items %}<tr><td>{{ item }}{% if item in items_with_text %}<br><input type="text" name="{{ question_name }}_{{ item }}_text" aria-label="Additional text for {{ item }}">{% endif %}</td>
            {% for option in question_options %}<td><input type="radio" name="{{ question_name }}_{{ item }}" value="{{ option }}" id="{{ question_name }}_{{ item }}_{{ option }}"></td>{% endfor %}</tr>{% endfor %}
            </table>"""
        )
        return template.render(
            question_name=self.question_name,
            question_items=self.question_items,
            question_options=self.question_options,
            option_labels=self.option_labels,
            items_with_text=self.items_with_text,
        )

    @classmethod
    @inject_exception
    def example(cls):
        return cls(
            question_name="service_matrix",
            question_text="Rate each part of the service and add details where useful.",
            question_items=["Speed", "Quality", "Support"],
            question_options=[1, 2, 3, 4, 5],
            items_with_text=["Support"],
        )
