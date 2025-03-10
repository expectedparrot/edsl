"""An Agent is an AI agent that can reference a set of traits in answering questions."""

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
)

# Type variable for the Agent class
A = TypeVar("A", bound="Agent")

if TYPE_CHECKING:
    from ..data import Cache
    from ..surveys import Survey
    from ..scenarios import Scenario
    from ..language_models import LanguageModel
    from ..surveys.memory import MemoryPlan
    from ..questions import QuestionBase
    from ..invigilators import InvigilatorBase
    from ..prompts import Prompt
    from ..questions import QuestionBase
    from ..key_management import KeyLookup


@runtime_checkable
class DirectAnswerMethod(Protocol):
    """Protocol defining the required signature for direct answer methods."""

    def __call__(self, self_: A, question: QuestionBase, scenario: Scenario) -> Any: ...


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


class AgentTraits(Scenario):
    """A class representing the traits of an agent."""

    def __repr__(self):
        return f"{self.data}"


class Agent(Base):
    """An class representing an agent that can answer questions."""

    __documentation__ = "https://docs.expectedparrot.com/en/latest/agents.html"

    default_instruction = """You are answering questions as if you were a human. Do not break character."""

    _traits = TraitsDescriptor()
    codebook = CodebookDescriptor()
    instruction = InstructionDescriptor()
    name = NameDescriptor()
    dynamic_traits_function_name = ""
    answer_question_directly_function_name = ""
    has_dynamic_traits_function = False

    def __init__(
        self,
        traits: Optional[dict] = None,
        name: Optional[str] = None,
        codebook: Optional[dict] = None,
        instruction: Optional[str] = None,
        traits_presentation_template: Optional[str] = None,
        dynamic_traits_function: Optional[Callable] = None,
        dynamic_traits_function_source_code: Optional[str] = None,
        dynamic_traits_function_name: Optional[str] = None,
        answer_question_directly_source_code: Optional[str] = None,
        answer_question_directly_function_name: Optional[str] = None,
    ):
        """Initialize a new instance of Agent.

        :param traits: A dictionary of traits that the agent has. The keys need to be valid identifiers.
        :param name: A name for the agent
        :param codebook: A codebook mapping trait keys to trait descriptions.
        :param instruction: Instructions for the agent in how to answer questions.
        :param trait_presentation_template: A template for how to present the agent's traits.
        :param dynamic_traits_function: A function that returns a dictionary of traits.
        :param dynamic_traits_function_source_code: The source code for the dynamic traits function.
        :param dynamic_traits_function_name: The name of the dynamic traits function.

        The `traits` parameter is a dictionary of traits that the agent has.
        These traits are used to construct a prompt that is presented to the LLM.
        In the absence of a `traits_presentation_template`, the default is used.
        This is a template that is used to present the agent's traits to the LLM.
        See :py:class:`edsl.prompts.library.agent_persona.AgentPersona` for more information.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}

        These traits are used to construct a prompt that is presented to the LLM.

        In the absence of a `traits_presentation_template`, the default is used.

        >>> a = Agent(traits = {"age": 10}, traits_presentation_template = "I am a {{age}} year old.")
        >>> repr(a.agent_persona)
        'Prompt(text=\"""I am a {{age}} year old.\""")'

        When this is rendered for presentation to the LLM, it will replace the `{{age}}` with the actual age.
        it is also possible to use the `codebook` to provide a more human-readable description of the trait.
        Here is an example where we give a prefix to the age trait (namely the age):

        >>> traits = {"age": 10, "hair": "brown", "height": 5.5}
        >>> codebook = {'age': 'Their age is'}
        >>> a = Agent(traits = traits, codebook = codebook, traits_presentation_template = "This agent is Dave. {{codebook['age']}} {{age}}")
        >>> d = a.traits | {'codebook': a.codebook}
        >>> a.agent_persona.render(d)
        Prompt(text=\"""This agent is Dave. Their age is 10\""")

        Instructions
        ------------
        The agent can also have instructions. These are instructions that are given to the agent when answering questions.

        >>> Agent.default_instruction
        'You are answering questions as if you were a human. Do not break character.'

        See see how these are used to actually construct the prompt that is presented to the LLM, see :py:class:`edsl.agents.Invigilator.InvigilatorBase`.

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

    def _initialize_basic_attributes(self, traits, name, codebook) -> None:
        """Initialize the basic attributes of the agent."""
        self.name = name
        self._traits = AgentTraits(traits or dict())
        self.codebook = codebook or dict()

    def _initialize_instruction(self, instruction) -> None:
        """Initialize the instruction for the agent i.e., how the agent should answer questions."""
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
        """Initialize the traits presentation template. How the agent's traits are presented to the LLM."""
        if traits_presentation_template is not None:
            self._traits_presentation_template = traits_presentation_template
            self.traits_presentation_template = traits_presentation_template
            self.set_traits_presentation_template = True
        else:
            self.traits_presentation_template = "Your traits: {{traits}}"
            self.set_traits_presentation_template = False

    def _initialize_dynamic_traits_function(
        self,
        dynamic_traits_function,
        dynamic_traits_function_source_code,
        dynamic_traits_function_name,
    ) -> None:
        """Initialize the dynamic traits function i.e., a function that returns a dictionary of traits based on the question."""
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

    def duplicate(self) -> Agent:
        """Return a duplicate of the agent.

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5}, codebook = {'age': 'Their age is'})
        >>> a2 = a.duplicate()
        >>> a2 == a
        True
        >>> id(a) == id(a2)
        False
        >>> def f(self, question, scenario): return "I am a direct answer."
        >>> a.add_direct_question_answering_method(f)
        >>> hasattr(a, "answer_question_directly")
        True
        >>> a2 = a.duplicate()
        >>> a2.answer_question_directly(None, None)
        'I am a direct answer.'

        >>> a = Agent(traits = {'age': 10}, instruction = "Have fun!")
        >>> a2 = a.duplicate()
        >>> a2.instruction
        'Have fun!'
        """
        new_agent = Agent.from_dict(self.to_dict())
        if hasattr(self, "answer_question_directly"):
            answer_question_directly = self.answer_question_directly
            newf = lambda self, question, scenario: answer_question_directly(
                question, scenario
            )
            new_agent.add_direct_question_answering_method(newf)
        if hasattr(self, "dynamic_traits_function"):
            dynamic_traits_function = self.dynamic_traits_function
            new_agent.dynamic_traits_function = dynamic_traits_function
        return new_agent

    @property
    def agent_persona(self) -> Prompt:
        """Return the agent persona template."""
        from ..prompts import Prompt

        return Prompt(text=self.traits_presentation_template)

    def prompt(self) -> str:
        """Return the prompt for the agent.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.prompt()
        Prompt(text=\"""Your traits: {'age': 10, 'hair': 'brown', 'height': 5.5}\""")
        """
        replacement_dict = (
            self.traits | {"traits": self.traits} | {"codebook": self.codebook}
        )
        if undefined := self.agent_persona.undefined_template_variables(
            replacement_dict
        ):
            raise QuestionScenarioRenderError(
                f"Agent persona still has variables that were not rendered: {undefined}"
            )
        else:
            return self.agent_persona.render(replacement_dict)

    def _check_dynamic_traits_function(self) -> None:
        """Check whether dynamic trait function is valid.

        This checks whether the dynamic traits function is valid.

        >>> def f(question): return {"age": 10, "hair": "brown", "height": 5.5}
        >>> a = Agent(dynamic_traits_function = f)
        >>> a._check_dynamic_traits_function()

        >>> def g(question, poo): return {"age": 10, "hair": "brown", "height": 5.5}
        >>> a = Agent(dynamic_traits_function = g)
        Traceback (most recent call last):
        ...
        edsl.agents.exceptions.AgentDynamicTraitsFunctionError: ...
        """
        if self.has_dynamic_traits_function:
            sig = inspect.signature(self.dynamic_traits_function)
            if "question" in sig.parameters:
                if len(sig.parameters) > 1:
                    raise AgentDynamicTraitsFunctionError(
                        message=f"The dynamic traits function {self.dynamic_traits_function} has too many parameters. It should only have one parameter: 'question'."
                    )
            else:
                if len(sig.parameters) > 0:
                    raise AgentDynamicTraitsFunctionError(
                        f"""The dynamic traits function {self.dynamic_traits_function} has too many parameters. It should have no parameters or 
                        just a single parameter: 'question'."""
                    )

    @property
    def traits(self) -> dict[str, str]:
        """An agent's traits, which is a dictionary.

        The agent could have a a dynamic traits function (`dynamic_traits_function`) that returns a dictionary of traits
        when called. This function can also take a `question` as an argument.
        If so, the dynamic traits function is called and the result is returned.
        Otherwise, the traits are returned.

        Example:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}

        """
        if self.has_dynamic_traits_function:
            sig = inspect.signature(self.dynamic_traits_function)
            if "question" in sig.parameters:
                return self.dynamic_traits_function(question=self.current_question)
            else:
                return self.dynamic_traits_function()
        else:
            return dict(self._traits)

    @contextmanager
    def modify_traits_context(self):
        self._check_before_modifying_traits()
        try:
            yield
        finally:
            self._traits = AgentTraits(self._traits)

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

    def _get_invigilator_class(self, question: QuestionBase) -> Type[InvigilatorBase]:
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
            from ..data import Cache

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

    def __add__(self, other_agent: Optional[Agent] = None) -> Agent:
        """
        Combine two agents by joining their traits.

        The agents must not have overlapping traits.

        Example usage:

        >>> a1 = Agent(traits = {"age": 10})
        >>> a2 = Agent(traits = {"height": 5.5})
        >>> a1 + a2
        Agent(traits = {'age': 10, 'height': 5.5})
        >>> a1 + a1
        Traceback (most recent call last):
        ...
        edsl.agents.exceptions.AgentCombinationError: The agents have overlapping traits: {'age'}.
        ...
        >>> a1 = Agent(traits = {"age": 10}, codebook = {"age": "Their age is"})
        >>> a2 = Agent(traits = {"height": 5.5}, codebook = {"height": "Their height is"})
        >>> a1 + a2
        Agent(traits = {'age': 10, 'height': 5.5}, codebook = {'age': 'Their age is', 'height': 'Their height is'})
        """
        if other_agent is None:
            return self
        elif common_traits := set(self.traits.keys()) & set(other_agent.traits.keys()):
            raise AgentCombinationError(
                f"The agents have overlapping traits: {common_traits}."
            )
        else:
            new_codebook = copy.deepcopy(self.codebook) | copy.deepcopy(
                other_agent.codebook
            )
            d = self.traits | other_agent.traits
            newagent = self.duplicate()
            newagent.traits = d
            newagent.codebook = new_codebook
            return newagent

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
        if self.name == None:
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
                and raw_data.get("answer_question_directly_source_code", None) != None
            ):
                raw_data["answer_question_directly_source_code"] = inspect.getsource(
                    answer_question_directly_func
                )
                raw_data["answer_question_directly_function_name"] = (
                    self.answer_question_directly_function_name
                )
        raw_data["traits"] = dict(raw_data["traits"])

        return raw_data

    def __hash__(self) -> int:
        """Return a hash of the agent.

        >>> hash(Agent.example())
        2067581884874391607
        """
        return dict_hash(self.to_dict(add_edsl_version=False))

    def to_dict(self, add_edsl_version=True) -> dict[str, Union[dict, bool]]:
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
        if self.set_instructions:
            d["instruction"] = self.instruction
        if self.set_traits_presentation_template:
            d["traits_presentation_template"] = self.traits_presentation_template
        if self.codebook:
            d["codebook"] = self.codebook
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
            return cls(
                traits=agent_dict["traits"],
                name=agent_dict.get("name", None),
                instruction=agent_dict.get("instruction", None),
                traits_presentation_template=agent_dict.get(
                    "traits_presentation_template", None
                ),
                codebook=agent_dict.get("codebook", None),
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
    agent = Agent(traits={"age": 10}) + Agent(traits={"height": 5.5})
    agent.traits
    # Agent -> Job using the to() method
    agent = Agent(traits={"allergies": "peanut"})
    question = QuestionMultipleChoice(
        question_text="Would you enjoy a PB&J?",
        question_options=["Yes", "No"],
        question_name="food_preference",
    )
    job = question.by(agent)
    results = job.run()


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
