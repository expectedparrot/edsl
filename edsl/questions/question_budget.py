from __future__ import annotations
from typing import Optional, List, Any
import re

from pydantic import BaseModel, Field, model_validator, ValidationError

from .question_base import QuestionBase
from .descriptors import IntegerDescriptor, QuestionOptionsDescriptor
from .response_validator_abc import ResponseValidatorABC
from .exceptions import QuestionAnswerValidationError


class BudgetResponse(BaseModel):
    """
    Pydantic model for validating budget allocation responses.
    
    This model defines the structure and validation rules for responses to
    budget questions, ensuring responses contain a list of numerical values
    representing allocations.
    
    Attributes:
        answer: List of float values representing budget allocation
        comment: Optional comment provided with the answer
        generated_tokens: Optional raw LLM output for token tracking
        
    Examples:
        >>> # Valid response with just answer
        >>> response = BudgetResponse(answer=[25, 25, 25, 25])
        >>> response.answer
        [25.0, 25.0, 25.0, 25.0]
        
        >>> # Valid response with comment
        >>> response = BudgetResponse(answer=[40, 30, 20, 10], comment="My allocation")
        >>> response.answer
        [40.0, 30.0, 20.0, 10.0]
        >>> response.comment
        'My allocation'
        
        >>> # Invalid non-list answer
        >>> try:
        ...     BudgetResponse(answer="not a list")
        ... except Exception as e:
        ...     print("Validation error occurred")
        Validation error occurred
    """
    answer: List[float]
    comment: Optional[str] = None
    generated_tokens: Optional[Any] = None


def create_budget_model(
    budget_sum: float, permissive: bool, question_options: List[str]
):
    """
    Create a constrained budget response model with appropriate validation.
    
    This function creates a Pydantic model for budget allocation responses with
    constraints on the number of values and total sum.
    
    Args:
        budget_sum: The total budget that must be allocated
        permissive: If True, allow allocations less than budget_sum
        question_options: List of options to allocate budget to
        
    Returns:
        A Pydantic model class tailored to the question's constraints
        
    Examples:
        >>> # Create model with constraints
        >>> options = ["Pizza", "Ice Cream", "Burgers", "Salad"]
        >>> ConstrainedModel = create_budget_model(100, False, options)
        >>> response = ConstrainedModel(answer=[25, 25, 25, 25])
        >>> response.answer
        [25.0, 25.0, 25.0, 25.0]
        
        >>> # Test count constraint
        >>> try:
        ...     ConstrainedModel(answer=[25, 25, 25])
        ... except Exception as e:
        ...     "List should have at least 4 items" in str(e)
        True
        
        >>> # Test negative values constraint
        >>> try:
        ...     ConstrainedModel(answer=[50, 50, 25, -25])
        ... except Exception as e:
        ...     "All values must be non-negative" in str(e)
        True
        
        >>> # Test sum constraint
        >>> try:
        ...     ConstrainedModel(answer=[30, 30, 30, 30])
        ... except Exception as e:
        ...     "Sum of numbers must equal 100" in str(e)
        True
        
        >>> # Permissive mode allows lower sums
        >>> PermissiveModel = create_budget_model(100, True, options)
        >>> response = PermissiveModel(answer=[20, 20, 20, 20])
        >>> response.answer
        [20.0, 20.0, 20.0, 20.0]
        
        >>> # But still prevents exceeding the budget
        >>> try:
        ...     PermissiveModel(answer=[30, 30, 30, 30])
        ... except Exception as e:
        ...     "Sum of numbers cannot exceed 100" in str(e)
        True
    """
    class ConstrainedBudgetResponse(BudgetResponse):
        """Budget response model with added constraints on count and total."""
        
        answer: List[float] = Field(
            ...,
            description="List of non-negative numbers representing budget allocation",
            min_length=len(question_options),
            max_length=len(question_options),
        )
        
        @model_validator(mode='after')
        def validate_budget_constraints(self):
            """Validate that the budget allocation meets all constraints."""
            # Check length constraint
            if len(self.answer) != len(question_options):
                validation_error = ValidationError.from_exception_data(
                    title='ConstrainedBudgetResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': f'Must provide {len(question_options)} values',
                        'input': self.answer,
                        'ctx': {'error': 'Invalid item count'}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"Must provide {len(question_options)} values",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
                
            # Check for negative values
            if any(x < 0 for x in self.answer):
                validation_error = ValidationError.from_exception_data(
                    title='ConstrainedBudgetResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': 'All values must be non-negative',
                        'input': self.answer,
                        'ctx': {'error': 'Negative values'}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message="All values must be non-negative",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
                
            # Check budget sum constraints
            total = sum(self.answer)
            if not permissive and total != budget_sum:
                validation_error = ValidationError.from_exception_data(
                    title='ConstrainedBudgetResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': f'Sum of numbers must equal {budget_sum}',
                        'input': self.answer,
                        'ctx': {'error': 'Invalid sum', 'total': total, 'expected': budget_sum}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"Sum of numbers must equal {budget_sum} (got {total})",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
            elif permissive and total > budget_sum:
                validation_error = ValidationError.from_exception_data(
                    title='ConstrainedBudgetResponse',
                    line_errors=[{
                        'type': 'value_error',
                        'loc': ('answer',),
                        'msg': f'Sum of numbers cannot exceed {budget_sum}',
                        'input': self.answer,
                        'ctx': {'error': 'Sum too large', 'total': total, 'max': budget_sum}
                    }]
                )
                raise QuestionAnswerValidationError(
                    message=f"Sum of numbers cannot exceed {budget_sum} (got {total})",
                    data=self.model_dump(),
                    model=self.__class__,
                    pydantic_error=validation_error
                )
                
            return self
        
    return ConstrainedBudgetResponse


class BudgetResponseValidator(ResponseValidatorABC):
    """
    Validator for budget question responses.
    
    This class implements the validation and fixing logic for budget allocation
    responses, ensuring they meet the requirements for item count, non-negative values,
    and budget total.
    
    Attributes:
        required_params: List of required parameters for validation
        valid_examples: Examples of valid responses for testing
        invalid_examples: Examples of invalid responses for testing
        
    Examples:
        >>> from edsl import QuestionBudget
        >>> q = QuestionBudget.example()
        >>> validator = q.response_validator
        
        >>> # Fix string to list
        >>> response = {"answer": "25, 25, 25, 25"}
        >>> fixed = validator.fix(response)
        >>> list(fixed.keys())
        ['answer']
        
        >>> # Preserve comments when fixing
        >>> response = {"answer": "25, 25, 25, 25", "comment": "My allocation"}
        >>> fixed = validator.fix(response)
        >>> "comment" in fixed
        True
    """
    required_params = ["budget_sum", "question_options", "permissive"]
    
    valid_examples = [
        ({"answer": [25, 25, 25, 25]}, {"budget_sum": 100, "question_options": ["A", "B", "C", "D"], "permissive": False}),
        ({"answer": [20, 20, 20, 20]}, {"budget_sum": 100, "question_options": ["A", "B", "C", "D"], "permissive": True}),
    ]
    
    invalid_examples = [
        ({"answer": [30, 30, 30, 30]}, {"budget_sum": 100, "question_options": ["A", "B", "C", "D"], "permissive": False}, "Sum must equal budget"),
        ({"answer": [25, 25, 25]}, {"budget_sum": 100, "question_options": ["A", "B", "C", "D"], "permissive": False}, "Must provide correct number of values"),
        ({"answer": [25, 25, -10, 60]}, {"budget_sum": 100, "question_options": ["A", "B", "C", "D"], "permissive": False}, "Values must be non-negative"),
    ]

    def fix(self, response, verbose=False):
        """
        Fix common issues in budget responses.
        
        This method attempts to convert various response formats into a valid
        budget allocation list, handling string inputs, comma-separated values,
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
            print(f"Fixing budget response: {response}")
            
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
                fixed_answer = [float(x.strip()) for x in answer.split(",") if x.strip()]
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
                sorted_keys = sorted(answer.keys(), key=lambda k: int(k) if isinstance(k, str) and k.isdigit() else k)
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


class QuestionBudget(QuestionBase):
    """
    A question that prompts the agent to allocate a budget among options.
    
    QuestionBudget is designed for scenarios where a fixed amount needs to be
    distributed across multiple categories or options. It's useful for allocation
    questions, spending priorities, resource distribution, and similar scenarios.
    
    Attributes:
        question_type: Identifier for this question type, set to "budget"
        budget_sum: The total amount to be allocated
        question_options: List of options to allocate the budget among
        _response_model: Initially None, set by create_response_model()
        response_validator_class: Class used to validate and fix responses
        
    Examples:
        >>> # Create budget allocation question
        >>> q = QuestionBudget(
        ...     question_name="spending",
        ...     question_text="How would you allocate $100?",
        ...     question_options=["Food", "Housing", "Entertainment", "Savings"],
        ...     budget_sum=100
        ... )
        >>> q.budget_sum
        100
        >>> len(q.question_options)
        4
    """
    question_type = "budget"
    budget_sum: int = IntegerDescriptor(none_allowed=False)
    question_options: list[str] = QuestionOptionsDescriptor(q_budget=True)
    _response_model = None
    response_validator_class = BudgetResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        question_options: list[str],
        budget_sum: int,
        include_comment: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        permissive: bool = False,
    ):
        """
        Initialize a new budget allocation question.
        
        Args:
            question_name: Identifier for the question, used in results and templates
            question_text: The actual text of the question to be asked
            question_options: The options for allocation of the budget sum
            budget_sum: The total amount of the budget to be allocated
            include_comment: Whether to allow comments with the answer
            question_presentation: Optional custom presentation template
            answering_instructions: Optional additional instructions
            permissive: If True, allow allocations less than budget_sum
            
        Examples:
            >>> q = QuestionBudget(
            ...     question_name="investment",
            ...     question_text="How would you invest $1000?",
            ...     question_options=["Stocks", "Bonds", "Real Estate", "Cash"],
            ...     budget_sum=1000
            ... )
            >>> q.question_name
            'investment'
        """
        self.question_name = question_name
        self.question_text = question_text
        self.question_options = question_options
        self.budget_sum = budget_sum
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions
        self.permissive = permissive
        self.include_comment = include_comment

    def create_response_model(self):
        """
        Create a response model with the appropriate constraints.
        
        This method creates a Pydantic model customized with the budget constraints
        and options specified for this question instance.
        
        Returns:
            A Pydantic model class tailored to this question's constraints
            
        Examples:
            >>> q = QuestionBudget.example()
            >>> model = q.create_response_model()
            >>> model(answer=[25, 25, 25, 25]).answer
            [25.0, 25.0, 25.0, 25.0]
        """
        return create_budget_model(
            self.budget_sum, self.permissive, self.question_options
        )

    def _translate_answer_code_to_answer(
        self, answer_code, combined_dict
    ) -> list[dict]:
        """
        Translate the answer codes to the actual answers.
        
        For example, for a budget question with options ["a", "b", "c"],
        and answer values [50, 30, 20], this method will create a list of
        dictionaries mapping each option to its allocated value.
        
        Args:
            answer_code: List of budget allocation values
            combined_dict: Additional context (unused)
            
        Returns:
            List of dictionaries mapping options to their allocation values
            
        Examples:
            >>> q = QuestionBudget.example()
            >>> q._translate_answer_code_to_answer([40, 30, 20, 10], {})
            [{'Pizza': 40}, {'Ice Cream': 30}, {'Burgers': 20}, {'Salad': 10}]
        """
        translated_codes = []
        for answer_value, question_option in zip(answer_code, self.question_options):
            translated_codes.append({question_option: answer_value})

        return translated_codes

    def _simulate_answer(self, human_readable=True):
        """
        Simulate a valid answer for debugging purposes.
        
        This method generates a random budget allocation that satisfies the
        constraints of the question, useful for testing and demonstrations.
        
        Args:
            human_readable: Whether to use option text (True) or indices (False)
            
        Returns:
            A dictionary containing a valid simulated answer
            
        Examples:
            >>> import random
            >>> random.seed(42)  # For reproducible test
            >>> q = QuestionBudget.example()
            >>> simulated = q._simulate_answer()
            >>> len(simulated["answer"])
            4
            >>> abs(sum(simulated["answer"]) - q.budget_sum) < 0.01  # Allow for float imprecision
            True
        """
        import random
        from edsl.utilities.utilities import random_string

        # Generate a random allocation that sums to budget_sum
        remaining_budget = self.budget_sum
        values = []
        
        for i in range(len(self.question_options)):
            if i == len(self.question_options) - 1:
                # Assign remaining budget to the last value
                values.append(remaining_budget)
            else:
                # Generate a random value between 0 and remaining budget
                value = random.randint(0, remaining_budget)
                values.append(value)
                remaining_budget -= value
                
        return {
            "answer": values,
            "comment": random_string() if self.include_comment else None,
        }

    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question in web interfaces.
        
        This property generates HTML markup for the question when it needs to be
        displayed in web interfaces or HTML contexts, including an interactive
        budget allocation form with JavaScript for real-time budget tracking.
        
        Returns:
            str: HTML markup for rendering the question
        """
        from jinja2 import Template

        question_html_content = Template(
            """
        <form id="budgetForm">
        <p>Total Budget: {{ budget_sum }}</p>
        <p>Remaining Budget: <span id="remainingBudget">{{ budget_sum }}</span></p>
        {% for option in question_options %}
        <div>
            <label for="{{ option }}">{{ option }}</label>
            <input type="number" id="{{ option }}" name="{{ question_name }}[{{ option }}]" value="0" min="0" max="{{ budget_sum }}" oninput="updateRemainingBudget()">
        </div>
        {% endfor %}
        </form>
        <script>
        function updateRemainingBudget() {
            let totalBudget = {{ budget_sum }};
            let allocated = 0;

            {% for option in question_options %}
            allocated += parseInt(document.getElementById("{{ option }}").value) || 0;
            {% endfor %}

            let remaining = totalBudget - allocated;
            document.getElementById('remainingBudget').innerText = remaining;

            {% for option in question_options %}
            document.getElementById("{{ option }}").max = remaining + parseInt(document.getElementById("{{ option }}").value);
            {% endfor %}
        }
        </script>
        """
        ).render(
            question_name=self.question_name,
            budget_sum=self.budget_sum,
            question_options=self.question_options,
        )
        return question_html_content

    ################
    # Helpful methods
    ################
    @classmethod
    def example(cls, include_comment: bool = True) -> QuestionBudget:
        """
        Create an example instance of a budget question.
        
        This class method creates a predefined example of a budget question
        for demonstration, testing, and documentation purposes.
        
        Args:
            include_comment: Whether to include a comment field with the answer
                           
        Returns:
            QuestionBudget: An example budget question
            
        Examples:
            >>> q = QuestionBudget.example()
            >>> q.question_name
            'food_budget'
            >>> q.question_text
            'How would you allocate $100?'
            >>> q.budget_sum
            100
            >>> q.question_options
            ['Pizza', 'Ice Cream', 'Burgers', 'Salad']
        """
        return cls(
            question_name="food_budget",
            question_text="How would you allocate $100?",
            question_options=["Pizza", "Ice Cream", "Burgers", "Salad"],
            budget_sum=100,
            include_comment=include_comment,
        )


def main():
    """
    Demonstrate the functionality of the QuestionBudget class.
    
    This function creates an example budget question and demonstrates its
    key features including validation, serialization, and answer simulation.
    It's primarily intended for testing and development purposes.
    
    Note:
        This function will be executed when the module is run directly,
        but not when imported.
    """
    # Create an example question
    q = QuestionBudget.example()
    
    print(f"Question text: {q.question_text}")
    print(f"Question options: {q.question_options}")
    print(f"Budget sum: {q.budget_sum}")
    
    # Validate an answer
    valid_answer = {"answer": [25, 25, 25, 25]}
    validated = q._validate_answer(valid_answer)
    print(f"Validated answer: {validated}")
    
    # Simulate an answer
    simulated = q._simulate_answer()
    print(f"Simulated answer: {simulated}")
    
    # Translate answer code
    translated = q._translate_answer_code_to_answer([40, 30, 20, 10], {})
    print(f"Translated answer: {translated}")
    
    # Serialization demonstration
    serialized = q.to_dict()
    print(f"Serialized: {serialized}")
    deserialized = QuestionBase.from_dict(serialized)
    print(f"Deserialization successful: {deserialized.question_text == q.question_text}")
    
    # Run doctests
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    print("Doctests completed")


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    
    # Uncomment to run demonstration
    # main()