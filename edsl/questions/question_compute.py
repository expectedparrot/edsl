from __future__ import annotations
from typing import Optional, Any

from pydantic import BaseModel

from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC
from .decorators import inject_exception


class ComputeResponse(BaseModel):
    """
    Pydantic model for validating compute responses.
    
    This model defines the structure for responses from compute questions,
    which return the rendered question text directly without LLM processing.
    
    Attributes:
        answer: The rendered question text
        comment: Optional comment about the computation
        generated_tokens: Optional token usage data (always None for compute questions)
    """
    
    answer: Any
    comment: Optional[str] = None
    generated_tokens: Optional[str] = None


class ComputeResponseValidator(ResponseValidatorABC):
    """
    Validator for compute question responses.
    
    Since compute questions return the rendered question text directly,
    this validator is minimal and primarily serves for consistency.
    """
    
    required_params = []
    valid_examples = [
        ({"answer": "What is your favorite color?"}, {}),
        ({"answer": "Hello world", "comment": "Computed successfully"}, {}),
    ]
    invalid_examples = []
    
    def fix(self, response, verbose=False):
        """
        Attempt to fix an invalid response.
        
        Args:
            response: The response to fix
            verbose: Whether to print verbose output
            
        Returns:
            The fixed response or the original response if it cannot be fixed
        """
        if verbose:
            print(f"Fixing compute response: {response}")
        
        # Handle case where response is a raw value without the proper structure
        if not isinstance(response, dict):
            try:
                return {"answer": response}
            except Exception as e:
                if verbose:
                    print(f"Failed to fix response: {e}")
                return {"answer": None, "comment": "Failed to compute answer"}
        
        return response


class QuestionCompute(QuestionBase):
    """
    A question that returns the rendered question text directly without LLM processing.
    
    This question type is useful for generating computed or template-based text
    that doesn't require language model processing. It simply returns the
    rendered question_text after template substitution.
    
    Examples:
        >>> q = QuestionCompute(
        ...     question_name="greeting",
        ...     question_text="Hello {{name}}!"
        ... )
        >>> q.question_type
        'compute'
        
        >>> from edsl import Scenario
        >>> scenario = Scenario({"name": "World"})
        >>> result = q.by(scenario).run(disable_remote_cache=True, disable_remote_inference=True)
        >>> result.select("answer.*").to_list()[0]
        'Hello World!'
    """
    
    question_type = "compute"
    _response_model = ComputeResponse
    response_validator_class = ComputeResponseValidator
    
    def __init__(
        self,
        question_name: str,
        question_text: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        """
        Initialize a new compute question.
        
        Args:
            question_name: Identifier for the question, used in results and templates.
                          Must be a valid Python variable name.
            question_text: The text to render and return as the answer.
            answering_instructions: Optional instructions (not used for compute questions).
            question_presentation: Optional presentation template (not used for compute questions).
        """
        self.question_name = question_name
        self.question_text = question_text
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation
    
    def answer_question_directly(self, scenario, agent_traits=None):
        """
        Return the rendered question text as the answer.
        
        This method renders the question_text using the provided scenario
        and returns it as the answer without any LLM processing.
        
        Args:
            scenario: The scenario containing template variables
            agent_traits: Agent traits (not used for compute questions)
            
        Returns:
            dict: A dictionary containing the rendered question text as the answer
        """
        try:
            # Render the question text using the scenario
            # The scenario might be an enriched dictionary with prior answers
            if hasattr(scenario, 'data'):
                render_context = scenario.data
            elif isinstance(scenario, dict):
                render_context = scenario
            else:
                render_context = scenario
            rendered_question = self.render(render_context)
            rendered_text = rendered_question.question_text
            
            # Try to convert to numeric type if possible
            answer_value = self._try_numeric_conversion(rendered_text)
            
            result = {
                "answer": answer_value,
                "comment": None,
                "generated_tokens": None
            }
            
            # Validate the result using the Pydantic model
            return self._response_model(**result).model_dump()
            
        except Exception as e:
            print("Compute question error:", e)
            return {
                "answer": self.question_text,  # Return original text if rendering fails
                "comment": f"Error during computation: {str(e)}",
                "generated_tokens": None
            }
    
    def _try_numeric_conversion(self, text: str):
        """
        Try to convert the rendered text to a numeric type (int or float).
        
        Args:
            text: The rendered text to convert
            
        Returns:
            The converted numeric value if possible, otherwise the original text
        """
        if not isinstance(text, str):
            return text
        
        # Strip whitespace
        text = text.strip()
        
        # Try integer conversion first
        try:
            # Check if it's a whole number (no decimal point)
            if '.' not in text and 'e' not in text.lower():
                return int(text)
        except ValueError:
            pass
        
        # Try float conversion
        try:
            float_value = float(text)
            return float_value
        except ValueError:
            pass
        
        # Return original text if conversion fails
        return text
    
    @property
    def question_html_content(self) -> str:
        """
        Generate HTML content for rendering the question.
        
        Returns:
            str: HTML markup showing the computed result
        """
        return f'<div class="compute-question"><p>{self.question_text}</p></div>'
    
    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionCompute":
        """
        Create an example instance of a compute question.
        
        Args:
            randomize: If True, adds randomization to the example
            
        Returns:
            QuestionCompute: An example compute question
        """
        if randomize:
            from uuid import uuid4
            addition = str(uuid4())
            return cls(
                question_name="computed_greeting",
                question_text=f"Hello {{{{name}}}}! Your ID is {addition}"
            )
        
        return cls(
            question_name="computed_greeting",
            question_text="Hello {{name}}!"
        )


def main():
    """
    Demonstrate the functionality of the QuestionCompute class.
    """
    from edsl import Scenario
    
    # Create an example question
    q = QuestionCompute.example()
    print(f"Question text: {q.question_text}")
    print(f"Question name: {q.question_name}")
    
    # Test direct answer
    scenario = Scenario({"name": "World"})
    answer = q.answer_question_directly(scenario)
    print(f"Direct answer: {answer}")
    
    # Serialization demonstration
    serialized = q.to_dict()
    print(f"Serialized: {serialized}")
    
    from .question_base import QuestionBase
    deserialized = QuestionBase.from_dict(serialized)
    print(f"Deserialization successful: {deserialized.question_text == q.question_text}")


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)