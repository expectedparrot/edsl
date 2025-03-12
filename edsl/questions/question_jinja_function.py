"""
QuestionJinjaFunction - A question type that uses Jinja2 macros instead of RestrictedPython.

This question type allows for safely serializable functions using Jinja2's macro
language. It provides a way to define computational logic that can be serialized
and deserialized safely, without the security risks of arbitrary Python code execution.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, Callable
import inspect
import re
import jinja2

from .question_base import QuestionBase
from ..utilities.decorators import add_edsl_version, remove_edsl_version


class QuestionJinjaFunction(QuestionBase):
    """A question type that uses Jinja2 macros for safely serializable functions.
    
    This class allows defining computational logic using Jinja2 templates with macros
    rather than Python functions. The advantage is that Jinja2 macros are safely
    serializable as text and provide a restricted execution environment.
    
    Example usage:
    
    >>> from edsl import Scenario, Agent
    >>> from edsl.questions import QuestionJinjaFunction
    
    >>> # Define a Jinja2 macro template
    >>> template_str = '''
    ... {% macro sum_and_multiply(scenario, agent_traits) %}
    ...     {% set numbers = scenario.get("numbers", []) %}
    ...     {% set multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1 %}
    ...     {% set sum = 0 %}
    ...     {% for num in numbers %}
    ...         {% set sum = sum + num %}
    ...     {% endfor %}
    ...     {{ sum * multiplier }}
    ... {% endmacro %}
    ... '''
    
    >>> # Create the question
    >>> question = QuestionJinjaFunction(
    ...     question_name="sum_and_multiply",
    ...     jinja2_template=template_str,
    ...     macro_name="sum_and_multiply"
    ... )
    
    >>> # Use the question
    >>> scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    >>> agent = Agent(traits={"multiplier": 10})
    >>> results = question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    >>> results.select("answer.*").to_list()[0] == 150
    True
    """
    
    question_type = "jinja_function"
    default_instructions = ""
    jinja2_template = ""
    macro_name = ""
    environment = None
    
    _response_model = None
    response_validator_class = None
    
    def __init__(
        self,
        question_name: str,
        jinja2_template: str = "",
        macro_name: str = "",
        question_text: str = "Jinja2 Function",
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
        func_for_conversion: Optional[Callable] = None,
    ):
        """Initialize a QuestionJinjaFunction.
        
        Args:
            question_name: Unique identifier for the question
            jinja2_template: Jinja2 template string containing the macro definition
            macro_name: Name of the macro to call in the template
            question_text: Text description of the question
            question_presentation: Optional custom template for presenting the question
            answering_instructions: Optional custom instructions for answering
            func_for_conversion: Optional Python function to convert to a Jinja2 macro
        """
        super().__init__()
        
        self.question_name = question_name
        self.question_text = question_text
        self.question_presentation = question_presentation
        
        if answering_instructions:
            self.instructions = answering_instructions
        else:
            self.instructions = self.default_instructions
        
        # If a Python function is provided, convert it to a Jinja2 macro
        if func_for_conversion:
            self.jinja2_template, self.macro_name = self._convert_python_to_jinja2(func_for_conversion)
        else:
            self.jinja2_template = jinja2_template
            self.macro_name = macro_name
        
        # Set up the Jinja2 environment and compile the template
        self._setup_jinja2_environment()
    
    def _setup_jinja2_environment(self):
        """Set up the Jinja2 environment with the template."""
        # Create environment with additional controls and security measures
        self.environment = jinja2.Environment(
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Verify the template is valid
        try:
            template = self.environment.from_string(self.jinja2_template)
            # Test compile to catch errors early
            template.render()
        except jinja2.exceptions.TemplateSyntaxError as e:
            raise ValueError(f"Invalid Jinja2 template: {str(e)}")
        except Exception as e:
            # Don't worry about runtime errors at this stage
            pass
    
    def _convert_python_to_jinja2(self, func: Callable) -> (str, str):
        """Convert a simple Python function to an equivalent Jinja2 macro.
        
        This is a best-effort conversion and will not work for complex Python functions.
        It supports basic operations like assignment, arithmetic, and for loops.
        
        Args:
            func: The Python function to convert
            
        Returns:
            Tuple of (jinja2_template, macro_name)
        """
        source_code = inspect.getsource(func)
        macro_name = func.__name__
        
        # Extract function signature and body
        # Handle indented function definitions in test functions
        source_code = source_code.strip()
        
        # This more flexible pattern can handle indented functions
        pattern = r"(?:^|\s+)def\s+(\w+)\s*\((.*?)\):(.*)"
        match = re.match(pattern, source_code, re.DOTALL)
        if not match:
            raise ValueError(f"Could not parse function definition from:\n{source_code}")
        
        name, params, body = match.groups()
        params = params.strip()
        
        # Start the Jinja2 macro
        jinja2_code = f"{{% macro {name}({params}) %}}\n"
        
        # Convert basic Python constructs to Jinja2
        # This is a simple approach and won't handle complex cases
        lines = body.strip().split("\n")
        indent = len(lines[0]) - len(lines[0].lstrip())
        
        for line in lines:
            line = line[indent:].rstrip()
            
            if not line:
                continue
                
            # Convert assignments
            assignment_match = re.match(r"(\w+)\s*=\s*(.*)", line)
            if assignment_match:
                var, value = assignment_match.groups()
                jinja2_code += f"    {{% set {var} = {value} %}}\n"
                continue
                
            # Convert for loops
            for_match = re.match(r"for\s+(.*?)\s+in\s+(.*?):", line)
            if for_match:
                var, iterable = for_match.groups()
                jinja2_code += f"    {{% for {var} in {iterable} %}}\n"
                continue
                
            # Check for end of for loop
            if line.strip() == "return":
                continue
                
            # Convert return statement
            return_match = re.match(r"return\s+(.*)", line)
            if return_match:
                value = return_match.group(1)
                jinja2_code += f"    {{ {value} }}\n"
                continue
                
            # Default case - add as comment
            jinja2_code += f"    {{# {line} #}}\n"
        
        # Close the macro
        jinja2_code += "{% endmacro %}"
        
        return jinja2_code, macro_name
    
    def answer_question_directly(self, scenario, agent_traits=None):
        """Execute the Jinja2 macro with the given scenario and agent traits.
        
        Args:
            scenario: Dictionary or Scenario object containing data
            agent_traits: Optional dictionary of agent traits
            
        Returns:
            Dict containing the macro's output
        """
        # Ensure scenario is a dictionary
        if hasattr(scenario, "__getitem__"):
            scenario_dict = scenario
        else:
            scenario_dict = {}
        
        # Ensure agent_traits is a dictionary
        if agent_traits is None:
            agent_traits_dict = {}
        else:
            agent_traits_dict = agent_traits
        
        try:
            # Prepare the template and render it
            context = {
                'scenario': scenario_dict,
                'agent_traits': agent_traits_dict,
            }
            
            # Create a clean template that trims whitespace
            clean_template = "{% set result = " + self.macro_name + "(scenario, agent_traits) %}{{ result|trim }}"
            
            # Call the specific macro within a controlled context
            env = jinja2.Environment(
                autoescape=True,
                trim_blocks=True,
                lstrip_blocks=True
            )
            
            # First, load the macro definitions
            env.from_string(self.jinja2_template).render(context)
            
            # Now import the macros and call the specific one
            template_with_macros = "{% import _self as macros %}" + self.jinja2_template + clean_template
            template = env.from_string(template_with_macros)
            output = template.render(context)
            
            return {"answer": output, "comment": None}
        except Exception as e:
            raise Exception(f"Error executing Jinja2 function: {str(e)}")
    
    def _translate_answer_code_to_answer(self, answer, scenario):
        """Required by Question, but not used by QuestionJinjaFunction."""
        return None
    
    def _simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Required by Question, but not used by QuestionJinjaFunction."""
        raise NotImplementedError
    
    def _validate_answer(self, answer: dict[str, str]):
        """Required by Question, but not used by QuestionJinjaFunction."""
        raise NotImplementedError
    
    @property
    def question_html_content(self) -> str:
        return "NA for QuestionJinjaFunction"
    
    def to_dict(self, add_edsl_version=True):
        """Serialize the question to a dictionary.
        
        Args:
            add_edsl_version: Whether to include the EDSL version in the output
            
        Returns:
            Dictionary representation of the question
        """
        d = {
            "question_name": self.question_name,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "jinja2_template": self.jinja2_template,
            "macro_name": self.macro_name,
            "answering_instructions": self.instructions,
        }
        
        if self.question_presentation:
            d["question_presentation"] = self.question_presentation
            
        if add_edsl_version:
            from edsl import __version__
            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
        
        return d
    
    @classmethod
    @remove_edsl_version
    def from_dict(cls, d):
        """Create a QuestionJinjaFunction from a dictionary.
        
        Args:
            d: Dictionary representation of the question
            
        Returns:
            New QuestionJinjaFunction instance
        """
        return cls(
            question_name=d["question_name"],
            jinja2_template=d["jinja2_template"],
            macro_name=d["macro_name"],
            question_text=d.get("question_text", "Jinja2 Function"),
            question_presentation=d.get("question_presentation"),
            answering_instructions=d.get("instructions"),
        )
    
    @classmethod
    def example(cls):
        """Create an example QuestionJinjaFunction.
        
        Returns:
            QuestionJinjaFunction instance with a simple sum_and_multiply macro
        """
        template_str = """
        {% macro sum_and_multiply(scenario, agent_traits) %}
            {% set numbers = scenario.get("numbers", []) %}
            {% set multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1 %}
            {% set sum = 0 %}
            {% for num in numbers %}
                {% set sum = sum + num %}
            {% endfor %}
            {{ sum * multiplier }}
        {% endmacro %}
        """
        
        return cls(
            question_name="sum_and_multiply",
            jinja2_template=template_str,
            macro_name="sum_and_multiply",
            question_text="Calculate the sum of the list and multiply it by the agent trait multiplier.",
            question_presentation="This is a functional question that calculates values instead of asking an LLM.",
            answering_instructions="No answering instructions needed for functional questions.",
        )


def calculate_sum_and_multiply(scenario, agent_traits):
    """Example function that sums a list of numbers and multiplies by a factor.
    
    This is used for demonstration and testing of the conversion function.
    
    Args:
        scenario: Dictionary containing a "numbers" list
        agent_traits: Dictionary containing a "multiplier" value
        
    Returns:
        Sum of numbers multiplied by the multiplier
    """
    numbers = scenario.get("numbers", [])
    multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1
    sum = 0
    for num in numbers:
        sum = sum + num
    return sum * multiplier


if __name__ == "__main__":
    # Run doctests
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
    
    # Manual test example
    from edsl import Scenario, Agent
    
    # Create the question using Python function conversion
    question = QuestionJinjaFunction(
        question_name="sum_and_multiply_converted",
        func_for_conversion=calculate_sum_and_multiply
    )
    
    # Test with sample data
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"multiplier": 10})
    
    # Print the generated Jinja2 template
    print("\nGenerated Jinja2 template:")
    print(question.jinja2_template)
    
    # Test execution
    results = question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    print(f"\nResult: {results.select('answer.*').to_list()[0]}")
    
    # Test serialization and deserialization
    question_dict = question.to_dict()
    new_question = QuestionJinjaFunction.from_dict(question_dict)
    results2 = new_question.by(scenario).by(agent).run(disable_remote_cache=True, disable_remote_inference=True)
    print(f"Deserialized result: {results2.select('answer.*').to_list()[0]}")