from __future__ import annotations
from typing import Optional, Callable, Any
import inspect

from pydantic import BaseModel

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .exceptions import QuestionErrors, QuestionAnswerValidationError, QuestionNotImplementedError

from ..utilities.restricted_python import create_restricted_function


class FunctionalResponse(BaseModel):
    """
    Pydantic model for functional question responses.
    
    Since functional questions are evaluated directly by Python code rather than an LLM,
    this model primarily serves as a structured way to represent the output.
    
    Attributes:
        answer: The result of the function evaluation
        comment: Optional comment about the result
        generated_tokens: Optional token usage data
    
    Examples:
        >>> # Valid response with a numeric answer
        >>> response = FunctionalResponse(answer=42)
        >>> response.answer
        42
        
        >>> # Valid response with a string answer and a comment
        >>> response = FunctionalResponse(answer="Hello world", comment="Function executed successfully")
        >>> response.answer
        'Hello world'
        >>> response.comment
        'Function executed successfully'
    """
    answer: Any
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


class FunctionalResponseValidator(ResponseValidatorABC):
    """
    Validator for functional question responses.
    
    Since functional questions are evaluated directly and not by an LLM,
    this validator is minimal and mainly serves for consistency with other question types.
    """
    required_params = []
    valid_examples = [
        (
            {"answer": 42},
            {},
        ),
        (
            {"answer": "Hello world", "comment": "Function executed successfully"},
            {},
        ),
    ]
    invalid_examples = []
    
    def fix(self, response, verbose=False):
        """
        Attempt to fix an invalid response.
        
        Since functional questions are evaluated directly, this method is mainly
        for consistency with other question types.
        
        Args:
            response: The response to fix
            verbose: Whether to print verbose output
            
        Returns:
            The fixed response or the original response if it cannot be fixed
        """
        if verbose:
            print(f"Fixing functional response: {response}")
        
        # Handle case where response is a raw value without the proper structure
        if not isinstance(response, dict):
            try:
                return {"answer": response}
            except Exception as e:
                if verbose:
                    print(f"Failed to fix response: {e}")
                return {"answer": None, "comment": "Failed to execute function"}
                
        return response


class QuestionFunctional(QuestionBase):
    """A special type of question that is *not* answered by an LLM.

    >>> from edsl import Scenario, Agent

    # Create an instance of QuestionFunctional with the new function
    >>> question = QuestionFunctional.example()

    # Activate and test the function
    >>> question.activate()
    >>> scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    >>> agent = Agent(traits={"multiplier": 10})
    >>> results = question.by(scenario).by(agent).run(disable_remote_cache = True, disable_remote_inference = True)
    >>> results.select("answer.*").to_list()[0] == 150
    True

    # Serialize the question to a dictionary

    >>> from .question_base import QuestionBase
    >>> new_question = QuestionBase.from_dict(question.to_dict())
    >>> results = new_question.by(scenario).by(agent).run(disable_remote_cache = True, disable_remote_inference = True)
    >>> results.select("answer.*").to_list()[0] == 150
    True

    """

    question_type = "functional"
    default_instructions = ""
    activated = True
    function_source_code = ""
    function_name = ""

    _response_model = None
    response_validator_class = FunctionalResponseValidator

    def __init__(
        self,
        question_name: str,
        func: Optional[Callable] = None,
        question_text: Optional[str] = "Functional question",
        requires_loop: Optional[bool] = False,
        function_source_code: Optional[str] = None,
        function_name: Optional[str] = None,
        unsafe: Optional[bool] = False,
    ):
        super().__init__()
        if func:
            self.function_source_code = inspect.getsource(func)
            self.function_name = func.__name__
        else:
            self.function_source_code = function_source_code
            self.function_name = function_name

        self.requires_loop = requires_loop

        if unsafe:
            self.func = func
        else:
            self.func = create_restricted_function(
                self.function_name, self.function_source_code
            )

        self.question_name = question_name
        self.question_text = question_text
        self.instructions = self.default_instructions

    def create_response_model(self):
        """
        Returns the Pydantic model for validating responses to this question.
        """
        return FunctionalResponse

    def activate(self):
        self.activated = True

    def activate_loop(self):
        """Activate the function with loop logic using RestrictedPython."""
        self.func = create_restricted_function(
            self.function_name, self.function_source_code, loop_activated=True
        )

    def answer_question_directly(self, scenario, agent_traits=None):
        """Return the answer to the question, ensuring the function is activated."""
        if not self.activated:
            raise QuestionErrors("Function not activated. Please activate it first.")
        try:
            result = {"answer": self.func(scenario, agent_traits), "comment": None}
            # Validate the result using the Pydantic model
            return self.create_response_model()(**result).model_dump()
        except Exception as e:
            print("Function execution error:", e)
            raise QuestionErrors("Error during function execution.")

    def _translate_answer_code_to_answer(self, answer, scenario):
        """Required by Question, but not used by QuestionFunctional."""
        return None

    def _simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Required by Question, but not used by QuestionFunctional."""
        raise QuestionNotImplementedError("_simulate_answer not implemented for QuestionFunctional")

    def _validate_answer(self, answer: dict[str, str]):
        """Validate the answer using the Pydantic model."""
        try:
            return self.create_response_model()(**answer).model_dump()
        except Exception as e:
            from pydantic import ValidationError
            # Create a ValidationError with a helpful message
            validation_error = ValidationError.from_exception_data(
                title='FunctionalResponse',
                line_errors=[{
                    'type': 'value_error',
                    'loc': ('answer',),
                    'msg': f'Function response validation failed: {str(e)}',
                    'input': answer,
                    'ctx': {'error': str(e)}
                }]
            )
            raise QuestionAnswerValidationError(
                message=f"Invalid function response: {str(e)}",
                data=answer,
                model=self.create_response_model(),
                pydantic_error=validation_error
            )

    @property
    def question_html_content(self) -> str:
        return "NA for QuestionFunctional"

    # @add_edsl_version
    def to_dict(self, add_edsl_version=True):
        d = {
            "question_name": self.question_name,
            "function_source_code": self.function_source_code,
            "question_type": "functional",
            "requires_loop": self.requires_loop,
            "function_name": self.function_name,
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__

        return d

    @classmethod
    def example(cls):
        return cls(
            question_name="sum_and_multiply",
            func=calculate_sum_and_multiply,
            question_text="Calculate the sum of the list and multiply it by the agent trait multiplier.",
            requires_loop=True,
        )


def calculate_sum_and_multiply(scenario, agent_traits):
    numbers = scenario.get("numbers", [])
    multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1
    sum = 0
    for num in numbers:
        sum = sum + num
    return sum * multiplier


def main():
    from edsl import Scenario, Agent
    from .question_functional import QuestionFunctional

    # Create an instance of QuestionFunctional with the new function
    question = QuestionFunctional.example()

    # Activate and test the function
    question.activate()
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"multiplier": 10})
    results = question.by(scenario).by(agent).run()
    assert results.select("answer.*").to_list()[0] == 150


if __name__ == "__main__":
    # main()
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
