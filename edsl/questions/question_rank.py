from __future__ import annotations
from typing import Optional, Any, List, Union
import random
import re

from pydantic import BaseModel, Field, model_validator, ValidationError

from .question_base import QuestionBase
from .descriptors import (
    QuestionOptionsDescriptor,
    NumSelectionsDescriptor,
)
from .response_validator_abc import ResponseValidatorABC
from .exceptions import QuestionAnswerValidationError
from ..scenarios import Scenario


class RankResponseBase(BaseModel):
    """
    Base model for rank question responses.
    
    Attributes:
        answer: A list of selected choices in ranked order
        comment: Optional comment about the ranking
        generated_tokens: Optional token usage data
    
    Examples:
        >>> # Valid response with numeric indices
        >>> model = RankResponseBase(answer=[0, 1], comment="First and second choices")
        >>> model.answer
        [0, 1]
        
        >>> # Valid response with string options
        >>> model = RankResponseBase(answer=["Pizza", "Pasta"])
        >>> model.answer
        ['Pizza', 'Pasta']
    """
    answer: List[Any]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_response_model(
    choices: Union[list, range],
    num_selections: Optional[int] = None,
    permissive: bool = False,
):
    """
    Creates a Pydantic model for rank question responses with appropriate validation.
    
    Args:
        choices: A list of allowed values for the answer field
        num_selections: The exact number of selections required (if not permissive)
        permissive: If True, allows any number of selections
        
    Returns:
        A Pydantic model class for validating rank responses
    
    Examples:
        >>> # Create a model for ranking 2 options from ["Pizza", "Pasta", "Salad", "Soup"]
        >>> Model = create_response_model(["Pizza", "Pasta", "Salad", "Soup"], num_selections=2)
        >>> response = Model(answer=["Pizza", "Pasta"])
        >>> response.answer
        ['Pizza', 'Pasta']
        
        >>> # Invalid: too many selections
        >>> try:
        ...     Model(answer=["Pizza", "Pasta", "Salad"])
        ... except Exception:
        ...     print("Validation error occurred")
        Validation error occurred
    """
    # Convert the choices to a tuple for Literal type annotation
    choice_tuple = tuple(choices) if not isinstance(choices, range) else tuple(choices)
    
    # Create a custom validation model that extends the base model
    class RankResponse(RankResponseBase):
        """
        Model for rank question responses with validation for the specific choices and constraints.
        """
        # Use Annotated to add field metadata while keeping the type as List[Any]
        # We'll validate the actual items in the model_validator
        answer: List[Any] = Field(..., description="List of selected choices in ranked order")
        
        @model_validator(mode='after')
        def validate_answer_items(self):
            """
            Validates that:
            1. All items in the answer are valid choices
            2. The correct number of selections is made (if not permissive)
            3. No duplicates exist in the ranking
            """
            answer = self.answer
            
            # Check if the correct number of selections is made
            if num_selections is not None and not permissive:
                if len(answer) != num_selections:
                    validation_error = ValidationError.from_exception_data(
                        title='RankResponse',
                        line_errors=[{
                            'type': 'value_error',
                            'loc': ('answer',),
                            'msg': f'Expected exactly {num_selections} selections, got {len(answer)}',
                            'input': answer,
                            'ctx': {'expected': num_selections, 'actual': len(answer)}
                        }]
                    )
                    raise QuestionAnswerValidationError(
                        message=f"Number of selections must be exactly {num_selections}",
                        data=self.model_dump(),
                        model=self.__class__,
                        pydantic_error=validation_error
                    )
            
            # Check for duplicates
            if len(answer) != len(set(answer)):
                validation_error = ValidationError.from_exception_data(
                    title='RankResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': 'Duplicate items found in ranking',
                        'input': answer,
                        'ctx': {'error': 'Duplicate items are not allowed in rankings'}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message="Rankings must not contain duplicate items",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
            
            # If not permissive, validate that all items are in the allowed choices
            if not permissive:
                # Check each item against the allowed choices
                for idx, item in enumerate(answer):
                    if item not in choice_tuple:
                        validation_error = ValidationError.from_exception_data(
                            title='RankResponse',
                            line_errors=[{
                                'type': 'value_error',
                                'loc': ('answer', idx),
                                'msg': f'Value {item} is not a valid choice',
                                'input': item,
                                'ctx': {'allowed_values': choice_tuple}
                            }]
                        )
                        raise QuestionAnswerValidationError(
                            message=f"Item '{item}' is not in the allowed choices",
                            data=self.model_dump(),
                            model=self.__class__,
                            pydantic_error=validation_error
                        )
            
            return self
        
        class Config:
            @staticmethod
            def json_schema_extra(schema: dict, model: BaseModel) -> None:
                # Add the list of choices to the schema for better documentation
                for prop in schema.get("properties", {}).values():
                    if prop.get("title") == "answer":
                        prop["items"] = {"enum": list(choices) if not isinstance(choices, range) else list(choices)}

    return RankResponse


class RankResponseValidator(ResponseValidatorABC):
    """
    Validator for rank question responses that attempts to fix invalid responses.
    
    This validator tries multiple strategies to recover a valid ranking from
    malformed responses, including parsing comma-separated strings, extracting
    numbers or options from text, and more.
    """
    required_params = ["num_selections", "permissive", "use_code", "question_options"]
    
    valid_examples = [
        (
            {"answer": [0, 1]},
            {"num_selections": 2, "use_code": True, "permissive": False, 
             "question_options": ["Pizza", "Pasta", "Salad", "Soup"]},
        ),
        (
            {"answer": ["Pizza", "Pasta"]},
            {"num_selections": 2, "use_code": False, "permissive": False, 
             "question_options": ["Pizza", "Pasta", "Salad", "Soup"]},
        ),
    ]
    
    invalid_examples = [
        (
            {"answer": [0, 0]},
            {"num_selections": 2, "use_code": True, "permissive": False, 
             "question_options": ["Pizza", "Pasta", "Salad", "Soup"]},
            "Duplicate items found in ranking",
        ),
        (
            {"answer": [0, 1, 2]},
            {"num_selections": 2, "use_code": True, "permissive": False, 
             "question_options": ["Pizza", "Pasta", "Salad", "Soup"]},
            "Expected exactly 2 selections",
        ),
        (
            {"answer": [5, 6]},
            {"num_selections": 2, "use_code": True, "permissive": False, 
             "question_options": ["Pizza", "Pasta", "Salad", "Soup"]},
            "not in the allowed choices",
        ),
    ]

    def fix(self, response, verbose=False):
        """
        Attempts to fix an invalid rank response by trying multiple parsing strategies.
        
        Args:
            response: The invalid response to fix
            verbose: Whether to print verbose debugging information
            
        Returns:
            A fixed response dict if fixable, otherwise the original response
        """
        if verbose:
            print(f"Fixing rank response: {response}")
        
        # If there's no answer field or it's empty, nothing to fix
        if "answer" not in response or not response["answer"]:
            if verbose:
                print("No answer field or empty answer, nothing to fix")
            return response
        
        # Strategy 1: Parse from answer if it's a string
        if isinstance(response.get("answer"), str):
            text = response["answer"]
            # Try a few parsing approaches
            proposed_list = self._parse_answer_from_text(text)
            if proposed_list:
                proposed_data = {
                    "answer": proposed_list,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens")
                }
                try:
                    self.response_model(**proposed_data)
                    if verbose:
                        print(f"Successfully fixed by parsing string: {proposed_data}")
                    return proposed_data
                except Exception as e:
                    if verbose:
                        print(f"Failed to validate after string parsing: {e}")
        
        # Strategy 2: Try to parse from generated_tokens if available
        if "generated_tokens" in response and response["generated_tokens"]:
            text = str(response["generated_tokens"])
            proposed_list = self._parse_answer_from_text(text)
            
            if proposed_list:
                proposed_data = {
                    "answer": proposed_list,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens")
                }
                try:
                    self.response_model(**proposed_data)
                    if verbose:
                        print(f"Successfully fixed by parsing generated_tokens: {proposed_data}")
                    return proposed_data
                except Exception as e:
                    if verbose:
                        print(f"Failed to validate after generated_tokens parsing: {e}")
        
        # Strategy 3: Look for mentions of options in the text
        if isinstance(response.get("answer"), str) or "generated_tokens" in response:
            text = str(response.get("answer", "")) + " " + str(response.get("generated_tokens", ""))
            matches = []
            
            # Extract by index or by option text
            if self.use_code:
                # Look for indices in the text
                indices = re.findall(r'\b(\d+)\b', text)
                for idx in indices:
                    try:
                        idx_int = int(idx)
                        if 0 <= idx_int < len(self.question_options) and idx_int not in matches:
                            matches.append(idx_int)
                    except ValueError:
                        continue
            else:
                # Look for options in the text
                for option in self.question_options:
                    if option in text and option not in matches:
                        matches.append(option)
            
            # If we found enough matches, try to use them
            if matches and (self.permissive or len(matches) == self.num_selections):
                proposed_data = {
                    "answer": matches[:self.num_selections] if not self.permissive else matches,
                    "comment": response.get("comment"),
                    "generated_tokens": response.get("generated_tokens")
                }
                try:
                    self.response_model(**proposed_data)
                    if verbose:
                        print(f"Successfully fixed by extracting mentions: {proposed_data}")
                    return proposed_data
                except Exception as e:
                    if verbose:
                        print(f"Failed to validate after extracting mentions: {e}")
        
        # If we got here, we couldn't fix the response
        if verbose:
            print("Could not fix rank response, returning original")
        return response
    
    def _parse_answer_from_text(self, text):
        """
        Parse an answer list from text using multiple strategies.
        
        Args:
            text: The text to parse
            
        Returns:
            A list of parsed options or indices, or None if parsing failed
        """
        # Try comma-separated list
        proposed_list = (
            text.replace("[", "").replace("]", "").replace("'", "").replace('"', "").split(",")
        )
        proposed_list = [item.strip() for item in proposed_list if item.strip()]
        
        # Convert to integers if using code indices
        if self.use_code and proposed_list:
            try:
                proposed_list = [int(i) for i in proposed_list]
            except ValueError:
                # If conversion fails but we're using codes, try to extract numbers
                numbers = re.findall(r'\b(\d+)\b', text)
                if numbers:
                    try:
                        proposed_list = [int(num) for num in numbers]
                    except ValueError:
                        pass
        
        return proposed_list if proposed_list else None


class QuestionRank(QuestionBase):
    """
    A question that prompts the agent to rank options from a list.
    
    This question type asks respondents to put options in order of preference,
    importance, or any other ordering criteria. The response is a list of
    selected options in ranked order.
    
    Examples:
        >>> # Create a ranking question for food preferences
        >>> question = QuestionRank(
        ...     question_name="food_ranking",
        ...     question_text="Rank these foods from most to least favorite.",
        ...     question_options=["Pizza", "Pasta", "Salad", "Soup"],
        ...     num_selections=2
        ... )
        >>> # The response should be a ranked list
        >>> response = {"answer": ["Pizza", "Pasta"], "comment": "I prefer Italian food."}
    """

    question_type = "rank"
    question_options: list[str] = QuestionOptionsDescriptor()
    num_selections = NumSelectionsDescriptor()

    _response_model = None
    response_validator_class = RankResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        num_selections: Optional[int] = None,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
        use_code: bool = True,
        include_comment: bool = True,
    ):
        """
        Initialize a rank question.

        Args:
            question_name: The name of the question
            question_text: The text of the question
            question_options: The options the respondent should rank
            num_selections: The number of options to select and rank (defaults to all)
            question_presentation: Custom presentation template (optional)
            answering_instructions: Custom instructions template (optional)
            permissive: Whether to relax validation constraints
            use_code: Whether to use numeric indices (0,1,2) instead of option text
            include_comment: Whether to include a comment field
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.num_selections = num_selections or len(question_options)
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions
        self.permissive = permissive
        self.use_code = use_code
        self.include_comment = include_comment

    def create_response_model(self):
        """
        Returns the pydantic model for validating responses to this question.
        
        The model is dynamically created based on the question's configuration,
        including allowed choices, number of selections, and permissiveness.
        """
        choices = (
            self.question_options
            if not self.use_code
            else range(len(self.question_options))
        )
        return create_response_model(
            choices=choices,
            num_selections=self.num_selections,
            permissive=self.permissive,
        )

    def _translate_answer_code_to_answer(
        self, answer_codes, scenario: Scenario = None
    ) -> list[str]:
        """
        Translate numeric answer codes to the actual option text.
        
        Args:
            answer_codes: The codes to translate
            scenario: The scenario for template rendering (optional)
            
        Returns:
            A list of translated option texts
        """
        from jinja2 import Template
        
        scenario = scenario or Scenario()
        translated_options = [
            Template(option).render(scenario) for option in self.question_options
        ]
        translated_codes = []
        for answer_code in answer_codes:
            if self.use_code:
                translated_codes.append(translated_options[int(answer_code)])
            else:
                translated_codes.append(answer_code)
        return translated_codes

    def _simulate_answer(self, human_readable=True) -> dict:
        """
        Simulate a valid answer for testing purposes.
        
        Args:
            human_readable: Whether to use option text (True) or indices (False)
            
        Returns:
            A valid simulated response
        """
        from ..utilities.utilities import random_string

        # Handle the simulation logic based on use_code and human_readable flags
        if human_readable:
            if not self.use_code:
                # When human_readable=True and not using code, return text options
                selected = random.sample(self.question_options, self.num_selections)
            else:
                # When human_readable=True but we're configured to use_code, 
                # still use the option text for better test compatibility
                selected = random.sample(self.question_options, self.num_selections)
        else:
            # When human_readable=False, always use indices
            selected = random.sample(
                range(len(self.question_options)), self.num_selections
            )
            
        answer = {
            "answer": selected,
            "comment": random_string(),
        }
        return answer

    @property
    def question_html_content(self) -> str:
        """
        Generate an HTML representation of the ranking question.
        
        Returns:
            HTML content string for rendering the question
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <form id="rankForm">
            <p>{{ question_text }}</p>
            {% for option in question_options %}
            <div>
                <label for="{{ option }}">{{ option }}</label>
                <input type="number" id="{{ option }}" name="{{ question_name }}[{{ option }}]" value="0" min="1" max="{{ question_options|length }}" oninput="updateRankings()">
            </div>
            {% endfor %}
        </form>
        <script>
        function updateRankings() {
            let options = {{ question_options|length }};
            let values = [];
            let isValid = true;

            {% for option in question_options %}
            let value = parseInt(document.getElementById("{{ option }}").value) || 0;
            if (value > 0 && value <= options && !values.includes(value)) {
                values.push(value);
            } else if (value !== 0) {
                isValid = false;
            }
            {% endfor %}

            if (!isValid || values.length !== new Set(values).size) {
                document.getElementById("error").innerText = "Please enter unique and valid ranks for each option.";
            } else {
                document.getElementById("error").innerText = "";
            }
        }
        </script>
        <p id="error" style="color: red;"></p>
        """
        ).render(
            question_name=self.question_name,
            question_text=self.question_text,
            question_options=self.question_options,
        )
        return question_html_content

    @classmethod
    def example(cls, use_code=False, include_comment=True) -> QuestionRank:
        """
        Return an example rank question.
        
        Args:
            use_code: Whether to use numeric indices 
            include_comment: Whether to include a comment field
            
        Returns:
            An example QuestionRank instance
        """
        return cls(
            question_name="rank_foods",
            question_text="Rank your favorite foods.",
            question_options=["Pizza", "Pasta", "Salad", "Soup"],
            num_selections=2,
            use_code=use_code,
            include_comment=include_comment,
        )


def main():
    """Show example usage."""
    from edsl.questions import QuestionRank

    q = QuestionRank.example(use_code=True)
    q.question_text
    q.question_name
    q.question_options
    q.num_selections
    # validate an answer
    answer = {"answer": [0, 1], "comment": "I like pizza and pasta."}
    q._validate_answer(answer)
    # translate an answer code to an answer
    # q._translate_answer_code_to_answer([0, 1])
    # simulate answer
    q._simulate_answer()
    q._simulate_answer(human_readable=False)
    q._validate_answer(q._simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q

    q = QuestionRank.example(use_code=False)
    answer = {"answer": ["Pizza", "Pasta"], "comment": "I like pizza and pasta."}
    q._validate_answer(answer)

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
