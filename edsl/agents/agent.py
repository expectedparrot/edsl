"""Agent module for creating and managing AI agents with traits and question-answering capabilities.

This module provides the Agent class, which represents an AI agent with customizable traits,
instructions, and optional direct question-answering methods. Agents are the primary entities
that answer questions in the EDSL framework, and they can be configured with:

- Traits: Key-value pairs representing agent attributes (age, occupation, preferences, etc.)
- Instructions: Directives for how the agent should answer questions
- Codebooks: Human-readable descriptions for traits used in prompts
- Dynamic traits: Functions that can modify traits based on questions
- Direct answering methods: Functions that can answer specific questions without using an LLM

Agents can be combined, modified, and used to answer various question types through different
invigilator mechanisms.

Codebook and Trait Rendering
---------------------------
One of the key features of the Agent class is its ability to use codebooks to improve
how traits are presented to language models. A codebook is a dictionary that maps trait keys 
to human-readable descriptions:

```python
traits = {"age": 30, "occupation": "doctor"}
codebook = {"age": "Age in years", "occupation": "Current profession"}
agent = Agent(traits=traits, codebook=codebook)
```

When an agent with a codebook generates prompts, it will use these descriptions
instead of the raw trait keys, creating more natural and descriptive prompts:

Without codebook: "Your traits: {'age': 30, 'occupation': 'doctor'}"
With codebook: 
```
Your traits:
Age in years: 30
Current profession: doctor
```

This approach helps language models better understand the traits and can lead to
more natural responses that properly interpret the agent's characteristics.
"""

from __future__ import annotations
import copy
import inspect
import types
import warnings
from uuid import uuid4
from contextlib import contextmanager
from typing import (
    Callable,
    Optional,
    Union,
    Any,
    TYPE_CHECKING,
    Protocol,
    runtime_checkable,
    TypeVar,
    Type,
)
from collections.abc import MutableMapping
from collections import UserDict, defaultdict  


if TYPE_CHECKING:
    from ..caching import Cache
    from ..surveys import Survey
    from ..scenarios import Scenario
    from ..language_models import LanguageModel
    from ..surveys.memory import MemoryPlan
    from ..questions import QuestionBase
    from ..invigilators import InvigilatorBase
    from ..prompts import Prompt
    from ..key_management import KeyLookup

from ..base import Base
from ..scenarios import Scenario
from ..questions import QuestionScenarioRenderError
from ..data_transfer_models import AgentResponseDict
from ..utilities import (
    sync_wrapper,
    create_restricted_function,
    dict_hash,
    remove_edsl_version,
)

from .exceptions import (
    AgentErrors,
    AgentCombinationError,
    AgentDirectAnswerFunctionError,
    AgentDynamicTraitsFunctionError,
)

from .descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
    NameDescriptor,
)

# Type variable for the Agent class
A = TypeVar("A", bound="Agent")


@runtime_checkable
class DirectAnswerMethod(Protocol):
    """Protocol defining the required signature for direct answer methods."""

    def __call__(self, self_: A, question: QuestionBase, scenario: Scenario) -> Any: ...


class AgentTraits(MutableMapping):
    """
    A proxy around the real trait dict.
    All writes go through _guard(), which delegates to the parent Agent
    to enforce whatever rules it wants (no dynamic-traits override, etc.).
    """
    def __init__(self, data: dict, parent: "Agent"):
        self._store = Scenario(data)
        self._parent = parent

    # ---- internal helper -------------------------------------------------
    def _guard(self):
        self._parent._check_before_modifying_traits()        # raise if not allowed

    # ---- MutableMapping interface ----------------------------------------
    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._guard()
        self._store[key] = value

    def __delitem__(self, key):
        self._guard()
        del self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    # nice repr for debugging
    def __repr__(self):
        return dict(self._store).__repr__()

    # allow dict | union syntax to work like normal dicts
    def __or__(self, other):
        """Return a regular dictionary that is the union of this mapping and *other*.

        Mirrors the behaviour of ``dict.__or__`` introduced in Python 3.9 so that
        ``AgentTraits | AgentTraits`` (or ``|`` with any mapping) behaves the
        same as with plain ``dict`` objects.  The result is a **new** *dict*
        (not an ``AgentTraits`` instance) which matches the semantics of the
        built-in type.
        """
        if isinstance(other, MutableMapping):
            return {**dict(self), **dict(other)}
        return NotImplemented

    # support reversed operand order (e.g. ``dict | AgentTraits``)
    def __ror__(self, other):
        if isinstance(other, MutableMapping):
            return {**dict(other), **dict(self)}
        return NotImplemented

    # in-place union ``|=`` – delegates to __setitem__ so guards still fire
    def __ior__(self, other):
        if isinstance(other, MutableMapping):
            for k, v in other.items():
                self[k] = v  # will trigger _guard()
            return self
        return NotImplemented
        


class Agent(Base):
    """A class representing an AI agent with customizable traits that can answer questions.
    
    An Agent in EDSL represents an entity with specific characteristics (traits) that can
    answer questions through various mechanisms. Agents can use language models to generate
    responses based on their traits, directly answer questions through custom functions, or
    dynamically adjust their traits based on the questions being asked.
    
    Key capabilities:
    - Store and manage agent characteristics (traits)
    - Provide instructions on how the agent should answer
    - Support for custom codebooks to provide human-readable trait descriptions
    - Integration with multiple question types and language models
    - Combine agents to create more complex personas
    - Customize agent behavior through direct answering methods
    
    Agents are used in conjunction with Questions, Scenarios, and Surveys to create
    structured interactions with language models.
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/agents.html"

    default_instruction = """You are answering questions as if you were a human. Do not break character."""

    # Trait storage using descriptors for validation and management
    _traits = TraitsDescriptor()
    
    # Codebook maps trait keys to human-readable descriptions
    # This improves prompt readability and LLM understanding
    # Example: {'age': 'Age in years'} → "Age in years: 30" instead of "age: 30"
    codebook = CodebookDescriptor()
    
    # Instructions for how the agent should answer questions
    instruction = InstructionDescriptor()
    
    # Optional name identifier for the agent
    name = NameDescriptor()
    
    # Default values for function-related attributes
    dynamic_traits_function_name = ""
    answer_question_directly_function_name = ""
    has_dynamic_traits_function = False

    def __init__(
        self,
        traits: Optional[dict] = None,
        name: Optional[str] = None,
        codebook: Optional[dict] = None,
        instruction: Optional[str] = None,
        trait_categories: Optional[OrganizedTraits] = None,
        traits_presentation_template: Optional[str] = None,
        dynamic_traits_function: Optional[Callable] = None,
        dynamic_traits_function_source_code: Optional[str] = None,
        dynamic_traits_function_name: Optional[str] = None,
        answer_question_directly_source_code: Optional[str] = None,
        answer_question_directly_function_name: Optional[str] = None,
    ):
        """Initialize a new Agent instance with specified traits and capabilities.

        Args:
            traits: Dictionary of agent characteristics (e.g., {"age": 30, "occupation": "doctor"})
            name: Optional name identifier for the agent
            codebook: Dictionary mapping trait keys to human-readable descriptions for prompts.
                This provides more descriptive labels for traits when rendering prompts.
                For example, {'age': 'Age in years'} would display "Age in years: 30" instead of "age: 30".
            instruction: Directive for how the agent should answer questions
            traits_presentation_template: Jinja2 template for formatting traits in prompts
            dynamic_traits_function: Function that can modify traits based on questions
            dynamic_traits_function_source_code: Source code string for the dynamic traits function
            dynamic_traits_function_name: Name of the dynamic traits function
            answer_question_directly_source_code: Source code for direct question answering method
            answer_question_directly_function_name: Name of the direct answering function
            
        The Agent class brings together several key concepts:
        
        Traits
        ------
        Traits are key-value pairs that define an agent's characteristics. These are used
        to construct a prompt that guides the language model on how to respond.
        
        Example:
        >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}
        
        Traits Presentation
        ------------------
        The traits_presentation_template controls how traits are formatted in prompts.
        It uses Jinja2 templating to insert trait values.
        
        Example:
        >>> a = Agent(traits={"age": 10}, traits_presentation_template="I am a {{age}} year old.")
        >>> repr(a.agent_persona)
        'Prompt(text=\"""I am a {{age}} year old.\""")'
        
        Codebooks
        ---------
        Codebooks provide human-readable descriptions for traits in prompts.
        
        Example:
        >>> traits = {"age": 10, "hair": "brown", "height": 5.5}
        >>> codebook = {'age': 'Their age is'}
        >>> a = Agent(traits=traits, codebook=codebook, 
        ...           traits_presentation_template="This agent is Dave. {{codebook['age']}} {{age}}")
        >>> d = a.traits | {'codebook': a.codebook}
        >>> a.agent_persona.render(d)
        Prompt(text=\"""This agent is Dave. Their age is 10\""")
        
        Instructions
        ------------
        Instructions guide how the agent should answer questions. If not provided,
        a default instruction is used.
        
        >>> Agent.default_instruction
        'You are answering questions as if you were a human. Do not break character.'
        
        For details on how these components are used to construct prompts, see
        :py:class:`edsl.agents.Invigilator.InvigilatorBase`.
        """
        self._initialize_basic_attributes(traits, name, codebook)
        self._initialize_instruction(instruction)
        self._initialize_dynamic_traits_function(
            dynamic_traits_function,
            dynamic_traits_function_source_code,
            dynamic_traits_function_name,
        )
        self._initialize_answer_question_directly(
            answer_question_directly_source_code, answer_question_directly_function_name
        )
        self._check_dynamic_traits_function()
        self._initialize_traits_presentation_template(traits_presentation_template)
        self.current_question = None
        self.trait_categories = trait_categories or {}

    def with_categories(self, *categories: str) -> Agent:
        """Return a new agent with the specified categories"""
        new_agent = self.duplicate()
        new_traits = {}
        for category in categories:
            if category not in self.trait_categories:
                raise AgentErrors(f"Category {category} not found in agent categories")
            for trait_key in self.trait_categories[category]:
                new_traits[trait_key] = self.traits[trait_key]
        new_agent.traits = new_traits
        return new_agent
    
    def add_category(self, category_name: str, trait_keys: Optional[list[str]] = None) -> None:
        """Add a category to the agent"""
        if category_name not in self.trait_categories:
            self.trait_categories[category_name] = []
        if trait_keys:
            for trait_key in trait_keys:
                if trait_key not in self.traits:
                    raise AgentErrors(f"Trait {trait_key} not found in agent traits")
                self.trait_categories[category_name].append(trait_key)

    def _initialize_basic_attributes(self, traits, name, codebook) -> None:
        """Initialize the basic attributes of the agent.
        
        Args:
            traits: Dictionary of agent characteristics
            name: Name identifier for the agent
            codebook: Dictionary mapping trait keys to descriptions
        """
        self.name = name
        self._traits = AgentTraits(traits or {}, parent=self)
        self.codebook = codebook or dict()

    def _initialize_instruction(self, instruction) -> None:
        """Initialize the instruction for how the agent should answer questions.
        
        If no instruction is provided, uses the default instruction.
        
        Args:
            instruction: Directive for how the agent should answer questions
        """
        if instruction is None:
            self.instruction = self.default_instruction
            self._instruction = self.default_instruction
            self.set_instructions = False
        else:
            self.instruction = instruction
            self._instruction = instruction
            self.set_instructions = True

    def _initialize_traits_presentation_template(
        self, traits_presentation_template
    ) -> None:
        """Initialize the template for presenting agent traits in prompts.
        
        This method sets up how the agent's traits will be formatted in language model prompts.
        The template is a Jinja2 template string that can reference trait values and other
        agent properties.
        
        If no template is provided:
        - If a codebook exists, the method creates a template that displays each trait with its 
          codebook description instead of the raw key names (e.g., "Age in years: 30" instead of "age: 30")
        - Without a codebook, it uses a default template that displays all traits as a dictionary
        
        Custom templates always take precedence over automatically generated ones, giving users
        complete control over how traits are presented.
        
        Args:
            traits_presentation_template: Optional Jinja2 template string for formatting traits.
                If not provided, a default template will be generated.
                
        Examples:
            With no template or codebook, traits are shown as a dictionary:
            
            >>> agent = Agent(traits={"age": 25, "occupation": "engineer"})
            >>> str(agent.prompt().text)
            'Your traits: {\'age\': 25, \'occupation\': \'engineer\'}'
            
            With a codebook but no custom template, traits are shown with descriptions:
            
            >>> codebook = {"age": "Age in years", "occupation": "Current profession"}
            >>> agent = Agent(traits={"age": 25, "occupation": "engineer"}, codebook=codebook)
            >>> print(agent.prompt().text)  # doctest: +NORMALIZE_WHITESPACE
            Your traits:
            Age in years: 25
            Current profession: engineer
            
            With a custom template, that format is used regardless of codebook:
            
            >>> template = "Person: {{age}} years old, works as {{occupation}}"
            >>> agent = Agent(traits={"age": 25, "occupation": "engineer"}, 
            ...               codebook=codebook, traits_presentation_template=template)
            >>> str(agent.prompt().text)
            'Person: 25 years old, works as engineer'
        """
        if traits_presentation_template is not None:
            self._traits_presentation_template = traits_presentation_template
            self.traits_presentation_template = traits_presentation_template
            self.set_traits_presentation_template = True
        else:
            # Set the default template based on whether a codebook exists
            if self.codebook:
                # Create a template that uses the codebook descriptions
                traits_lines = []
                for trait_key in self.traits.keys():
                    if trait_key in self.codebook:
                        # Use codebook description if available
                        traits_lines.append(f"{self.codebook[trait_key]}: {{{{ {trait_key} }}}}")
                    else:
                        # Fall back to raw key for traits without codebook entries
                        traits_lines.append(f"{trait_key}: {{{{ {trait_key} }}}}")
                
                # Join all trait lines with newlines
                self.traits_presentation_template = "Your traits:\n" + "\n".join(traits_lines)
            else:
                # Use the standard dictionary format if no codebook
                self.traits_presentation_template = "Your traits: {{traits}}"
                
            self.set_traits_presentation_template = False

    def _initialize_dynamic_traits_function(
        self,
        dynamic_traits_function,
        dynamic_traits_function_source_code,
        dynamic_traits_function_name,
    ) -> None:
        """Initialize a function that can dynamically modify agent traits based on questions.
        
        This allows traits to change based on the question being asked, enabling
        more sophisticated agent behaviors. The function can be provided directly
        or as source code that will be compiled.
        
        Args:
            dynamic_traits_function: Function object that returns a dictionary of traits
            dynamic_traits_function_source_code: Source code string for the function
            dynamic_traits_function_name: Name to assign to the function
        """
        # Deal with dynamic traits function
        self.dynamic_traits_function = dynamic_traits_function

        if self.dynamic_traits_function:
            self.dynamic_traits_function_name = self.dynamic_traits_function.__name__
            self.has_dynamic_traits_function = True
        else:
            self.has_dynamic_traits_function = False

        if dynamic_traits_function_source_code:
            self.dynamic_traits_function_name = dynamic_traits_function_name
            self.dynamic_traits_function = create_restricted_function(
                dynamic_traits_function_name, dynamic_traits_function
            )

    def _initialize_answer_question_directly(
        self,
        answer_question_directly_source_code,
        answer_question_directly_function_name,
    ) -> None:
        """Initialize a method for the agent to directly answer questions without using an LLM.
        
        This allows creating agents that answer programmatically rather than through
        language model generation. The direct answering method can be provided as
        source code that will be compiled and bound to this agent instance.
        
        Args:
            answer_question_directly_source_code: Source code for the direct answering method
            answer_question_directly_function_name: Name to assign to the method
        """
        if answer_question_directly_source_code:
            self.answer_question_directly_function_name = (
                answer_question_directly_function_name
            )
            protected_method = create_restricted_function(
                answer_question_directly_function_name,
                answer_question_directly_source_code,
            )
            bound_method = types.MethodType(protected_method, self)
            setattr(self, "answer_question_directly", bound_method)

    def _initialize_traits_presentation_template(
        self, traits_presentation_template
    ) -> None:
        if traits_presentation_template is not None:
            self._traits_presentation_template = traits_presentation_template
            self.traits_presentation_template = traits_presentation_template
            self.set_traits_presentation_template = True
        else:
            self.traits_presentation_template = "Your traits: {{traits}}"
            self.set_traits_presentation_template = False


    def drop(self, field_name: str) -> Agent:
        """Drop a field from the agent.
        
        Args:
            field_name: The name of the field to drop.
        """
        d = self.to_dict()
        if field_name in d['traits']:
            d['traits'].pop(field_name)
        elif field_name in d:
            d.pop(field_name)
        else:
            raise AgentErrors((f"Field '{field_name}' not found in agent"
                               f"Available fields: {d.keys()}"
                               f"Available traits: {d['traits'].keys()}"
                              ))
        return Agent.from_dict(d)

    def duplicate(self) -> Agent:
        """Create a deep copy of this agent with all its traits and capabilities.
        
        This method creates a completely independent copy of the agent, including
        all its traits, codebook, instructions, and special functions like dynamic
        traits and direct answering methods.
        
        Returns:
            Agent: A new agent instance that is functionally identical to this one
            
        Examples:
            Create a duplicate agent and verify it's equal but not the same object:
            
            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5}, 
            ...           codebook={'age': 'Their age is'})
            >>> a2 = a.duplicate()
            >>> a2 == a  # Functionally equivalent
            True
            >>> id(a) == id(a2)  # But different objects
            False
            
            Duplicating preserves direct answering methods:
            
            >>> def f(self, question, scenario): return "I am a direct answer."
            >>> a.add_direct_question_answering_method(f)
            >>> hasattr(a, "answer_question_directly")
            True
            >>> a2 = a.duplicate()
            >>> a2.answer_question_directly(None, None)
            'I am a direct answer.'
            
            Duplicating preserves custom instructions:
            
            >>> a = Agent(traits={'age': 10}, instruction="Have fun!")
            >>> a2 = a.duplicate()
            >>> a2.instruction
            'Have fun!'
        """
        new_agent = Agent.from_dict(self.to_dict())
        
        # Transfer direct answering method if present
        if hasattr(self, "answer_question_directly"):
            answer_question_directly = self.answer_question_directly
            def newf(self, question, scenario):
                return answer_question_directly(
                    question, scenario
                )
            new_agent.add_direct_question_answering_method(newf)
            
        # Transfer dynamic traits function if present
        if hasattr(self, "dynamic_traits_function"):
            dynamic_traits_function = self.dynamic_traits_function
            new_agent.dynamic_traits_function = dynamic_traits_function
            
        return new_agent
        
    def copy(self) -> Agent:
        """Create a deep copy of this agent using serialization/deserialization.
        
        This method uses to_dict/from_dict to create a completely independent copy
        of the agent, including all its traits, codebook, instructions, and special
        functions like dynamic traits and direct answering methods.
        
        Returns:
            Agent: A new agent instance that is functionally identical to this one
            
        Examples:
            >>> a = Agent(traits={"age": 10, "hair": "brown"}, 
            ...           codebook={'age': 'Their age is'})
            >>> a2 = a.copy()
            >>> a2 == a  # Functionally equivalent
            True
            >>> id(a) == id(a2)  # But different objects
            False
            
            Copy preserves direct answering methods:
            
            >>> def f(self, question, scenario): return "I am a direct answer."
            >>> a.add_direct_question_answering_method(f)
            >>> a2 = a.copy()
            >>> a2.answer_question_directly(None, None)
            'I am a direct answer.'
        """
        return self.duplicate()

    @property
    def agent_persona(self) -> Prompt:
        """Get the agent's persona template as a Prompt object.
        
        This property provides access to the template that formats the agent's traits
        for presentation in prompts. The template is wrapped in a Prompt object
        that supports rendering with variable substitution.
        
        Returns:
            Prompt: A prompt object containing the traits presentation template
        """
        from ..prompts import Prompt

        return Prompt(text=self.traits_presentation_template)

    def prompt(self) -> str:
        """Generate a formatted prompt containing the agent's traits.
        
        This method renders the agent's traits presentation template with the
        agent's traits and codebook, creating a formatted prompt that can be
        used in language model requests.
        
        The method is dynamic and responsive to changes in the agent's state:
        
        1. If a custom template was explicitly set during initialization, it will be used
        2. If using the default template and the codebook has been updated since
           initialization, this method will recreate the template to reflect the current
           codebook values
        3. The template is rendered with access to all trait values, the complete traits
           dictionary, and the codebook
           
        The template rendering makes the following variables available:
        - All individual trait keys (e.g., {{age}}, {{occupation}})
        - The full traits dictionary as {{traits}}
        - The codebook as {{codebook}}
        
        Returns:
            Prompt: A Prompt object containing the rendered template
            
        Raises:
            QuestionScenarioRenderError: If any template variables remain undefined
            
        Examples:
            Basic trait rendering without a codebook:
            
            >>> agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> agent.prompt()
            Prompt(text=\"""Your traits: {'age': 10, 'hair': 'brown', 'height': 5.5}\""")
            
            Trait rendering with a codebook (more readable format):
            
            >>> codebook = {"age": "Age in years", "hair": "Hair color"}
            >>> agent = Agent(traits={"age": 10, "hair": "brown"}, codebook=codebook)
            >>> print(agent.prompt().text)  # doctest: +NORMALIZE_WHITESPACE
            Your traits:
            Age in years: 10
            Hair color: brown
            
            Adding a codebook after initialization updates the rendering:
            
            >>> agent = Agent(traits={"age": 30, "occupation": "doctor"})
            >>> initial_prompt = agent.prompt()
            >>> "Your traits: {" in initial_prompt.text
            True
            >>> agent.codebook = {"age": "Age", "occupation": "Profession"}
            >>> updated_prompt = agent.prompt()
            >>> "Age: 30" in updated_prompt.text
            True
            >>> "Profession: doctor" in updated_prompt.text
            True
            
            Custom templates can reference any trait directly:
            
            >>> template = "Profile: {{age}} year old {{occupation}}"
            >>> agent = Agent(traits={"age": 45, "occupation": "teacher"}, 
            ...               traits_presentation_template=template)
            >>> agent.prompt().text
            'Profile: 45 year old teacher'
        """
        # If using the default template and the codebook has been updated since initialization,
        # recreate the template to use the current codebook
        if not self.set_traits_presentation_template and self.codebook:
            # Create a template that uses the codebook descriptions
            traits_lines = []
            for trait_key in self.traits.keys():
                if trait_key in self.codebook:
                    # Use codebook description if available
                    traits_lines.append(f"{self.codebook[trait_key]}: {{{{ {trait_key} }}}}")
                else:
                    # Fall back to raw key for traits without codebook entries
                    traits_lines.append(f"{trait_key}: {{{{ {trait_key} }}}}")
            
            # Join all trait lines with newlines
            self.traits_presentation_template = "Your traits:\n" + "\n".join(traits_lines)
            
        # Create a dictionary with traits, a reference to all traits, and the codebook
        replacement_dict = (
            self.traits | {"traits": self.traits} | {"codebook": self.codebook}
        )
        
        # Check for any undefined variables in the template
        if undefined := self.agent_persona.undefined_template_variables(
            replacement_dict
        ):
            raise QuestionScenarioRenderError(
                f"Agent persona still has variables that were not rendered: {undefined}"
            )
        else:
            return self.agent_persona.render(replacement_dict)

    def _check_dynamic_traits_function(self) -> None:
        """Validate that the dynamic traits function has the correct signature.
        
        This method checks if the dynamic traits function (if present) has the correct
        parameter list. The function should either take no parameters or a single
        parameter named 'question'.
        
        Raises:
            AgentDynamicTraitsFunctionError: If the function signature is invalid
            
        Examples:
            Valid function with 'question' parameter:
            
            >>> def f(question): return {"age": 10, "hair": "brown", "height": 5.5}
            >>> a = Agent(dynamic_traits_function=f)
            >>> a._check_dynamic_traits_function()
            
            Invalid function with extra parameters:
            
            >>> def g(question, poo): return {"age": 10, "hair": "brown", "height": 5.5}
            >>> a = Agent(dynamic_traits_function=g)
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentDynamicTraitsFunctionError: ...
        """
        if self.has_dynamic_traits_function:
            sig = inspect.signature(self.dynamic_traits_function)
            
            if "question" in sig.parameters:
                # If it has 'question' parameter, it should be the only one
                if len(sig.parameters) > 1:
                    raise AgentDynamicTraitsFunctionError(
                        message=f"The dynamic traits function {self.dynamic_traits_function} has too many parameters. It should only have one parameter: 'question'."
                    )
            else:
                # If it doesn't have 'question', it shouldn't have any parameters
                if len(sig.parameters) > 0:
                    raise AgentDynamicTraitsFunctionError(
                        f"""The dynamic traits function {self.dynamic_traits_function} has too many parameters. It should have no parameters or 
                        just a single parameter: 'question'."""
                    )

    @property
    def traits(self) -> dict[str, str]:
        """Get the agent's traits, potentially using dynamic generation.
        
        This property provides access to the agent's traits, either from the stored
        traits dictionary or by calling a dynamic traits function if one is defined.
        If a dynamic traits function is used, it may take the current question as a
        parameter to generate context-aware traits.
        
        Returns:
            dict: Dictionary of agent traits (key-value pairs)
            
        Examples:
            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> a.traits
            {'age': 10, 'hair': 'brown', 'height': 5.5}
        """
        if self.has_dynamic_traits_function:
            # Check if the function expects a question parameter
            sig = inspect.signature(self.dynamic_traits_function)
            
            if "question" in sig.parameters:
                # Call with the current question
                return self.dynamic_traits_function(question=self.current_question)
            else:
                # Call without parameters
                return self.dynamic_traits_function()
        else:
            # Return the stored traits
            return self._traits

    @contextmanager
    def modify_traits_context(self):
        self._check_before_modifying_traits()
        try:
            yield
        finally:
            # re-wrap the possibly mutated mapping so future writes remain guarded
            self._traits = AgentTraits(dict(self._traits), parent=self)

    def _check_before_modifying_traits(self):
        """Check before modifying traits."""
        if self.has_dynamic_traits_function:
            raise AgentErrors(
                "You cannot modify the traits of an agent that has a dynamic traits function.",
                "If you want to modify the traits, you should remove the dynamic traits function.",
            )

    @traits.setter
    def traits(self, traits: dict[str, str]):
        with self.modify_traits_context():
            # store raw dict temporarily – it will be wrapped by the context manager
            self._traits = traits

    def rename(
        self,
        old_name_or_dict: Union[str, dict[str, str]],
        new_name: Optional[str] = None,
    ) -> Agent:
        """Rename a trait.

        :param old_name_or_dict: The old name of the trait or a dictionary of old names and new names.
        :param new_name: The new name of the trait.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> newa = a.rename("age", "years")
        >>> newa == Agent(traits = {'years': 10, 'hair': 'brown', 'height': 5.5})
        True

        >>> newa.rename({'years': 'smage'}) == Agent(traits = {'smage': 10, 'hair': 'brown', 'height': 5.5})
        True

        """
        self._check_before_modifying_traits()
        if isinstance(old_name_or_dict, dict) and new_name:
            raise AgentErrors(
                f"You passed a dict: {old_name_or_dict} and a new name: {new_name}. You should pass only a dict."
            )

        if isinstance(old_name_or_dict, dict) and new_name is None:
            return self._rename_dict(old_name_or_dict)

        if isinstance(old_name_or_dict, str):
            return self._rename(old_name_or_dict, new_name)

        raise AgentErrors("Something is not right with Agent renaming")

    def _rename_dict(self, renaming_dict: dict[str, str]) -> Agent:
        """
        Internal method to rename traits using a dictionary.
        The keys should all be old names and the values should all be new names.

        Example usage:
        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a._rename_dict({"age": "years", "height": "feet"})
        Agent(traits = {'years': 10, 'hair': 'brown', 'feet': 5.5})

        """
        try:
            assert all(k in self.traits for k in renaming_dict.keys())
        except AssertionError:
            raise AgentErrors(
                f"The trait(s) {set(renaming_dict.keys()) - set(self.traits.keys())} do not exist in the agent's traits, which are {self.traits}."
            )
        new_agent = self.duplicate()
        new_agent.traits = {renaming_dict.get(k, k): v for k, v in self.traits.items()}
        return new_agent

    def _rename(self, old_name: str, new_name: str) -> Agent:
        """Rename a trait.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a._rename(old_name="age", new_name="years")
        Agent(traits = {'years': 10, 'hair': 'brown', 'height': 5.5})

        """
        try:
            assert old_name in self.traits
        except AssertionError:
            raise AgentErrors(
                f"The trait '{old_name}' does not exist in the agent's traits, which are {self.traits}."
            )
        newagent = self.duplicate()
        newagent.traits = {
            new_name if k == old_name else k: v for k, v in self.traits.items()
        }
        newagent.codebook = {
            new_name if k == old_name else k: v for k, v in self.codebook.items()
        }
        return newagent

    def __getitem__(self, key):
        """Allow for accessing traits using the bracket notation.

        Example:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a['traits']['age']
        10

        """
        return getattr(self, key)

    def remove_direct_question_answering_method(self) -> None:
        """Remove the direct question answering method.

        Example usage:

        >>> a = Agent()
        >>> def f(self, question, scenario): return "I am a direct answer."
        >>> a.add_direct_question_answering_method(f)
        >>> a.remove_direct_question_answering_method()
        >>> hasattr(a, "answer_question_directly")
        False
        """
        if hasattr(self, "answer_question_directly"):
            delattr(self, "answer_question_directly")

    def add_direct_question_answering_method(
        self,
        method: DirectAnswerMethod,
        validate_response: bool = False,
        translate_response: bool = False,
    ) -> None:
        """Add a method to the agent that can answer a particular question type.
        https://docs.expectedparrot.com/en/latest/agents.html#agent-direct-answering-methods

        :param method: A method that can answer a question directly.
        :param validate_response: Whether to validate the response.
        :param translate_response: Whether to translate the response.

        Example usage:

        >>> a = Agent()
        >>> def f(self, question, scenario): return "I am a direct answer."
        >>> a.add_direct_question_answering_method(f)
        >>> a.answer_question_directly(question = None, scenario = None)
        'I am a direct answer.'
        """
        if hasattr(self, "answer_question_directly"):

            warnings.warn(
                "Warning: overwriting existing answer_question_directly method"
            )

        self.validate_response = validate_response
        self.translate_response = translate_response

        signature = inspect.signature(method)
        for argument in ["question", "scenario", "self"]:
            if argument not in signature.parameters:
                raise AgentDirectAnswerFunctionError(
                    f"The method {method} does not have a '{argument}' parameter."
                )
        bound_method = types.MethodType(method, self)
        setattr(self, "answer_question_directly", bound_method)
        self.answer_question_directly_function_name = bound_method.__name__

    def create_invigilator(
        self,
        *,
        question: "QuestionBase",
        cache: "Cache",
        survey: Optional["Survey"] = None,
        scenario: Optional["Scenario"] = None,
        model: Optional["LanguageModel"] = None,
        memory_plan: Optional["MemoryPlan"] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 1,
        raise_validation_errors: bool = True,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> "InvigilatorBase":
        """Create an Invigilator.

        An invigilator is an object that is responsible for administering a question to an agent.
        There are several different types of invigilators, depending on the type of question and the agent.
        For example, there are invigilators for functional questions (i.e., question is of type :class:`edsl.questions.QuestionFunctional`:), for direct questions, and for LLM questions.

        >>> a = Agent(traits = {})
        >>> a.create_invigilator(question = None, cache = False)
        InvigilatorAI(...)

        An invigator is an object that is responsible for administering a question to an agent and
        recording the responses.
        """
        from ..language_models import Model
        from ..scenarios import Scenario

        cache = cache
        self.current_question = question
        model = model or Model()
        scenario = scenario or Scenario()
        invigilator = self._create_invigilator(
            question=question,
            scenario=scenario,
            survey=survey,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            cache=cache,
            raise_validation_errors=raise_validation_errors,
            key_lookup=key_lookup,
        )
        if hasattr(self, "validate_response"):
            invigilator.validate_response = self.validate_response
        if hasattr(self, "translate_response"):
            invigilator.translate_response = self.translate_response
        return invigilator

    async def async_answer_question(
        self,
        *,
        question: QuestionBase,
        cache: Cache,
        scenario: Optional[Scenario] = None,
        survey: Optional[Survey] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> AgentResponseDict:
        """
        Answer a posed question.

        :param question: The question to answer.
        :param scenario: The scenario in which the question is asked.
        :param model: The language model to use.
        :param debug: Whether to run in debug mode.
        :param memory_plan: The memory plan to use.
        :param current_answers: The current answers.
        :param iteration: The iteration number.

        >>> a = Agent(traits = {})
        >>> a.add_direct_question_answering_method(lambda self, question, scenario: "I am a direct answer.")
        >>> from edsl.questions import QuestionFreeText
        >>> q = QuestionFreeText.example()
        >>> a.answer_question(question = q, cache = False).answer
        'I am a direct answer.'

        This is a function where an agent returns an answer to a particular question.
        However, there are several different ways an agent can answer a question, so the
        actual functionality is delegated to an :class:`edsl.agents.InvigilatorBase`: object.
        """
        invigilator = self.create_invigilator(
            question=question,
            cache=cache,
            scenario=scenario,
            survey=survey,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            key_lookup=key_lookup,
        )
        response: AgentResponseDict = await invigilator.async_answer_question()
        return response

    answer_question = sync_wrapper(async_answer_question)

    def _get_invigilator_class(self, question: "QuestionBase") -> Type["InvigilatorBase"]:
        """Get the invigilator class for a question.

        This method returns the invigilator class that should be used to answer a question.
        The invigilator class is determined by the type of question and the type of agent.
        """
        from ..invigilators import (
            InvigilatorHuman,
            InvigilatorFunctional,
            InvigilatorAI,
        )

        if hasattr(question, "answer_question_directly"):
            return InvigilatorFunctional
        elif hasattr(self, "answer_question_directly"):
            return InvigilatorHuman
        else:
            return InvigilatorAI

    def _create_invigilator(
        self,
        question: QuestionBase,
        cache: Optional[Cache] = None,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        survey: Optional[Survey] = None,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        raise_validation_errors: bool = True,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> "InvigilatorBase":
        """Create an Invigilator."""
        from ..language_models import Model
        from ..scenarios import Scenario

        model = model or Model()
        scenario = scenario or Scenario()

        if cache is None:
            from ..caching import Cache

            cache = Cache()

        invigilator_class = self._get_invigilator_class(question)

        invigilator = invigilator_class(
            self,
            question=question,
            scenario=scenario,
            survey=survey,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            cache=cache,
            raise_validation_errors=raise_validation_errors,
            key_lookup=key_lookup,
        )
        return invigilator

    def select(self, *traits: str) -> Agent:
        """Selects agents with only the references traits

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5}, codebook = {'age': 'Their age is'})
        >>> a
        Agent(traits = {'age': 10, 'hair': 'brown', 'height': 5.5}, codebook = {'age': 'Their age is'})


        >>> a.select("age", "height")
        Agent(traits = {'age': 10, 'height': 5.5}, codebook = {'age': 'Their age is'})

        >>> a.select("height")
        Agent(traits = {'height': 5.5})

        """

        if len(traits) == 1:
            traits_to_select = [list(traits)[0]]
        else:
            traits_to_select = list(traits)

        def _remove_none(d):
            return {k: v for k, v in d.items() if v is not None}

        newagent = self.duplicate()
        newagent.traits = {
            trait: self.traits.get(trait, None) for trait in traits_to_select
        }
        newagent.codebook = _remove_none(
            {trait: self.codebook.get(trait, None) for trait in traits_to_select}
        )
        return newagent

    def add(
        self: A,
        other_agent: Optional[A] = None,
        *,
        conflict_strategy: str = "numeric",
    ) -> A:
        """Combine *self* with *other_agent* and return a new Agent.

        Parameters
        ----------
        other_agent
            The second agent to merge with *self*.  If *None*, *self* is
            returned unchanged.
        conflict_strategy
            How to handle overlapping trait names.

            • ``"numeric"`` (default) – rename conflicting traits coming from
              *other_agent* by appending an incrementing suffix (``_1``,
              ``_2`` …).  This is identical to the behaviour of the ``+``
              operator before this refactor.
            • ``"error"`` – raise :class:`edsl.agents.exceptions.AgentCombinationError`.
            • ``"repeated_observation"`` – if both agents have the same
              trait *and* the codebook entry for that trait is identical (or
              missing in both), merge the two values into a list ``[old,
              new]``.  If the codebook entries differ, an
              :class:`edsl.agents.exceptions.AgentCombinationError` is raised.

        Returns
        -------
        Agent
            A new agent containing the merged traits / codebooks.
        """

        if other_agent is None:
            return self

        if conflict_strategy not in {"numeric", "error", "repeated_observation"}:
            raise ValueError(
                "conflict_strategy must be 'numeric', 'error', or 'repeated_observation', got "
                f"{conflict_strategy!r}"
            )

        # Quick path: raise if user asked for error strategy and there is a clash
        if conflict_strategy == "error":
            common = set(self.traits) & set(other_agent.traits)
            if common:
                raise AgentCombinationError(
                    f"The agents have overlapping traits: {common}."
                )

        # Otherwise proceed with numeric-suffix merging (behaviour identical
        # to the former __add__).
        newagent = self.duplicate()

        combined_traits: dict = dict(self.traits)
        combined_codebook: dict = copy.deepcopy(self.codebook)

        def _unique_name(base_name: str, existing_keys: set[str]) -> str:
            """Return *base_name* or *base_name_N* to avoid duplicates."""
            if base_name not in existing_keys:
                return base_name

            idx = 1
            while f"{base_name}_{idx}" in existing_keys:
                idx += 1
            return f"{base_name}_{idx}"

        rename_map: dict[str, str] = {}

        for key, value in other_agent.traits.items():
            if key not in combined_traits:
                # no conflict
                combined_traits[key] = value
                rename_map[key] = key
                continue

            # conflict handling
            if conflict_strategy == "numeric":
                unique_key = _unique_name(key, combined_traits.keys())
                combined_traits[unique_key] = value
                rename_map[key] = unique_key
            elif conflict_strategy == "repeated_observation":
                # validate codebook equality
                desc_self = self.codebook.get(key)
                desc_other = other_agent.codebook.get(key)
                if desc_self != desc_other:
                    raise AgentCombinationError(
                        "Trait conflict on '{key}' with differing codebook descriptions.".format(key=key)
                    )
                # merge values into list
                existing_val = combined_traits[key]
                if isinstance(existing_val, list):
                    merged_val = existing_val + [value]
                else:
                    merged_val = [existing_val, value]
                combined_traits[key] = merged_val
                rename_map[key] = key  # name unchanged
            else:  # conflict_strategy == 'error' (should not be reached)
                pass

        for key, description in other_agent.codebook.items():
            if key in rename_map:
                target_key = rename_map[key]
            elif conflict_strategy == "numeric":
                target_key = _unique_name(key, combined_codebook.keys())
            else:
                target_key = key
            combined_codebook[target_key] = description

        newagent.traits = combined_traits
        newagent.codebook = combined_codebook

        return newagent

    def __add__(self, other_agent: Optional[Agent] = None) -> Agent:
        """Syntactic sugar – delegates to :pymeth:`add`."""
        return self.add(other_agent)

    def __eq__(self, other: Agent) -> bool:
        """Check if two agents are equal.

        This only checks the traits.
        >>> a1 = Agent(traits = {"age": 10})
        >>> a2 = Agent(traits = {"age": 10})
        >>> a1 == a2
        True
        >>> a3 = Agent(traits = {"age": 11})
        >>> a1 == a3
        False
        """
        return self.data == other.data

    def __getattr__(self, name):
        """
        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.age
        10
        """
        if name == "has_dynamic_traits_function":
            return self.has_dynamic_traits_function

        if name in self._traits:
            return self._traits[name]

        # Keep using AttributeError instead of our custom exception to maintain compatibility
        # with Python's attribute access mechanism
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __getstate__(self):
        state = self.__dict__.copy()
        # Include any additional state that needs to be serialized
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Ensure _traits is initialized if it's missing
        if "_traits" not in self.__dict__:
            self._traits = {}

    def __repr__(self) -> str:
        """Return representation of Agent."""
        class_name = self.__class__.__name__
        items = [
            f'{k} = """{v}"""' if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        return f"{class_name}({', '.join(items)})"

    @property
    def data(self) -> dict:
        """Format the data for serialization.

        TODO: Warn if has dynamic traits function or direct answer function that cannot be serialized.
        TODO: Add ability to have coop-hosted functions that are serializable.
        """

        raw_data = {
            k.replace("_", "", 1): v
            for k, v in self.__dict__.items()
            if k.startswith("_")
        }

        if hasattr(self, "set_instructions"):
            if not self.set_instructions:
                raw_data.pop("instruction")
        if self.codebook == {}:
            raw_data.pop("codebook")
        if self.name is None:
            raw_data.pop("name")

        if hasattr(self, "dynamic_traits_function"):
            raw_data.pop(
                "dynamic_traits_function", None
            )  # in case dynamic_traits_function will appear with _ in self.__dict__
            dynamic_traits_func = self.dynamic_traits_function
            if dynamic_traits_func:
                func = inspect.getsource(dynamic_traits_func)
                raw_data["dynamic_traits_function_source_code"] = func
                raw_data["dynamic_traits_function_name"] = (
                    self.dynamic_traits_function_name
                )
        if hasattr(self, "answer_question_directly"):
            raw_data.pop(
                "answer_question_directly", None
            )  # in case answer_question_directly will appear with _ in self.__dict__
            answer_question_directly_func = self.answer_question_directly

            if (
                answer_question_directly_func
                and raw_data.get("answer_question_directly_source_code", None) is not None
            ):
                raw_data["answer_question_directly_source_code"] = inspect.getsource(
                    answer_question_directly_func
                )
                raw_data["answer_question_directly_function_name"] = (
                    self.answer_question_directly_function_name
                )
        raw_data["traits"] = dict(raw_data["traits"])

        if hasattr(self, "trait_categories"):
            if self.trait_categories:
                raw_data["trait_categories"] = self.trait_categories

        return raw_data

    def __hash__(self) -> int:
        """Return a hash of the agent.

        >>> hash(Agent.example())
        2067581884874391607
        """
        return dict_hash(self.to_dict(add_edsl_version=False))

    def to_dict(self, add_edsl_version=True, full_dict=False) -> dict[str, Union[dict, bool]]:
        """Serialize to a dictionary with EDSL info.

        Example usage:

        >>> a = Agent(name = "Steve", traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.to_dict()
        {'traits': {'age': 10, 'hair': 'brown', 'height': 5.5}, 'name': 'Steve', 'edsl_version': '...', 'edsl_class_name': 'Agent'}

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5}, instruction = "Have fun.")
        >>> a.to_dict()
        {'traits': {'age': 10, 'hair': 'brown', 'height': 5.5}, 'instruction': 'Have fun.', 'edsl_version': '...', 'edsl_class_name': 'Agent'}
        """
        d = {}
        d["traits"] = copy.deepcopy(dict(self._traits))
        if self.name:
            d["name"] = self.name
        if self.set_instructions or full_dict:
            d["instruction"] = self.instruction
        if self.set_traits_presentation_template or full_dict:
            d["traits_presentation_template"] = self.traits_presentation_template
        if self.codebook or full_dict:
            d["codebook"] = self.codebook
        if self.trait_categories or full_dict:
            d["trait_categories"] = self.trait_categories
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, agent_dict: dict[str, Union[dict, bool]]) -> Agent:
        """Deserialize from a dictionary.

        Example usage:

        >>> Agent.from_dict({'name': "Steve", 'traits': {'age': 10, 'hair': 'brown', 'height': 5.5}})
        Agent(name = \"""Steve\""", traits = {'age': 10, 'hair': 'brown', 'height': 5.5})

        """
        if "traits" in agent_dict:
            if "trait_categories" in agent_dict:
                trait_categories = agent_dict.pop("trait_categories", {})
            else:
                trait_categories = {}
            return cls(
                traits=agent_dict["traits"],
                name=agent_dict.get("name", None),
                instruction=agent_dict.get("instruction", None),
                traits_presentation_template=agent_dict.get(
                    "traits_presentation_template", None
                ),
                codebook=agent_dict.get("codebook", None),
                trait_categories=trait_categories,
            )
        else:  # old-style agent - we used to only store the traits
            return cls(**agent_dict)

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data."""
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    def add_trait(self, trait_name_or_dict: str, value: Optional[Any] = None) -> Agent:
        """Adds a trait to an agent and returns that agent
        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.add_trait("weight", 150)
        Agent(traits = {'age': 10, 'hair': 'brown', 'height': 5.5, 'weight': 150})
        """
        if isinstance(trait_name_or_dict, dict) and value is None:
            newagent = self.duplicate()
            newagent.traits = {**self.traits, **trait_name_or_dict}
            return newagent

        if isinstance(trait_name_or_dict, dict) and value:
            raise AgentErrors(
                f"You passed a dict: {trait_name_or_dict} and a value: {value}. You should pass only a dict."
            )

        if isinstance(trait_name_or_dict, str):
            newagent = self.duplicate()
            newagent.traits = {**self.traits, **{trait_name_or_dict: value}}
            return newagent

        raise AgentErrors("Something is not right with adding a trait to an Agent")

    def remove_trait(self, trait: str) -> Agent:
        """Remove a trait from the agent.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.remove_trait("age")
        Agent(traits = {'hair': 'brown', 'height': 5.5})
        """
        newagent = self.duplicate()
        newagent.traits = {k: v for k, v in self.traits.items() if k != trait}
        return newagent

    def translate_traits(self, values_codebook: dict) -> Agent:
        """Translate traits to a new codebook.

        >>> a = Agent(traits = {"age": 10, "hair": 1, "height": 5.5})
        >>> a.translate_traits({"hair": {1:"brown"}})
        Agent(traits = {'age': 10, 'hair': 'brown', 'height': 5.5})

        :param values_codebook: The new codebook.
        """
        new_traits = {}
        for key, value in self.traits.items():
            if key in values_codebook:
                new_traits[key] = values_codebook[key].get(value, value)
            else:
                new_traits[key] = value
        newagent = self.duplicate()
        newagent.traits = new_traits
        return newagent

    @classmethod
    def example(cls, randomize: bool = False) -> Agent:
        """
        Returns an example Agent instance.

        :param randomize: If True, adds a random string to the value of an example key.

        >>> Agent.example()
        Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})
        """
        addition = "" if not randomize else str(uuid4())
        return cls(traits={"age": 22, "hair": f"brown{addition}", "height": 5.5})

    def code(self) -> str:
        """Return the code for the agent.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> print(a.code())
        from edsl.agents import Agent
        agent = Agent(traits={'age': 10, 'hair': 'brown', 'height': 5.5})
        """
        return f"from edsl.agents import Agent\nagent = Agent(traits={self.traits})"

    @classmethod
    def from_result(
        cls,
        result: "Result",
        name: Optional[str] = None,
    ) -> "Agent":
        """Create an Agent instance from an :pyclass:`edsl.results.Result` object.

        The agent's ``traits`` will correspond to the questions asked during the
        interview (the keys of ``result.answer``) with their respective answers
        as the values.

        A simple, readable ``traits_presentation_template`` is automatically
        generated so that rendering the agent will look like::

            They were asked the following questions – here are their answers:
            Q: <question 1>
            A: <answer 1>

            Q: <question 2>
            A: <answer 2>
            ...

        Parameters
        ----------
        result
            The :pyclass:`edsl.results.Result` instance from which to build the
            agent.
        name
            Optional explicit name for the new agent.  If omitted, we attempt
            to reuse ``result.agent.name`` if it exists.
        """
        # Import locally to avoid an import cycle when the agents module is
        # imported from results and vice-versa.
        from ..results import result as _result_module  # noqa: WPS433 – local import by design

        if not isinstance(result, _result_module.Result):
            raise TypeError("from_result expects an edsl.results.Result object")

        # 1. Traits are simply the answers dictionary (shallow-copied).
        traits: dict[str, Any] = dict(result.answer)

        # 2. Where available, build a codebook mapping question keys to their
        #    human-readable question text.  This improves prompt readability
        #    but falls back gracefully if the information is missing.
        codebook: dict[str, str] = {}
        question_attrs = getattr(result, "question_to_attributes", None)
        if question_attrs:
            from ..prompts import Prompt

            for qname, attrs in question_attrs.items():
                qtext_template = attrs.get("question_text", qname)

                # If the question text contains Jinja variables, render it with the
                # scenario context so it becomes a fully populated human-readable
                # string.  We fall back gracefully if rendering fails for any
                # reason (e.g. missing variables).
                try:
                    rendered_qtext = (
                        Prompt(text=qtext_template)
                        .render(result.scenario)  # scenario provides replacement vars
                        .text
                    )
                except Exception:
                    rendered_qtext = qtext_template

                codebook[qname] = rendered_qtext

        # 3. Provide a presentation template that lists the Q&A pairs.
        # Build a Jinja2 template that gracefully handles repeated observations
        # (i.e. when a trait value is a list because the question was asked
        # more than once).
        template_lines = [
            "This person was asked the following questions – here are the answers:",
            "{% for key, value in traits.items() %}",
            "Q: {{ codebook[key] if codebook and key in codebook else key }}",
            "{% if value is iterable and value is not string %}",
            "    {% for v in value %}",
            "A: {{ v }}",
            "    {% endfor %}",
            "{% else %}",
            "A: {{ value }}",
            "{% endif %}",
            "",
            "{% endfor %}",
        ]
        traits_presentation_template = "\n".join(template_lines)

        # 4. Fallback to the name inside the original agent if not provided.
        if name is None and hasattr(result, "agent") and getattr(result.agent, "name", None):
            name = result.agent.name

        return cls(
            traits=traits,
            name=name,
            codebook=codebook,
            traits_presentation_template=traits_presentation_template,
        )


def main():
    """
    Give an example of usage.

    WARNING: Consume API credits
    """
    from ..agents import Agent
    from ..questions import QuestionMultipleChoice

    # a simple agent
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    agent.traits
    agent.print()
    # combining two agents
    agent = Agent(traits={"age": 10}) + Agent(traits={"height": 5.7})
    agent.traits
    # Agent -> Job using the to() method
    agent = Agent(traits={"allergies": "peanut"})
    question = QuestionMultipleChoice(
        question_text="Would you enjoy a PB&J?",
        question_options=["Yes", "No"],
        question_name="food_preference",
    )
    job = question.by(agent)
    job.run()  # results not used


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)


    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5, "gender": "male"}, trait_categories={"demographics": ["age", "gender"]})
    agent.with_categories("demographics")