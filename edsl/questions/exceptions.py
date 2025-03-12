from typing import Any, SupportsIndex
import json
from pydantic import ValidationError


class QuestionErrors(Exception):
    """
    Base exception class for question-related errors.
    """

    def __init__(self, message="An error occurred with the question"):
        self.message = message
        super().__init__(self.message)


class QuestionAnswerValidationError(QuestionErrors):
    documentation = "https://docs.expectedparrot.com/en/latest/exceptions.html"

    explanation = """
    This can occur when the answer coming from the Language Model does not conform to the expectations for the question type.
    For example, if the question is a multiple choice question, the answer should be drawn from the list of options provided.
    """

    def __init__(
        self,
        message="Invalid answer.",
        pydantic_error: ValidationError = None,
        data: dict = None,
        model=None,
    ):
        self.message = message
        self.pydantic_error = pydantic_error
        self.data = data
        self.model = model
        super().__init__(self.message)

    def __str__(self):
        if isinstance(self.message, ValidationError):
            # If it's a ValidationError, just return the core error message
            return str(self.message)
        elif hasattr(self.message, "errors"):
            # Handle the case where it's already been converted to a string but has errors
            error_list = self.message.errors()
            if error_list:
                return str(error_list[0].get("msg", "Unknown error"))
        return str(self.message)

    # def __str__(self):
    #     return f"""{repr(self)}
    #     Data being validated: {self.data}
    #     Pydnantic Model: {self.model}.
    #     Reported error: {self.message}."""

    def to_html_dict(self):
        return {
            "Exception type": ("p", "/p", self.__class__.__name__),
            "Explanation": ("p", "/p", self.explanation),
            "EDSL response": (
                "pre",
                "/pre",
                json.dumps(self.data, indent=2),
            ),
            "Validating model": (
                "pre",
                "/pre",
                json.dumps(self.model.model_json_schema(), indent=2),
            ),
            "Error message": (
                "p",
                "/p",
                self.message,
            ),
            "Documentation": (
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
