from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, field_validator

# from decimal import Decimal
from typing import Optional, Any, List, TypedDict

from edsl.exceptions import QuestionAnswerValidationError
from pydantic import ValidationError


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
        self.original_exception = None

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

        if not hasattr(self, "permissive"):
            self.permissive = False

        self.fixes_tried = 0

    class RawEdslAnswerDict(TypedDict):
        answer: Any
        comment: Optional[str]
        generated_tokens: Optional[str]

    def _preprocess(self, data: RawEdslAnswerDict) -> RawEdslAnswerDict:
        """This is for testing purposes. A question can be given an exception to throw or an answer to always return.

        >>> rv = ResponseValidatorABC.example()
        >>> rv.override_answer = {"answer": 42}
        >>> rv.validate({"answer": 23})
        {'answer': 42, 'comment': None, 'generated_tokens': None}
        """
        if self.exception_to_throw:
            raise self.exception_to_throw
        return self.override_answer if self.override_answer else data

    def _base_validate(self, data: RawEdslAnswerDict) -> BaseModel:
        """This is the main validation function. It takes the response_model and checks the data against it, returning the instantiated model.

        >>> rv = ResponseValidatorABC.example("numerical")
        >>> rv._base_validate({"answer": 42})
        ConstrainedNumericResponse(answer=42, comment=None, generated_tokens=None)
        """
        try:
            return self.response_model(**data)
        except ValidationError as e:
            raise QuestionAnswerValidationError(e, data=data, model=self.response_model)

    def post_validation_answer_convert(self, data):
        return data

    class EdslAnswerDict(TypedDict):
        answer: Any
        comment: Optional[str]
        generated_tokens: Optional[str]

    def validate(
        self,
        raw_edsl_answer_dict: RawEdslAnswerDict,
        fix=False,
        verbose=False,
        replacement_dict: dict = None,
    ) -> EdslAnswerDict:
        """This is the main validation function.

        >>> rv = ResponseValidatorABC.example("numerical")
        >>> rv.validate({"answer": 42})
        {'answer': 42, 'comment': None, 'generated_tokens': None}
        >>> rv.max_value
        86.7
        >>> rv.validate({"answer": "120"})
        Traceback (most recent call last):
        ...
        edsl.exceptions.questions.QuestionAnswerValidationError:...
        >>> from edsl import QuestionNumerical
        >>> q = QuestionNumerical.example()
        >>> q.permissive = True
        >>> rv = q.response_validator
        >>> rv.validate({"answer": "120"})
        {'answer': 120, 'comment': None, 'generated_tokens': None}
        >>> rv.validate({"answer": "poo"})
        Traceback (most recent call last):
        ...
        edsl.exceptions.questions.QuestionAnswerValidationError:...
        """
        proposed_edsl_answer_dict = self._preprocess(raw_edsl_answer_dict)
        try:
            pydantic_edsl_answer: BaseModel = self._base_validate(
                proposed_edsl_answer_dict
            )
            edsl_answer_dict = self._extract_answer(pydantic_edsl_answer)
            return self._post_process(edsl_answer_dict)
        except QuestionAnswerValidationError as e:
            if verbose:
                print(f"Failed to validate {raw_edsl_answer_dict}; {str(e)}")
            return self._handle_exception(e, raw_edsl_answer_dict)

    def _handle_exception(self, e: Exception, raw_edsl_answer_dict) -> EdslAnswerDict:
        if self.fixes_tried == 0:
            self.original_exception = e

        if self.fixes_tried == 0 and hasattr(self, "fix"):
            self.fixes_tried += 1
            fixed_data = self.fix(raw_edsl_answer_dict)
            try:
                return self.validate(fixed_data, fix=True)
            except Exception as e:
                pass  # we don't log failed fixes

        raise QuestionAnswerValidationError(
            self.original_exception,
            data=raw_edsl_answer_dict,
            model=self.response_model,
        )

    def _check_constraints(self, pydantic_edsl_answer: BaseModel) -> dict:
        pass

    def _extract_answer(self, response: BaseModel) -> EdslAnswerDict:
        return response.model_dump()

    def _post_process(self, edsl_answer_dict: EdslAnswerDict) -> EdslAnswerDict:
        return edsl_answer_dict

    @classmethod
    def example(cls, question_type="numerical"):
        from edsl import Question

        q = Question.example(question_type)
        return q.response_validator


# Example usage
if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
