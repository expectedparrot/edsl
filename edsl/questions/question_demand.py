from __future__ import annotations
from typing import Optional, List, Any, Union
import re

from pydantic import BaseModel, Field, model_validator, ValidationError

from .question_base import QuestionBase
from .descriptors import QuestionOptionsDescriptor
from .response_validator_abc import ResponseValidatorABC
from .exceptions import QuestionAnswerValidationError


class DemandResponse(BaseModel):
    """
    Pydantic model for validating demand curve responses.

    This model defines the structure and validation rules for responses to
    demand questions, ensuring responses contain a list of numerical values
    representing quantities demanded at each price point.

    Attributes:
        answer: List of non-negative numbers representing quantities demanded
        comment: Optional comment provided with the answer
        generated_tokens: Optional raw LLM output for token tracking

    Examples:
        >>> # Valid response with just answer
        >>> response = DemandResponse(answer=[10, 8, 5, 2])
        >>> response.answer
        [10.0, 8.0, 5.0, 2.0]

        >>> # Valid response with comment
        >>> response = DemandResponse(answer=[10, 8, 5, 2], comment="Typical downward sloping demand")
        >>> response.answer
        [10.0, 8.0, 5.0, 2.0]
        >>> response.comment
        'Typical downward sloping demand'

        >>> # Invalid non-list answer
        >>> try:
        ...     DemandResponse(answer="not a list")
        ... except Exception as e:
        ...     print("Validation error occurred")
        Validation error occurred
    """

    answer: List[float]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_demand_model(prices: List[Union[int, float]]):
    """
    Create a constrained demand response model with appropriate validation.

    This function creates a Pydantic model for demand responses with
    constraints on the number of quantities and non-negativity.

    Args:
        prices: List of price points for which quantities should be provided

    Returns:
        A Pydantic model class tailored to the question's constraints

    Examples:
        >>> # Create model with constraints
        >>> prices = [1.0, 2.0, 3.0, 4.0]
        >>> ConstrainedModel = create_demand_model(prices)
        >>> response = ConstrainedModel(answer=[10, 8, 5, 2])
        >>> response.answer
        [10.0, 8.0, 5.0, 2.0]

        >>> # Test count constraint
        >>> try:
        ...     ConstrainedModel(answer=[10, 8, 5])
        ... except Exception as e:
        ...     "Must provide" in str(e) and "quantities" in str(e)
        True

        >>> # Test negative values constraint
        >>> try:
        ...     ConstrainedModel(answer=[10, 8, -5, 2])
        ... except Exception as e:
        ...     "non-negative" in str(e)
        True
    """

    class ConstrainedDemandResponse(DemandResponse):
        """Demand response model with added constraints on count and non-negativity."""

        answer: List[float] = Field(
            ...,
            description="List of non-negative numbers representing quantities demanded at each price",
            min_length=len(prices),
            max_length=len(prices),
        )

        @model_validator(mode="after")
        def validate_demand_constraints(self):
            """Validate that the demand response meets all constraints."""
            # Check length constraint
            if len(self.answer) != len(prices):
                validation_error = ValidationError.from_exception_data(
                    title="ConstrainedDemandResponse",
                    line_errors=[
                        {
                            "type": "value_error",
                            "loc": ("answer",),
                            "msg": f"Must provide {len(prices)} quantities (one for each price)",
                            "input": self.answer,
                            "ctx": {"error": "Invalid item count"},
                        }
                    ],
                )
                raise QuestionAnswerValidationError(
                    message=f"Must provide {len(prices)} quantities (one for each price)",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error,
                )

            # Check for negative values
            if any(x < 0 for x in self.answer):
                validation_error = ValidationError.from_exception_data(
                    title="ConstrainedDemandResponse",
                    line_errors=[
                        {
                            "type": "value_error",
                            "loc": ("answer",),
                            "msg": "All quantities must be non-negative",
                            "input": self.answer,
                            "ctx": {"error": "Negative values"},
                        }
                    ],
                )
                raise QuestionAnswerValidationError(
                    message="All quantities must be non-negative",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error,
                )

            return self

    return ConstrainedDemandResponse


class DemandResponseValidator(ResponseValidatorABC):
    """
    Validator for demand question responses.

    This class implements the validation and fixing logic for demand curve
    responses, ensuring they meet the requirements for item count and non-negative values.

    Attributes:
        required_params: List of required parameters for validation
        valid_examples: Examples of valid responses for testing
        invalid_examples: Examples of invalid responses for testing

    Examples:
        >>> from edsl import QuestionDemand
        >>> q = QuestionDemand.example()
        >>> validator = q.response_validator

        >>> # Fix string to list
        >>> response = {"answer": "10, 8, 5, 2"}
        >>> fixed = validator.fix(response)
        >>> list(fixed.keys())
        ['answer']

        >>> # Preserve comments when fixing
        >>> response = {"answer": "10, 8, 5, 2", "comment": "My demand curve"}
        >>> fixed = validator.fix(response)
        >>> "comment" in fixed
        True
    """

    required_params = ["prices"]

    valid_examples = [
        (
            {"answer": [10, 8, 5, 2]},
            {"prices": [1.0, 2.0, 3.0, 4.0]},
        ),
        (
            {"answer": [0, 0, 0, 0]},
            {"prices": [1.0, 2.0, 3.0, 4.0]},
        ),
    ]

    invalid_examples = [
        (
            {"answer": [10, 8, -5, 2]},
            {"prices": [1.0, 2.0, 3.0, 4.0]},
            "Quantities must be non-negative",
        ),
        (
            {"answer": [10, 8, 5]},
            {"prices": [1.0, 2.0, 3.0, 4.0]},
            "Must provide correct number of quantities",
        ),
    ]

    def fix(self, response, verbose=False):
        """
        Fix common issues in demand responses.

        This method attempts to convert various response formats into a valid
        demand curve list, handling string inputs, comma-separated values,
        and dictionary formats.

        Args:
            response: The response dictionary to fix
            verbose: If True, print information about the fixing process

        Returns:
            A fixed version of the response dictionary

        Notes:
            - Handles string inputs by splitting on commas
            - Converts dictionaries to lists
            - Preserves any comment in the original response
        """
        if verbose:
            print(f"Fixing demand response: {response}")

        # Start with a default answer
        fixed_answer = []

        # Extract the answer field or use generated_tokens as fallback
        answer = response.get("answer")
        if answer is None:
            answer = response.get("generated_tokens", "")

        # Strategy 1: Handle string inputs with comma separators
        if isinstance(answer, str):
            # Split by commas and convert to floats
            try:
                fixed_answer = [
                    float(x.strip()) for x in answer.split(",") if x.strip()
                ]
            except ValueError:
                # If conversion fails, try to extract numbers using regex
                pattern = r"\b\d+(?:\.\d+)?\b"
                matches = re.findall(pattern, answer.replace(",", " "))
                if matches:
                    fixed_answer = [float(match) for match in matches]

        # Strategy 2: Handle dictionary inputs (convert to list)
        elif isinstance(answer, dict):
            # If keys are numeric or string indices, convert to a list
            try:
                # Sort by key (if keys are integers or can be converted to integers)
                sorted_keys = sorted(
                    answer.keys(),
                    key=lambda k: int(k) if isinstance(k, str) and k.isdigit() else k,
                )
                fixed_answer = [float(answer[k]) for k in sorted_keys]
            except (ValueError, TypeError):
                # If we can't sort, just take values in whatever order
                fixed_answer = [float(v) for v in answer.values()]

        # Strategy 3: If it's already a list but might contain non-numeric values
        elif isinstance(answer, list):
            try:
                fixed_answer = [float(x) for x in answer]
            except (ValueError, TypeError):
                pass

        if verbose:
            print(f"Fixed answer: {fixed_answer}")

        # Construct the response
        fixed_response = {"answer": fixed_answer}

        # Preserve comment if present
        if "comment" in response:
            fixed_response["comment"] = response["comment"]

        return fixed_response

    def _check_constraints(self, pydantic_edsl_answer: BaseModel):
        """Method preserved for compatibility, constraints handled in Pydantic model."""
        pass


class QuestionDemand(QuestionBase):
    """
    A question that prompts the agent to provide quantities demanded at different prices.

    QuestionDemand is designed for economic scenarios where you want to understand
    how demand varies with price. The agent provides a quantity they would purchase
    at each specified price point, creating a demand curve.

    Attributes:
        question_type: Identifier for this question type, set to "demand"
        prices: List of price points at which to elicit quantity demanded
        _response_model: Initially None, set by create_response_model()
        response_validator_class: Class used to validate and fix responses

    Examples:
        >>> # Create demand curve question
        >>> q = QuestionDemand(
        ...     question_name="coffee_demand",
        ...     question_text="How many cups of coffee would you buy per week at each price?",
        ...     prices=[1.0, 2.0, 3.0, 4.0, 5.0]
        ... )
        >>> q.prices
        [1.0, 2.0, 3.0, 4.0, 5.0]
        >>> len(q.prices)
        5
    """

    question_type = "demand"
    prices: List[Union[int, float]] = QuestionOptionsDescriptor(q_demand=True)
    _response_model = None
    response_validator_class = DemandResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        prices: List[Union[int, float]],
        include_comment: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
    ):
        """
        Initialize a new demand curve question.

        Args:
            question_name: Identifier for the question, used in results and templates
            question_text: The actual text of the question to be asked
            prices: The price points at which to elicit quantity demanded
            include_comment: Whether to allow comments with the answer
            question_presentation: Optional custom presentation template
            answering_instructions: Optional additional instructions

        Examples:
            >>> q = QuestionDemand(
            ...     question_name="apple_demand",
            ...     question_text="How many apples would you buy at each price?",
            ...     prices=[0.5, 1.0, 1.5, 2.0]
            ... )
            >>> q.question_name
            'apple_demand'
        """
        self.question_name = question_name
        self.question_text = question_text
        self.prices = prices
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions
        self.include_comment = include_comment

    def create_response_model(self):
        """
        Create a response model with the appropriate constraints.

        This method creates a Pydantic model customized with the price constraints
        specified for this question instance.

        Returns:
            A Pydantic model class tailored to this question's constraints

        Examples:
            >>> q = QuestionDemand.example()
            >>> model = q.create_response_model()
            >>> model(answer=[10, 8, 5, 2]).answer
            [10.0, 8.0, 5.0, 2.0]
        """
        return create_demand_model(self.prices)

    def _translate_answer_code_to_answer(
        self, answer_code, combined_dict
    ) -> list[dict]:
        """
        Translate the answer codes to the actual answers.

        For example, for a demand question with prices [1, 2, 3],
        and answer values [10, 5, 2], this method will create a list of
        dictionaries mapping each price to its corresponding quantity.

        Args:
            answer_code: List of quantity values
            combined_dict: Additional context (unused)

        Returns:
            List of dictionaries mapping prices to their quantity values

        Examples:
            >>> q = QuestionDemand.example()
            >>> q._translate_answer_code_to_answer([10, 8, 5, 2], {})
            [{'$1.00': 10}, {'$2.00': 8}, {'$3.00': 5}, {'$4.00': 2}]
        """
        translated_codes = []
        for quantity, price in zip(answer_code, self.prices):
            translated_codes.append({f"${price:.2f}": quantity})

        return translated_codes

    def _simulate_answer(self, human_readable=True):
        """
        Simulate a valid answer for debugging purposes.

        This method generates a random demand curve that satisfies the
        constraints of the question, useful for testing and demonstrations.
        Typically generates a downward-sloping demand curve.

        Args:
            human_readable: Whether to use price text (True) or indices (False)

        Returns:
            A dictionary containing a valid simulated answer

        Examples:
            >>> import random
            >>> random.seed(42)  # For reproducible test
            >>> q = QuestionDemand.example()
            >>> simulated = q._simulate_answer()
            >>> len(simulated["answer"])
            4
            >>> all(isinstance(x, (int, float)) for x in simulated["answer"])
            True
        """
        import random
        from edsl.utilities.utilities import random_string

        # Generate a downward-sloping demand curve with some randomness
        base_quantity = random.randint(5, 20)
        quantities = []

        for i, price in enumerate(self.prices):
            # Decrease quantity as price increases, with some randomness
            quantity = max(0, base_quantity - i * random.randint(1, 3))
            quantities.append(quantity)

        return {
            "answer": quantities,
            "comment": random_string() if self.include_comment else None,
        }

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.

        This property generates HTML markup for the question when it needs to be
        displayed in web interfaces or HTML contexts, including an interactive
        form with input fields for each price point.

        Returns:
            str: HTML markup for rendering the question
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <form id="demandForm">
        <p>{{ question_text }}</p>
        <table>
            <tr>
                <th>Price</th>
                <th>Quantity</th>
            </tr>
        {% for price in prices %}
            <tr>
                <td>${{ "%.2f"|format(price) }}</td>
                <td><input type="number" id="price_{{ loop.index0 }}" name="{{ question_name }}[{{ loop.index0 }}]" value="0" min="0" step="any"></td>
            </tr>
        {% endfor %}
        </table>
        </form>
        """
        ).render(
            question_name=self.question_name,
            question_text=self.question_text,
            prices=self.prices,
        )
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls, include_comment: bool = True) -> QuestionDemand:
        """
        Create an example instance of a demand question.

        This class method creates a predefined example of a demand question
        for demonstration, testing, and documentation purposes.

        Args:
            include_comment: Whether to include a comment field with the answer

        Returns:
            QuestionDemand: An example demand question

        Examples:
            >>> q = QuestionDemand.example()
            >>> q.question_name
            'coffee_demand'
            >>> q.question_text
            'How many cups of coffee would you buy per week at each price?'
            >>> q.prices
            [1.0, 2.0, 3.0, 4.0]
        """
        return cls(
            question_name="coffee_demand",
            question_text="How many cups of coffee would you buy per week at each price?",
            prices=[1.0, 2.0, 3.0, 4.0],
            include_comment=include_comment,
        )


def main():
    """
    Demonstrate the functionality of the QuestionDemand class.

    This function creates an example demand question and demonstrates its
    key features including validation, serialization, and answer simulation.
    It's primarily intended for testing and development purposes.

    Note:
        This function will be executed when the module is run directly,
        but not when imported.
    """
    # Create an example question
    q = QuestionDemand.example()

    print(f"Question text: {q.question_text}")
    print(f"Prices: {q.prices}")

    # Validate an answer
    valid_answer = {"answer": [10, 8, 5, 2]}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")

    # Simulate an answer
    simulated = q._simulate_answer()
    print(f"Simulated answer: {simulated}")

    # Translate answer code
    translated = q._translate_answer_code_to_answer([10, 8, 5, 2], {})
    print(f"Translated answer: {translated}")

    # Serialization demonstration
    serialized = q.to_dict()
    print(f"Serialized: {serialized}")
    deserialized = QuestionBase.from_dict(serialized)
    print(
        f"Deserialization successful: {deserialized.question_text == q.question_text}"
    )

    # Run doctests
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
    print("Doctests completed")


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # Uncomment to run demonstration
    # main()
