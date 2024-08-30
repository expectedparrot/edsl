from typing import Any, SupportsIndex
from jinja2 import Template
import json


class QuestionErrors(Exception):
    """
    Base exception class for question-related errors.
    """

    def __init__(self, message="An error occurred with the question"):
        self.message = message
        super().__init__(self.message)


class QuestionAnswerValidationError(QuestionErrors):
    documentation = "https://docs.expectedparrot.com/en/latest/exceptions.html"

    explanation = """This when the answer coming from the Language Model does not conform to the expectation for that question type.
    For example, if the question is a multiple choice question, the answer should be drawn from the list of options provided.
    """

    def __init__(self, message="Invalid answer.", data=None, model=None):
        self.message = message
        self.data = data
        self.model = model
        super().__init__(self.message)

    def __str__(self):
        return f"""{repr(self)} 
        Data being validated: {self.data} 
        Pydnantic Model: {self.model}.
        Reported error: {self.message}."""

    def to_html_dict(self):
        return {
            "error_type": ("Name of the exception", "p", "/p", self.__class__.__name__),
            "explaination": ("Explanation", "p", "/p", self.explanation),
            "edsl answer": (
                "What model returned",
                "pre",
                "/pre",
                json.dumps(self.data, indent=2),
            ),
            "validating_model": (
                "Pydantic model for answers",
                "pre",
                "/pre",
                json.dumps(self.model.model_json_schema(), indent=2),
            ),
            "error_message": (
                "Error message Pydantic returned",
                "p",
                "/p",
                self.message,
            ),
            "documentation_url": (
                "URL to EDSL docs",
                f"a href='{self.documentation}'",
                "/a",
                self.documentation,
            ),
        }


class QuestionCreationValidationError(QuestionErrors):
    pass


class QuestionResponseValidationError(QuestionErrors):
    pass


class QuestionAttributeMissing(QuestionErrors):
    pass


class QuestionSerializationError(QuestionErrors):
    pass


class QuestionScenarioRenderError(QuestionErrors):
    pass


class QuestionMissingTypeError(QuestionErrors):
    pass


class QuestionBadTypeError(QuestionErrors):
    pass
