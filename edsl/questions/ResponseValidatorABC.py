from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal
from typing import Optional, Any, List

from edsl.exceptions import QuestionAnswerValidationError


class BaseResponse(BaseModel):
    answer: Any
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None


class ResponseValidatorABC(ABC):
    required_params: List[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        required_class_vars = ["required_params", "valid_examples", "invalid_examples"]
        for var in required_class_vars:
            if not hasattr(cls, var):
                raise ValueError(f"Class {cls.__name__} must have a '{var}' attribute.")

    def __init__(
        self,
        response_model: type[BaseModel],
        exception_to_throw: Optional[Exception] = None,
        override_answer: Optional[dict] = None,
        **kwargs,
    ):
        self.response_model = response_model
        self.exception_to_throw = exception_to_throw  # for testing
        self.override_answer = override_answer  # for testing

        # Validate required parameters
        missing_params = [
            param for param in self.required_params if param not in kwargs
        ]
        if missing_params:
            raise ValueError(
                f"Missing required parameters: {', '.join(missing_params)}"
            )

        # Set attributes
        for key, value in kwargs.items():
            setattr(self, key, value)

    def _base_validate(self, data):
        try:
            return self.response_model(**data)
        except Exception as e:
            if hasattr(self, "fix"):
                # print("Trying to fix the data")
                fixed_data = self.fix(data)
                return self.response_model(**fixed_data)
            raise e

    def validate(self, data):
        if self.exception_to_throw:
            raise self.exception_to_throw
        if self.override_answer:  # for testing
            data = self.override_answer

        try:
            response = self._base_validate(data)
        except Exception as e:
            raise QuestionAnswerValidationError(
                message=str(e), data=data, model=self.response_model
            )

        try:
            return self.custom_validate(response)
        except Exception as e:
            raise QuestionAnswerValidationError(str(e))

    @abstractmethod
    def custom_validate(self, data: dict) -> BaseModel:
        pass

    # def self_check(self):
    #     for example in self.valid_examples:
    #         self.validate(example)
    #     for example in self.invalid_examples:
    #         try:
    #             self.validate(example)
    #         except ValueError:
    #             pass
    #         else:
    #             raise ValueError(f"Example {example} should have failed.")


# Example usage
if __name__ == "__main__":
    pass
