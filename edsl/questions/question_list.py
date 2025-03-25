from __future__ import annotations
import json
from typing import Any, Optional, Union, ForwardRef

from pydantic import Field, model_validator, ValidationError
from json_repair import repair_json
from .question_base import QuestionBase
from .descriptors import IntegerOrNoneDescriptor
from .decorators import inject_exception
from .response_validator_abc import ResponseValidatorABC

# Forward reference for function return type annotation
ListResponse = ForwardRef("ListResponse")

def convert_string(s: str) -> Union[float, int, str, dict]:
    """Convert a string to a more appropriate type if possible.

    >>> convert_string("3.14")
    3.14
    >>> convert_string("42")
    42
    >>> convert_string("hello")
    'hello'
    >>> convert_string('{"key": "value"}')
    {'key': 'value'}
    >>> convert_string("{'key': 'value'}")
    {'key': 'value'}
    """

    if not isinstance(s, str):  # if it's not a string, return it as is
        return s

    # If the repair returns, continue on; otherwise, try to load it as JSON
    if (repaired_json := repair_json(s)) == '""':
        pass
    else:
        try:
            return json.loads(repaired_json)
        except json.JSONDecodeError:
            pass

    # Try to convert to float
    try:
        return float(s)
    except ValueError:
        pass

    # Try to convert to int
    try:
        return int(s)
    except ValueError:
        pass

    # If all conversions fail, return the original string
    return s


def create_model(min_list_items: Optional[int], max_list_items: Optional[int], permissive: bool) -> "ListResponse":
    from pydantic import BaseModel

    if permissive or (max_list_items is None and min_list_items is None):
        class ListResponse(BaseModel):
            """
            Pydantic model for validating list responses with no constraints.
            
            Examples:
                >>> # Valid response with any number of items
                >>> response = ListResponse(answer=["one", "two", "three"])
                >>> response.answer
                ['one', 'two', 'three']
                
                >>> # Empty list is valid in permissive mode
                >>> response = ListResponse(answer=[])
                >>> response.answer
                []
                
                >>> # Missing answer field raises error
                >>> try:
                ...     ListResponse(you="will never be able to do this!")
                ... except Exception as e:
                ...     "Field required" in str(e)
                True
            """
            answer: list[Any]
            comment: Optional[str] = None
            generated_tokens: Optional[str] = None
            
            @classmethod
            def model_validate(cls, obj, *args, **kwargs):
                try:
                    return super().model_validate(obj, *args, **kwargs)
                except ValidationError as e:
                    from .exceptions import QuestionAnswerValidationError
                    raise QuestionAnswerValidationError(
                        message=f"Invalid list response: {e}",
                        data=obj,
                        model=cls,
                        pydantic_error=e
                    )

    else:
        # Determine field constraints
        field_kwargs = {"...": None}
        
        if min_list_items is not None:
            field_kwargs["min_items"] = min_list_items
            
        if max_list_items is not None:
            field_kwargs["max_items"] = max_list_items

        class ListResponse(BaseModel):
            """
            Pydantic model for validating list responses with size constraints.
            
            Examples:
                >>> # Create a model with min=2, max=4 items
                >>> ConstrainedList = create_model(min_list_items=2, max_list_items=4, permissive=False)
                
                >>> # Valid response within constraints
                >>> response = ConstrainedList(answer=["Apple", "Cherry", "Banana"])
                >>> len(response.answer)
                3
                
                >>> # Too few items raises error
                >>> try:
                ...     ConstrainedList(answer=["Apple"])
                ... except QuestionAnswerValidationError as e:
                ...     "must have at least 2 items" in str(e)
                True
                
                >>> # Too many items raises error
                >>> try:
                ...     ConstrainedList(answer=["A", "B", "C", "D", "E"])
                ... except QuestionAnswerValidationError as e:
                ...     "cannot have more than 4 items" in str(e)
                True
                
                >>> # Optional comment is allowed
                >>> response = ConstrainedList(
                ...     answer=["Apple", "Cherry"],
                ...     comment="These are my favorites"
                ... )
                >>> response.comment
                'These are my favorites'
                
                >>> # Generated tokens are optional
                >>> response = ConstrainedList(
                ...     answer=["Apple", "Cherry"],
                ...     generated_tokens="Apple, Cherry"
                ... )
                >>> response.generated_tokens
                'Apple, Cherry'
            """

            answer: list[Any] = Field(**field_kwargs)
            comment: Optional[str] = None
            generated_tokens: Optional[str] = None

            @model_validator(mode='after')
            def validate_list_constraints(self):
                """
                Validate that the list meets size constraints.
                
                Returns:
                    The validated model instance.
                    
                Raises:
                    QuestionAnswerValidationError: If list size constraints are violated.
                """
                if max_list_items is not None and len(self.answer) > max_list_items:
                    from .exceptions import QuestionAnswerValidationError
                    validation_error = ValidationError.from_exception_data(
                        title='ListResponse',
                        line_errors=[{
                            'type': 'value_error',
                            'loc': ('answer',),
                            'msg': f'List cannot have more than {max_list_items} items',
                            'input': self.answer,
                            'ctx': {'error': 'Too many items'}
                        }]
                    )
                    raise QuestionAnswerValidationError(
                        message=f"List cannot have more than {max_list_items} items",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error
                    )
                
                if min_list_items is not None and len(self.answer) < min_list_items:
                    from .exceptions import QuestionAnswerValidationError
                    validation_error = ValidationError.from_exception_data(
                        title='ListResponse',
                        line_errors=[{
                            'type': 'value_error',
                            'loc': ('answer',),
                            'msg': f'List must have at least {min_list_items} items',
                            'input': self.answer,
                            'ctx': {'error': 'Too few items'}
                        }]
                    )
                    raise QuestionAnswerValidationError(
                        message=f"List must have at least {min_list_items} items",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error
                    )
                return self
                
            @classmethod
            def model_validate(cls, obj, *args, **kwargs):
                try:
                    return super().model_validate(obj, *args, **kwargs)
                except ValidationError as e:
                    from .exceptions import QuestionAnswerValidationError
                    raise QuestionAnswerValidationError(
                        message=f"Invalid list response: {e}",
                        data=obj,
                        model=cls,
                        pydantic_error=e
                    )

    return ListResponse


class ListResponseValidator(ResponseValidatorABC):
    required_params = ["min_list_items", "max_list_items", "permissive"]
    valid_examples = [({"answer": ["hello", "world"]}, {"max_list_items": 5})]
    invalid_examples = [
        (
            {"answer": ["hello", "world", "this", "is", "a", "test"]},
            {"max_list_items": 5},
            "List cannot have more than 5 items",
        ),
        (
            {"answer": ["hello"]},
            {"min_list_items": 2},
            "List must have at least 2 items",
        ),
    ]
    
    def validate(
        self,
        raw_edsl_answer_dict: dict,
        fix=False,
        verbose=False,
        replacement_dict: dict = None,
    ) -> dict:
        """Override validate to handle missing answer key properly."""
        # Check for missing answer key
        if "answer" not in raw_edsl_answer_dict:
            from .exceptions import QuestionAnswerValidationError
            from pydantic import ValidationError
            
            # Create a synthetic validation error
            validation_error = ValidationError.from_exception_data(
                title='ListResponse',
                line_errors=[{
                    'type': 'missing',
                    'loc': ('answer',),
                    'msg': 'Field required',
                    'input': raw_edsl_answer_dict,
                }]
            )
            
            raise QuestionAnswerValidationError(
                message="Missing required 'answer' field in response",
                data=raw_edsl_answer_dict,
                model=self.response_model,
                pydantic_error=validation_error
            )
        
        # Check if answer is not a list
        if "answer" in raw_edsl_answer_dict and not isinstance(raw_edsl_answer_dict["answer"], list):
            from .exceptions import QuestionAnswerValidationError
            from pydantic import ValidationError
            
            # Create a synthetic validation error
            validation_error = ValidationError.from_exception_data(
                title='ListResponse',
                line_errors=[{
                    'type': 'list_type',
                    'loc': ('answer',),
                    'msg': 'Input should be a valid list',
                    'input': raw_edsl_answer_dict["answer"],
                }]
            )
            
            raise QuestionAnswerValidationError(
                message=f"Answer must be a list (got {type(raw_edsl_answer_dict['answer']).__name__})",
                data=raw_edsl_answer_dict,
                model=self.response_model,
                pydantic_error=validation_error
            )
        
        # Continue with parent validation
        return super().validate(raw_edsl_answer_dict, fix, verbose, replacement_dict)

    def _check_constraints(self, response) -> None:
        # This method can now be removed since validation is handled in the Pydantic model
        pass

    def fix(self, response, verbose=False):
        """
        Fix common issues in list responses by splitting strings into lists.
        
        Examples:
            >>> from edsl import QuestionList
            >>> q = QuestionList.example(min_list_items=2, max_list_items=4)
            >>> validator = q.response_validator
            
            >>> # Fix a string that should be a list
            >>> bad_response = {"answer": "apple,banana,cherry"}
            >>> try:
            ...     validator.validate(bad_response)
            ... except Exception:
            ...     fixed = validator.fix(bad_response)
            ...     validated = validator.validate(fixed)
            ...     validated  # Show full response
            {'answer': ['apple', 'banana', 'cherry'], 'comment': None, 'generated_tokens': None}

            >>> # Fix using generated_tokens when answer is invalid
            >>> bad_response = {
            ...     "answer": None,
            ...     "generated_tokens": "pizza, pasta, salad"
            ... }
            >>> try:
            ...     validator.validate(bad_response)
            ... except Exception:
            ...     fixed = validator.fix(bad_response)
            ...     validated = validator.validate(fixed)
            ...     validated
            {'answer': ['pizza', ' pasta', ' salad'], 'comment': None, 'generated_tokens': None}

            >>> # Preserve comments during fixing
            >>> bad_response = {
            ...     "answer": "red,blue,green",
            ...     "comment": "These are colors"
            ... }
            >>> fixed = validator.fix(bad_response)
            >>> fixed == {
            ...     "answer": ["red", "blue", "green"],
            ...     "comment": "These are colors"
            ... }
            True
        """
        if verbose:
            print(f"Fixing list response: {response}")
        answer = str(response.get("answer") or response.get("generated_tokens", ""))
        result = {"answer": answer.split(",")}
        if "comment" in response:
            result["comment"] = response["comment"]
        return result

    def _post_process(self, edsl_answer_dict):
        edsl_answer_dict["answer"] = [
            convert_string(item) for item in edsl_answer_dict["answer"]
        ]
        return edsl_answer_dict


class QuestionList(QuestionBase):
    """This question prompts the agent to answer by providing a list of items as comma-separated strings."""

    question_type = "list"
    max_list_items: int = IntegerOrNoneDescriptor()
    min_list_items: int = IntegerOrNoneDescriptor()
    _response_model = None
    response_validator_class = ListResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        include_comment: bool = True,
        max_list_items: Optional[int] = None,
        min_list_items: Optional[int] = None,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        permissive: bool = False,
    ):
        """Instantiate a new QuestionList.

        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param max_list_items: The maximum number of items that can be in the answer list.
        :param min_list_items: The minimum number of items that must be in the answer list.

        >>> QuestionList.example().self_check()
        """
        self.question_name = question_name
        self.question_text = question_text
        self.max_list_items = max_list_items
        self.min_list_items = min_list_items
        self.permissive = permissive

        self.include_comment = include_comment
        self.answering_instructions = answering_instructions
        self.question_presentations = question_presentation

    def create_response_model(self):
        return create_model(self.min_list_items, self.max_list_items, self.permissive)

    @property
    def question_html_content(self) -> str:
        from jinja2 import Template

        question_html_content = Template(
            """
        <div id="question-list-container">
            <div>
                <textarea name="{{ question_name }}[]" rows="1" placeholder="Enter item"></textarea>
            </div>
        </div>
        <button type="button" onclick="addNewLine()">Add another line</button>

        <script>
            function addNewLine() {
                var container = document.getElementById('question-list-container');
                var newLine = document.createElement('div');
                newLine.innerHTML = '<textarea name="{{ question_name }}[]" rows="1" placeholder="Enter item"></textarea>';
                container.appendChild(newLine);
            }
        </script>
        """
        ).render(question_name=self.question_name)
        return question_html_content

    @classmethod
    @inject_exception
    def example(
        cls, include_comment=True, max_list_items=None, min_list_items=None, permissive=False
    ) -> QuestionList:
        """Return an example of a list question."""
        return cls(
            question_name="list_of_foods",
            question_text="What are your favorite foods?",
            include_comment=include_comment,
            max_list_items=max_list_items,
            min_list_items=min_list_items,
            permissive=permissive,
        )


def main():
    """Create an example of a list question and demonstrate its functionality."""
    from edsl.questions import QuestionList

    q = QuestionList.example(max_list_items=5, min_list_items=2)
    q.question_text
    q.question_name
    q.max_list_items
    q.min_list_items
    # validate an answer
    q._validate_answer({"answer": ["pasta", "garlic", "oil", "parmesan"]})
    # translate answer code
    q._translate_answer_code_to_answer(["pasta", "garlic", "oil", "parmesan"])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
