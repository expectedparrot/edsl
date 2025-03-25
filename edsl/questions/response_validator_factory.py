from typing import Type, List
from .data_structures import BaseModel
from .response_validator_abc import ResponseValidatorABC


class ResponseValidatorFactory:
    """Factory class to create a response validator for a question."""

    def __init__(self, question):
        self.question = question

    @property
    def response_model(self) -> Type["BaseModel"]:
        if self.question._response_model is not None:
            return self.question._response_model
        else:
            return self.question.create_response_model()

    @property
    def response_validator(self) -> "ResponseValidatorABC":
        """Return the response validator."""
        params = {}
        params.update({"response_model": self.question.response_model})
        params.update({k: getattr(self.question, k) for k in self.validator_parameters})
        params.update({"exception_to_throw": getattr(self.question, "exception_to_throw", None)})
        params.update({"override_answer": getattr(self.question, "override_answer", None)})
        return self.question.response_validator_class(**params)

    @property
    def validator_parameters(self) -> List[str]:
        """Return the parameters required for the response validator."""
        return self.question.response_validator_class.required_params
