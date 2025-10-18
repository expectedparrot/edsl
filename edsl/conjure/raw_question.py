from dataclasses import dataclass, field
from typing import List, Optional
from edsl.questions import QuestionBase
from edsl.questions import Question

from .utilities import convert_value


@dataclass
class RawQuestion:
    """
    A class to represent a question before it is converted to edsl class.

    >>> rq = RawQuestion.example()
    >>> rq.to_question()
    Question('multiple_choice', question_name = \"""how_are_you\""", question_text = \"""How are you doing?\""", question_options = ['Good', 'Bad'])
    """

    question_type: str
    question_name: str
    question_text: str
    responses: List[str] = field(default_factory=list)
    question_options: Optional[List[str]] = None

    @classmethod
    def example(cls):
        return cls(
            question_type="multiple_choice",
            question_name="how_are_you",
            question_text="How are you doing?",
            responses=["Good", "Bad", "Bad", "Good"],
            question_options=["Good", "Bad"],
        )

    def __post_init__(self):
        self.responses = [convert_value(r) for r in self.responses]

    def _sanitize_question_text(self, text: str) -> str:
        """Sanitize question text to remove braces that cause Jinja2 parsing errors."""
        if not text:
            return text

        # Replace curly braces with safe placeholders to prevent Jinja2 parsing issues
        text = text.replace("{", "<left_brace>").replace("}", "<right_brace>")

        return text.strip()

    def to_question(self) -> QuestionBase:
        """Return a Question object from the RawQuestion."""
        try:
            # TODO: Remove this once we have a better way to handle multiple_choice_with_other
            if self.question_type == "multiple_choice_with_other":
                question_type = "multiple_choice"
            else:
                question_type = self.question_type

            # Sanitize question text to remove Jinja2 comment tags
            sanitized_text = self._sanitize_question_text(self.question_text)

            # exclude responses from the dictionary if they have a None value; don't inlcude responses in the dictionary
            d = {
                k: v
                for k, v in {
                    "question_type": question_type,
                    "question_name": self.question_name,
                    "question_text": sanitized_text,
                    "responses": self.responses,
                    "question_options": self.question_options,
                }.items()
                if v is not None and k != "responses"
            }
            return Question(**d)
        except Exception as e:
            # Provide detailed error information including the offending question text
            original_text = self.question_text
            sanitized_text = (
                self._sanitize_question_text(original_text) if original_text else ""
            )

            error_msg = (
                f"Error creating question '{self.question_name}': {str(e)}\n"
                f"Original question text: {repr(original_text)}\n"
                f"Sanitized question text: {repr(sanitized_text)}\n"
                f"Suggested fix: Check for malformed Jinja2 comment tags like {{# ... #}} in the question text."
            )
            raise ValueError(error_msg) from e


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
