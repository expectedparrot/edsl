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
from uuid import uuid4
from typing import (
    Callable,
    Optional,
    Union,
    Any,
    TYPE_CHECKING,
    Protocol,
    runtime_checkable,
    TypeVar,
    List,
)

from ..base import Base

# from ..scenarios import Scenario
from ..data_transfer_models import AgentResponseDict

from ..utilities import (
    sync_wrapper,
    dict_hash,
    remove_edsl_version,
)

from .exceptions import (
    AgentErrors,
)

from .descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
    NameDescriptor,
)


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
    from .agent_delta import AgentDelta
    from ..jobs import Jobs
    from ..dataset import Dataset
    from ..results import Result
    from ..utilities.similarity_rank import RankableItems  # type: ignore[import-untyped]

# Type alias for trait categories
OrganizedTraits = dict[str, list[str]]

# Type variable for the Agent class
A = TypeVar("A", bound="Agent")


@runtime_checkable
class DirectAnswerMethod(Protocol):
    """Protocol defining the required signature for direct answer methods.

    Args:
        self_: The agent instance
        question: The question being asked
        scenario: The scenario context

    Returns:
        The answer to the question
    """

    def __call__(self, self_: A, question: "QuestionBase", scenario: "Scenario") -> Any:
        ...


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
    answer_question_directly_function_name = ""

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
        **kwargs: Any,
    ):
        """Initialize a new Agent instance with specified traits and capabilities.

        Args:
            traits: Dictionary of agent characteristics (e.g., {"age": 30, "occupation": "doctor"}).
                If None and additional keyword arguments are provided, those kwargs will be used as traits.
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
            **kwargs: Additional keyword arguments. If traits is None, these will be used as traits.

        The Agent class brings together several key concepts:

        Traits
        ------
        Traits are key-value pairs that define an agent's characteristics. These are used
        to construct a prompt that guides the language model on how to respond.

        Example:
        >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}

        You can also pass traits directly as keyword arguments:
        >>> a = Agent(age=10, hair="brown", height=5.5)
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
        # If traits is None and kwargs are provided, use kwargs as traits
        if traits is None and kwargs:
            traits = kwargs
        
        # Initialize basic attributes directly
        self.name = name

        # Initialize current_question early to avoid issues during initialization
        self.current_question = None

        # Initialize managers early
        from .agent_direct_answering import AgentDirectAnswering
        from .agent_traits_manager import AgentTraitsManager
        from .agent_prompt import AgentPrompt
        from .agent_instructions import AgentInstructions
        from .agent_table import AgentTable

        self.direct_answering = AgentDirectAnswering(self)
        # Lazy initialize invigilator to avoid importing language_models during Survey import
        self._invigilator = None
        self.traits_manager = AgentTraitsManager(self)
        self.prompt_manager = AgentPrompt(self)
        self.instructions = AgentInstructions(self)
        self.table_manager = AgentTable(self)

        # Maintain backward compatibility aliases
        self.trait_manager = self.traits_manager  # Alias for backward compatibility
        self.dynamic_traits = self.traits_manager  # Alias for backward compatibility

        # Initialize traits and codebook using the unified traits manager
        self.traits_manager.initialize(traits, codebook)

        # Initialize instruction using the manager
        self.instructions.initialize(instruction)

        # Initialize dynamic traits function
        self.traits_manager.initialize_dynamic_function(
            dynamic_traits_function,
            dynamic_traits_function_source_code,
            dynamic_traits_function_name,
        )

        # Initialize direct answering method
        self.direct_answering.initialize_from_source_code(
            answer_question_directly_source_code, answer_question_directly_function_name
        )

        self.traits_manager.validate_dynamic_function()

        # Initialize traits presentation template
        self.prompt_manager.initialize_traits_presentation_template(
            traits_presentation_template
        )

        self.trait_categories = trait_categories or {}
    
    @property
    def base_name(self) -> str | None:
        """Get the base name of the agent.
        
        Extracts the base name from various name formats:
        - If name is a dict, returns the "name" key value
        - If name is a string representation of a dict, parses it and returns the "name" key value
        - Otherwise, returns the name as-is
        
        Examples:
        >>> from edsl.agents import Agent
        >>> a = Agent(name="Alice")
        >>> a.base_name
        'Alice'
        
        >>> a = Agent(name="{'name': 'Bob', 'title': 'Dr'}")
        >>> a.base_name
        'Bob'
        
        >>> a = Agent(name="{'title': 'Dr', 'id': '123'}")
        >>> a.base_name
        "{'title': 'Dr', 'id': '123'}"
        
        >>> a = Agent()
        >>> a.base_name is None
        True
        """
        import ast
        if isinstance(self.name, dict):
            return self.name.get("name", None)

        try:
            naming_dict = ast.literal_eval(self.name)
            if "name" in naming_dict:
                return naming_dict["name"]
            else:
                return self.name
        except ValueError:
            return self.name

    @property
    def traits_presentation_template(self):
        """Get the traits presentation template."""
        return self._traits_presentation_template

    @traits_presentation_template.setter
    def traits_presentation_template(self, value):
        """Set the traits presentation template and mark it as explicitly set."""
        self._traits_presentation_template = value
        self.set_traits_presentation_template = True

    @property
    def invigilator(self):
        """Lazily initialize the invigilator to avoid importing language_models during Survey import"""
        if self._invigilator is None:
            from .agent_invigilator import AgentInvigilator

            self._invigilator = AgentInvigilator(self)
        return self._invigilator

    def with_categories(self, *categories: str) -> Agent:
        """Return a new agent with the specified categories"""
        new_agent = self.duplicate()
        new_traits = {}
        for category in categories:
            if category not in self.trait_categories:
                raise AgentErrors(f"Category {category} not found in agent categories")
            for trait_key in self.trait_categories[category]:
                new_traits[trait_key] = self.traits[trait_key]
        new_agent.trait_manager.set_all_traits(new_traits)
        return new_agent

    def add_category(
        self, category_name: str, trait_keys: Optional[list[str]] = None
    ) -> None:
        """Add a category to the agent"""
        if category_name not in self.trait_categories:
            self.trait_categories[category_name] = []
        if trait_keys:
            for trait_key in trait_keys:
                if trait_key not in self.traits:
                    raise AgentErrors(f"Trait {trait_key} not found in agent traits")
                self.trait_categories[category_name].append(trait_key)

    def chat(self):
        from .agent_chat import AgentChat

        return AgentChat(self).run()

    def drop(self, *field_names: Union[str, List[str]]) -> "Agent":
        """Drop field(s) from the agent.

        Args:
            *field_names: The name(s) of the field(s) to drop. Can be:
                - Single field name: drop("age")
                - Multiple field names: drop("age", "height")
                - List of field names: drop(["age", "height"])

        Examples:
            Drop a single trait from the agent:

            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_dropped = a.drop("age")
            >>> a_dropped.traits
            {'hair': 'brown', 'height': 5.5}

            Drop multiple traits using separate arguments:

            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_dropped = a.drop("age", "height")
            >>> a_dropped.traits
            {'hair': 'brown'}

            Drop multiple traits using a list:

            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_dropped = a.drop(["age", "height"])
            >>> a_dropped.traits
            {'hair': 'brown'}

            Drop an agent field like name:

            >>> a = Agent(traits={"age": 30}, name="John")
            >>> a_dropped = a.drop("name")
            >>> a_dropped.name is None
            True
            >>> a_dropped.traits
            {'age': 30}

            Error when trying to drop a non-existent field:

            >>> a = Agent(traits={"age": 30})
            >>> a.drop("nonexistent")  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentErrors: ...
        """
        from .agent_operations import AgentOperations

        return AgentOperations.drop(self, *field_names)

    def keep(self, *field_names: Union[str, List[str]]) -> "Agent":
        """Keep only the specified fields from the agent.

        Args:
            *field_names: The name(s) of the field(s) to keep. Can be:
                - Single field name: keep("age")
                - Multiple field names: keep("age", "height")
                - List of field names: keep(["age", "height"])

        Examples:
            Keep a single trait:

            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_kept = a.keep("age")
            >>> a_kept.traits
            {'age': 30}

            Keep multiple traits using separate arguments:

            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_kept = a.keep("age", "height")
            >>> a_kept.traits
            {'age': 30, 'height': 5.5}

            Keep multiple traits using a list:

            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_kept = a.keep(["age", "height"])
            >>> a_kept.traits
            {'age': 30, 'height': 5.5}

            Keep agent fields and traits:

            >>> a = Agent(traits={"age": 30, "hair": "brown"}, name="John")
            >>> a_kept = a.keep("name", "age")
            >>> a_kept.name
            'John'
            >>> a_kept.traits
            {'age': 30}

            Error when trying to keep a non-existent field:

            >>> a = Agent(traits={"age": 30})
            >>> a.keep("nonexistent")  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentErrors: ...
        """
        from .agent_operations import AgentOperations

        return AgentOperations.keep(self, *field_names)

    def duplicate(self, add_edsl_version: bool = False) -> "Agent":
        """Create a deep copy of this agent with all its traits and capabilities.

        This method creates a completely independent copy of the agent, including
        all its traits, codebook, instructions, and special functions like dynamic
        traits and direct answering methods.

        Args:
            add_edsl_version: Whether to include EDSL version information (ignored for agents)

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
        new_agent = Agent.from_dict(self.to_dict(add_edsl_version=add_edsl_version))

        # Transfer direct answering method if present
        self.direct_answering.transfer_to(new_agent)

        # Transfer dynamic traits function if present
        self.traits_manager.transfer_to(new_agent)

        return new_agent

    def add_canned_response(self, question_name, response):
        """Add a canned response to the agent."""
        if not hasattr(self, "_canned_responses"):
            self._canned_responses = {}
        self._canned_responses[question_name] = response

        def f(self, question, scenario):
            if question.question_name in self._canned_responses:
                return self._canned_responses[question.question_name]
            else:
                return None

        self.remove_direct_question_answering_method()
        self.add_direct_question_answering_method(f)

    def copy(self) -> "Agent":
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
        return self.prompt_manager.agent_persona()

    def prompt(self) -> "Prompt":
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
        return self.prompt_manager.prompt()

    @property
    def traits(self) -> dict[str, Any]:
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
        return self.traits_manager.get_traits(self.current_question)

    @traits.setter
    def traits(self, traits: dict[str, Any]):
        """Set traits using the unified traits manager."""
        self.traits_manager.set_traits_safely(traits)

    def to(self, target: Union["QuestionBase", "Jobs", "Survey"]) -> "Jobs":
        """Send the agent to a question, job, or survey.

        Args:
            target: The question, job, or survey to send the agent to

        Returns:
            A Jobs object containing the agent and target

        Example:
            >>> agent = Agent(traits={'age': 30})
            >>> from edsl.questions import QuestionFreeText
            >>> q = QuestionFreeText(question_name='test', question_text='How are you?')
            >>> job = agent.to(q)
            >>> type(job).__name__
            'Jobs'
        """
        from .agent_list import AgentList

        return AgentList([self]).to(target)

    def search_traits(self, search_string: str) -> "RankableItems":
        """Search the agent's traits for a string.

        This method delegates to the traits manager to search through trait
        descriptions and return ranked matches based on similarity.

        Args:
            search_string: The string to search for in trait descriptions

        Returns:
            A ScenarioList containing ranked trait matches

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30, "occupation": "doctor"})
            >>> results = agent.search_traits("age")
            >>> len(results) >= 1
            True
        """
        return self.traits_manager.search_traits(search_string)

    def rename(
        self,
        old_name_or_dict: Union[str, dict[str, str]],
        new_name: Optional[str] = None,
    ) -> "Agent":
        """Rename a trait.

        Args:
            old_name_or_dict: The old name of the trait or a dictionary of old names and new names
            new_name: The new name of the trait (required if old_name_or_dict is a string)

        Returns:
            A new Agent instance with renamed traits

        Raises:
            AgentErrors: If invalid arguments are provided

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> newa = a.rename("age", "years")
            >>> newa == Agent(traits = {'years': 10, 'hair': 'brown', 'height': 5.5})
            True

            >>> newa.rename({'years': 'smage'}) == Agent(traits = {'smage': 10, 'hair': 'brown', 'height': 5.5})
            True
        """
        from .agent_operations import AgentOperations

        return AgentOperations.rename(self, old_name_or_dict, new_name)

    def __getitem__(self, key: str) -> Any:
        """Allow for accessing traits using the bracket notation.

        Args:
            key: The attribute name to access

        Returns:
            The attribute value

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> a['traits']['age']
            10
        """
        return getattr(self, key)

    def remove_direct_question_answering_method(self) -> None:
        """Remove the direct question answering method.

        Example:
            >>> a = Agent()
            >>> def f(self, question, scenario): return "I am a direct answer."
            >>> a.add_direct_question_answering_method(f)
            >>> a.remove_direct_question_answering_method()
            >>> hasattr(a, "answer_question_directly")
            False
        """
        self.direct_answering.remove_method()

    def add_direct_question_answering_method(
        self,
        method: DirectAnswerMethod,
        validate_response: bool = False,
        translate_response: bool = False,
    ) -> None:
        """Add a method to the agent that can answer a particular question type.

        See: https://docs.expectedparrot.com/en/latest/agents.html#agent-direct-answering-methods

        Args:
            method: A method that can answer a question directly
            validate_response: Whether to validate the response
            translate_response: Whether to translate the response

        Raises:
            AgentDirectAnswerFunctionError: If the method signature is invalid

        Example:
            >>> a = Agent()
            >>> def f(self, question, scenario): return "I am a direct answer."
            >>> a.add_direct_question_answering_method(f)
            >>> a.answer_question_directly(question = None, scenario = None)
            'I am a direct answer.'
        """
        self.direct_answering.add_method(method, validate_response, translate_response)

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
        For example, there are invigilators for functional questions, for direct questions, and for LLM questions.

        Args:
            question: The question to be asked
            cache: The cache for storing responses
            survey: The survey context
            scenario: The scenario context
            model: The language model to use
            memory_plan: The memory plan to use
            current_answers: The current answers
            iteration: The iteration number
            raise_validation_errors: Whether to raise validation errors
            key_lookup: The key lookup for API credentials

        Returns:
            An InvigilatorBase instance for handling the question

        Example:
            >>> a = Agent(traits = {})
            >>> inv = a.create_invigilator(question = None, cache = False)
            >>> type(inv).__name__
            'InvigilatorAI'

        Note:
            An invigilator is an object that is responsible for administering a question to an agent and
            recording the responses.
        """
        return self.invigilator.create_invigilator_with_context(
            question=question,
            cache=cache,
            survey=survey,
            scenario=scenario,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            raise_validation_errors=raise_validation_errors,
            key_lookup=key_lookup,
        )

    async def async_answer_question(
        self,
        *,
        question: "QuestionBase",
        cache: "Cache",
        scenario: Optional["Scenario"] = None,
        survey: Optional["Survey"] = None,
        model: Optional["LanguageModel"] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> AgentResponseDict:
        """Answer a posed question asynchronously.

        Args:
            question: The question to answer
            cache: The cache to use for storing responses
            scenario: The scenario in which the question is asked
            survey: The survey context
            model: The language model to use
            debug: Whether to run in debug mode
            memory_plan: The memory plan to use
            current_answers: The current answers
            iteration: The iteration number
            key_lookup: The key lookup for API credentials

        Returns:
            An AgentResponseDict containing the answer

        Example:
            >>> a = Agent(traits = {})
            >>> a.add_direct_question_answering_method(lambda self, question, scenario: "I am a direct answer.")
            >>> from edsl.questions import QuestionFreeText
            >>> q = QuestionFreeText.example()
            >>> a.answer_question(question = q, cache = False).answer
            'I am a direct answer.'

        Note:
            This is a function where an agent returns an answer to a particular question.
            However, there are several different ways an agent can answer a question, so the
            actual functionality is delegated to an InvigilatorBase object.
        """
        return await self.invigilator.async_answer_question(
            question=question,
            cache=cache,
            scenario=scenario,
            survey=survey,
            model=model,
            debug=debug,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            key_lookup=key_lookup,
        )

    answer_question = sync_wrapper(async_answer_question)

    def drop_trait_if(self, bad_value: Any) -> "Agent":
        """Drop traits that have a specific bad value.

        Args:
            bad_value: The value to remove from traits

        Returns:
            A new Agent instance with the bad value traits removed

        Example:
            >>> agent = Agent(traits={'age': 30, 'height': None, 'weight': 150})
            >>> clean_agent = agent.drop_trait_if(None)
            >>> clean_agent.traits
            {'age': 30, 'weight': 150}
        """
        return self.traits_manager.drop_trait_if(bad_value)

    def old_keep(self, *traits: str) -> "Agent":
        """Legacy trait selection method (renamed from select).

        Note: This method has data integrity issues and is kept for backward compatibility.
        Use select() or keep() instead, which provide better data consistency.

        Args:
            *traits: The trait names to select

        Returns:
            A new Agent instance with only the selected traits

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5}, codebook = {'age': 'Their age is'})
            >>> a.old_keep("age", "height")
            Agent(traits = {'age': 10, 'height': 5.5}, codebook = {'age': 'Their age is'})

            >>> a.old_keep("height")
            Agent(traits = {'height': 5.5})
        """

        if len(traits) == 1:
            traits_to_select = [list(traits)[0]]
        else:
            traits_to_select = list(traits)

        def _remove_none(d):
            return {k: v for k, v in d.items() if v is not None}

        newagent = self.duplicate()
        new_traits = {trait: self.traits.get(trait, None) for trait in traits_to_select}
        newagent.trait_manager.set_all_traits(new_traits)
        newagent.codebook = _remove_none(
            {trait: self.codebook.get(trait, None) for trait in traits_to_select}
        )
        return newagent

    def select(self, *traits: str) -> "Agent":
        """Select agents with only the referenced traits.

        This method now uses the robust keep() implementation for better data integrity
        and consistent handling of codebooks and trait_categories.

        Args:
            *traits: The trait names to select

        Returns:
            A new Agent instance with only the selected traits

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5}, codebook = {'age': 'Their age is'})
            >>> a.select("age", "height")
            Agent(traits = {'age': 10, 'height': 5.5}, codebook = {'age': 'Their age is'})

            >>> a.select("height")
            Agent(traits = {'height': 5.5})
        """
        from .agent_operations import AgentOperations

        return AgentOperations.select(self, *traits)

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
        from .agent_combination import AgentCombination

        return AgentCombination.add(
            self, other_agent, conflict_strategy=conflict_strategy
        )

    def __add__(self, other_agent: Optional["Agent"] = None) -> "Agent":
        """Syntactic sugar – delegates to :pymeth:`add`."""
        from .agent_combination import AgentCombination

        return AgentCombination.add_with_plus_operator(self, other_agent)

    def __eq__(self, other: object) -> bool:
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
        if not isinstance(other, Agent):
            return NotImplemented
        # return self.data == other.data
        return hash(self) == hash(other)

    # Backward compatibility properties for dynamic traits
    @property
    def has_dynamic_traits_function(self) -> bool:
        """Whether the agent has a dynamic traits function.

        This property provides backward compatibility for the old attribute access pattern.

        Returns:
            True if the agent has a dynamic traits function, False otherwise

        Examples:
            >>> agent = Agent(traits={'age': 30})
            >>> agent.has_dynamic_traits_function
            False
            >>> def dynamic_func(): return {'age': 25}
            >>> agent.traits_manager.initialize_dynamic_function(dynamic_func)
            >>> agent.has_dynamic_traits_function
            True
        """
        return self.traits_manager.has_dynamic_function

    @property
    def dynamic_traits_function(self) -> Optional[Callable]:
        """The dynamic traits function if one exists.

        This property provides backward compatibility for the old attribute access pattern.

        Returns:
            The dynamic traits function or None

        Examples:
            >>> agent = Agent(traits={'age': 30})
            >>> agent.dynamic_traits_function is None
            True
            >>> def dynamic_func(): return {'age': 25}
            >>> agent.traits_manager.initialize_dynamic_function(dynamic_func)
            >>> agent.dynamic_traits_function is not None
            True
        """
        return self.traits_manager.dynamic_function

    @dynamic_traits_function.setter
    def dynamic_traits_function(self, function: Optional[Callable]) -> None:
        """Set the dynamic traits function.

        This setter allows you to easily assign a dynamic traits function to an
        already-instantiated agent using simple assignment syntax.

        Args:
            function: The function to set, or None to remove the current function

        Examples:
            Set a dynamic traits function:

            >>> agent = Agent(traits={'age': 30})
            >>> def my_func():
            ...     return {'age': 25, 'dynamic': True}
            >>> agent.dynamic_traits_function = my_func
            >>> agent.has_dynamic_traits_function
            True

            Remove a dynamic traits function:

            >>> agent.dynamic_traits_function = None
            >>> agent.has_dynamic_traits_function
            False
        """
        if function is None:
            self.traits_manager.remove_function()
        else:
            self.traits_manager.initialize_dynamic_function(function)

    @property
    def dynamic_traits_function_name(self) -> str:
        """The name of the dynamic traits function.

        This property provides backward compatibility for the old attribute access pattern.

        Returns:
            The function name or empty string if no function

        Examples:
            >>> agent = Agent(traits={'age': 30})
            >>> agent.dynamic_traits_function_name
            ''
            >>> def my_func(): return {'age': 25}
            >>> agent.traits_manager.initialize_dynamic_function(my_func)
            >>> agent.dynamic_traits_function_name
            'my_func'
        """
        return self.traits_manager.dynamic_function_name

    def __getattr__(self, name: str) -> Any:
        """Get an attribute, checking traits if not found in instance.

        This method now only handles trait access for backward compatibility.
        All other dynamic attributes have been converted to proper properties.

        Args:
            name: The attribute name to get

        Returns:
            The attribute value

        Raises:
            AttributeError: If the attribute is not found

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> a.age
            10
        """
        if name in self._traits:
            return self._traits[name]

        # Keep using AttributeError instead of our custom exception to maintain compatibility
        # with Python's attribute access mechanism
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __getstate__(self) -> dict:
        """Get state for pickling.

        Returns:
            The instance state dictionary

        Example:
            >>> agent = Agent(traits={'age': 30})
            >>> state = agent.__getstate__()
            >>> isinstance(state, dict)
            True
        """
        state = self.__dict__.copy()
        # Include any additional state that needs to be serialized
        return state

    def __setstate__(self, state: dict) -> None:
        """Set state from unpickling.

        Args:
            state: The state dictionary to restore

        Example:
            >>> agent = Agent(traits={'age': 30})
            >>> state = agent.__getstate__()
            >>> new_agent = Agent.__new__(Agent)
            >>> new_agent.__setstate__(state)
            >>> new_agent.traits['age']
            30
        """
        self.__dict__.update(state)
        # Ensure _traits is initialized if it's missing
        if "_traits" not in self.__dict__:
            self._traits = {}

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the Agent.

        This representation can be used with eval() to recreate the Agent object.
        Used primarily for doctests and debugging.
        """
        class_name = self.__class__.__name__
        items = [
            f'{k} = """{v}"""' if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k not in ("question_type", "invigilator") and not k.startswith("_")
        ]
        return f"{class_name}({', '.join(items)})"

    def _summary_repr(self, max_traits: int = 5) -> str:
        """Generate a summary representation of the Agent with Rich formatting.

        Args:
            max_traits: Maximum number of traits to show before truncating
        """
        from rich.console import Console
        from rich.text import Text
        import io

        # Build the Rich text
        output = Text()
        class_name = self.__class__.__name__

        output.append(f"{class_name}(\n", style="bold cyan")

        # Name (if present)
        if self.name:
            output.append("    name=", style="white")
            output.append(f'"{self.name}"', style="green")
            output.append(",\n", style="white")

        # Traits
        traits = self.traits
        num_traits = len(traits)
        output.append(f"    num_traits={num_traits}", style="white")

        if num_traits > 0:
            output.append(",\n    traits={\n", style="white")

            for i, (key, value) in enumerate(list(traits.items())[:max_traits]):
                value_repr = repr(value)
                if len(value_repr) > 40:
                    value_repr = value_repr[:37] + "..."

                output.append("        ", style="white")
                output.append(f"'{key}'", style="bold yellow")
                output.append(f": {value_repr},\n", style="white")

            if num_traits > max_traits:
                output.append(
                    f"        ... ({num_traits - max_traits} more)\n", style="dim"
                )

            output.append("    }", style="white")

        # Codebook (if present)
        if self.codebook:
            num_codebook = len(self.codebook)
            output.append(",\n    ", style="white")
            output.append(f"num_codebook_entries={num_codebook}", style="magenta")

        # Instruction (if custom)
        if self.instruction != self.default_instruction:
            instruction_text = self.instruction
            if len(instruction_text) > 50:
                instruction_text = instruction_text[:47] + "..."
            output.append(",\n    instruction=", style="white")
            output.append(f'"{instruction_text}"', style="cyan")

        # Dynamic traits function (if present)
        if self.has_dynamic_traits_function:
            func_name = self.dynamic_traits_function_name or "anonymous"
            output.append(",\n    ", style="white")
            output.append(f"dynamic_traits_function='{func_name}'", style="blue")

        # Direct answering method (if present)
        if hasattr(self, "answer_question_directly"):
            func_name = getattr(
                self, "answer_question_directly_function_name", "anonymous"
            )
            output.append(",\n    ", style="white")
            output.append(f"direct_answer_method='{func_name}'", style="blue")

        output.append("\n)", style="bold cyan")

        # Render to string
        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        console.print(output, end="")
        return string_io.getvalue()

    @property
    def data(self) -> dict:
        """Format the data for serialization.

        Returns:
            A dictionary containing the agent's serializable data

        Todo:
            * Warn if has dynamic traits function or direct answer function that cannot be serialized
            * Add ability to have coop-hosted functions that are serializable

        Example:
            >>> agent = Agent(traits={'age': 30}, name='John')
            >>> data = agent.data
            >>> 'traits' in data
            True
        """
        from .agent_serialization import AgentSerialization

        return AgentSerialization.data(self)

    def __hash__(self) -> int:
        """Return a hash of the agent.

        Returns:
            A hash value for the agent

        Example:
            >>> hash(Agent.example())
            2067581884874391607
        """
        # Cache the hash to avoid expensive to_dict() calls on every hash lookup
        # This is safe because agents should be immutable after creation
        if not hasattr(self, "_cached_hash"):
            self._cached_hash = dict_hash(self.to_dict(add_edsl_version=False))
        return self._cached_hash

    def to_dict(
        self, add_edsl_version: bool = True, full_dict: bool = False
    ) -> dict[str, Union[dict, bool, str]]:
        """Serialize to a dictionary with EDSL info.

        Args:
            add_edsl_version: Whether to include EDSL version information
            full_dict: Whether to include all attributes even if they have default values

        Returns:
            A dictionary representation of the agent

        Example:
            >>> a = Agent(name = "Steve", traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> d = a.to_dict()
            >>> d['traits']
            {'age': 10, 'hair': 'brown', 'height': 5.5}
            >>> d['name']
            'Steve'
            >>> d['edsl_class_name']
            'Agent'

            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5}, instruction = "Have fun.")
            >>> d = a.to_dict()
            >>> d['traits']
            {'age': 10, 'hair': 'brown', 'height': 5.5}
            >>> d['instruction']
            'Have fun.'
            >>> d['edsl_class_name']
            'Agent'
        """
        from .agent_serialization import AgentSerialization

        return AgentSerialization.to_dict(self, add_edsl_version, full_dict)

    @classmethod
    @remove_edsl_version
    def from_dict(cls, agent_dict: dict[str, Union[dict, bool, str]]) -> Agent:
        """Deserialize from a dictionary.

        Args:
            agent_dict: Dictionary containing agent data

        Returns:
            An Agent instance created from the dictionary

        Example:
            >>> Agent.from_dict({'name': "Steve", 'traits': {'age': 10, 'hair': 'brown', 'height': 5.5}})
            Agent(name = \"""Steve\""", traits = {'age': 10, 'hair': 'brown', 'height': 5.5})
        """
        from .agent_serialization import AgentSerialization

        return AgentSerialization.from_dict(agent_dict)

    def table(self) -> "Dataset":
        """Create a tabular representation of the agent's traits.

        This method delegates to the table manager to create a structured
        Dataset containing trait information.

        Returns:
            A Dataset containing trait information

        Example:
            >>> agent = Agent(traits={'age': 30, 'height': 5.5}, codebook={'age': 'Age in years'})
            >>> dataset = agent.table()
            >>> len(dataset) == 2
            True
        """
        return self.table_manager.table()

    def _table(self) -> tuple[list[dict], list[str]]:
        """Prepare generic table data.

        This method delegates to the table manager to create generic
        attribute table data for debugging and introspection.

        Returns:
            A tuple of (table_data, column_names)

        Example:
            >>> agent = Agent(traits={'age': 30})
            >>> data, columns = agent._table()
            >>> 'Attribute' in columns
            True
        """
        return self.table_manager.generic_table()

    def add_trait(
        self,
        trait_name_or_dict: Union[str, dict[str, Any]],
        value: Optional[Any] = None,
    ) -> "Agent":
        """Add a trait to an agent and return a new agent.

        Args:
            trait_name_or_dict: Either a trait name string or a dictionary of traits
            value: The trait value if trait_name_or_dict is a string

        Returns:
            A new Agent instance with the added trait(s)

        Raises:
            AgentErrors: If both a dictionary and a value are provided

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> a.add_trait("weight", 150)
            Agent(traits = {'age': 10, 'hair': 'brown', 'height': 5.5, 'weight': 150})
        """
        return self.traits_manager.add_trait(trait_name_or_dict, value)

    def remove_trait(self, trait: str) -> "Agent":
        """Remove a trait from the agent.

        Args:
            trait: The name of the trait to remove

        Returns:
            A new Agent instance without the specified trait

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> a.remove_trait("age")
            Agent(traits = {'hair': 'brown', 'height': 5.5})
        """
        return self.traits_manager.remove_trait(trait)

    def update_trait(self, trait_name: str, value: Any) -> "Agent":
        """Update an existing trait value.

        This method modifies the value of an existing trait. If the trait
        doesn't exist, it raises an AgentErrors exception. To add a new trait,
        use add_trait() instead.

        Args:
            trait_name: The name of the trait to update
            value: The new value for the trait

        Returns:
            A new Agent instance with the updated trait value

        Raises:
            AgentErrors: If the trait doesn't exist

        Examples:
            Update an existing trait value:

            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> a_updated = a.update_trait("age", 11)
            >>> a_updated.traits
            {'age': 11, 'hair': 'brown', 'height': 5.5}

            Update with a different type:

            >>> a = Agent(traits={"age": 10, "hair": "brown"})
            >>> a_updated = a.update_trait("hair", "black")
            >>> a_updated.traits
            {'age': 10, 'hair': 'black'}

            Error when trying to update a non-existent trait:

            >>> a = Agent(traits={"age": 10})
            >>> a.update_trait("weight", 150)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentErrors: ...
        """
        return self.traits_manager.update_trait(trait_name, value)

    def translate_traits(self, values_codebook: dict[str, dict[Any, Any]]) -> "Agent":
        """Translate traits to a new codebook.

        Args:
            values_codebook: Dictionary mapping trait names to value translation dictionaries

        Returns:
            A new Agent instance with translated trait values

        Example:
            >>> a = Agent(traits = {"age": 10, "hair": 1, "height": 5.5})
            >>> a.translate_traits({"hair": {1:"brown"}})
            Agent(traits = {'age': 10, 'hair': 'brown', 'height': 5.5})
        """
        return self.traits_manager.translate_traits(values_codebook)

    def apply_delta(self, delta: "AgentDelta") -> "Agent":
        """Apply an AgentDelta to create a new agent with updated trait values.

        This is a convenience method that delegates to AgentDelta.apply().

        Args:
            delta: The AgentDelta to apply

        Returns:
            A new Agent instance with the updated trait values

        Raises:
            AgentErrors: If any trait in the delta doesn't exist in this agent

        Examples:
            Apply a delta to update agent traits:

            >>> from edsl.agents import AgentDelta
            >>> a = Agent(traits={'age': 30, 'height': 5.5})
            >>> delta = AgentDelta({'age': 31})
            >>> updated = a.apply_delta(delta)
            >>> updated.traits
            {'age': 31, 'height': 5.5}

            Multiple trait updates:

            >>> delta = AgentDelta({'age': 35, 'height': 5.8})
            >>> updated = a.apply_delta(delta)
            >>> updated.traits
            {'age': 35, 'height': 5.8}

            Error when trait doesn't exist:

            >>> bad_delta = AgentDelta({'weight': 150})
            >>> a.apply_delta(bad_delta)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentErrors: ...
        """
        return delta.apply(self)

    @classmethod
    def example(cls, randomize: bool = False) -> "Agent":
        """Return an example Agent instance.

        Args:
            randomize: If True, adds a random string to the value of an example key

        Returns:
            An example Agent instance

        Example:
            >>> Agent.example()
            Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})
        """
        addition = "" if not randomize else str(uuid4())
        return cls(traits={"age": 22, "hair": f"brown{addition}", "height": 5.5})

    def code(self) -> str:
        """Return the code for the agent.

        Returns:
            Python code string to recreate this agent

        Example:
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
        """Create an Agent instance from a Result object.

        The agent's traits will correspond to the questions asked during the
        interview (the keys of result.answer) with their respective answers
        as the values.

        A simple, readable traits_presentation_template is automatically
        generated so that rendering the agent will look like::

            This person was asked the following questions – here are the answers:
            Q: <question 1>
            A: <answer 1>

            Q: <question 2>
            A: <answer 2>
            ...

        Args:
            result: The Result instance from which to build the agent
            name: Optional explicit name for the new agent. If omitted, we attempt
                to reuse result.agent.name if it exists

        Returns:
            A new Agent instance created from the result

        Raises:
            TypeError: If result is not a Result object

        Example:
            >>> from edsl.results import Result  # doctest: +SKIP
            >>> # result = Result(...)
            >>> # agent = Agent.from_result(result)
        """
        from .agent_from_result import AgentFromResult

        return AgentFromResult.from_result(result, name)


def main() -> None:
    """Give an example of usage.

    Warning:
        This function consumes API credits when run.

    Example:
        >>> main()  # doctest: +SKIP
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
