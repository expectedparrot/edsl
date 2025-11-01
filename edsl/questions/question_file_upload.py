from __future__ import annotations
from typing import Optional

import os
from pydantic import BaseModel, field_validator

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class FileUploadResponse(BaseModel):
    """Response model for file upload questions.

    Fields:
        answer: Absolute path to the selected file.
        comment: Optional comment.
        generated_tokens: Optional raw text; unused here but kept for consistency.
    """

    answer: str
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_path(cls, v: str) -> str:
        # Expand user (~) and environment variables, and normalize to absolute path
        expanded = os.path.expandvars(os.path.expanduser(v.strip()))
        abs_path = os.path.abspath(expanded)

        if not os.path.exists(abs_path):
            from .exceptions import QuestionAnswerValidationError

            raise QuestionAnswerValidationError(
                message=f"File does not exist: {abs_path}",
                data={"answer": v},
                model=cls,
                pydantic_error=None,
            )

        if not os.path.isfile(abs_path):
            from .exceptions import QuestionAnswerValidationError

            raise QuestionAnswerValidationError(
                message=f"Path is not a file: {abs_path}",
                data={"answer": v},
                model=cls,
                pydantic_error=None,
            )

        return abs_path


class FileUploadResponseValidator(ResponseValidatorABC):
    """Validator for file upload responses.

    Ensures the provided path exists and points to a file.
    """

    required_params = []
    valid_examples = [({"answer": __file__}, {})]
    invalid_examples = [
        ({"answer": "/definitely/not/here.xyz"}, {}, "File does not exist")
    ]

    # No custom fix; rely on strict validation


class QuestionFileUpload(QuestionBase):
    """Question allowing the user to provide a local file path as the answer.

    Example:
        >>> q = QuestionFileUpload(question_name="resume", question_text="Upload your resume file path")
        >>> q.question_type
        'file_upload'
    """

    question_type = "file_upload"
    _response_model = FileUploadResponse
    response_validator_class = FileUploadResponseValidator

    @property
    def fake_data_factory(self):
        """Override fake_data_factory to generate valid file paths for testing."""
        if not hasattr(self, "_fake_data_factory"):
            from polyfactory.factories.pydantic_factory import ModelFactory

            class FakeFileUploadData(ModelFactory[self.response_model]):
                __model__ = FileUploadResponse

                @classmethod
                def answer(cls):
                    # Return the path to this current file as it's guaranteed to exist
                    return __file__

            self._fake_data_factory = FakeFileUploadData
        return self._fake_data_factory

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @classmethod
    @inject_exception
    def example(cls) -> "QuestionFileUpload":
        return cls(
            question_name="file_path",
            question_text="Please provide the path to the file.",
        )
