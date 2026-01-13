"""Agent invigilator and question answering functionality.

This module provides the AgentInvigilator class that manages invigilator creation
and question answering functionality for Agent instances, including creating the
appropriate invigilator type and handling question answering workflows.
"""

from __future__ import annotations
from typing import Optional, Type, TYPE_CHECKING

from edsl.utilities import sync_wrapper

if TYPE_CHECKING:
    from ..agent import Agent
    from edsl.questions import QuestionBase
    from edsl.scenarios import Scenario
    from edsl.surveys import Survey
    from edsl.language_models import LanguageModel
    from edsl.surveys.memory import MemoryPlan
    from edsl.caching import Cache
    from edsl.key_management import KeyLookup
    from edsl.invigilators import InvigilatorBase
    from edsl.data_transfer_models import AgentResponseDict


class AgentInvigilator:
    """Manages invigilator creation and question answering for an Agent instance.

    This class provides methods to create appropriate invigilators based on question
    and agent types, and handles the complete question answering workflow including
    async and sync variants.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the invigilator manager for an agent.

        Args:
            agent: The agent instance this manager will handle
        """
        self.agent = agent

    def get_invigilator_class(
        self, question: "QuestionBase"
    ) -> Type["InvigilatorBase"]:
        """Get the invigilator class for a question.

        This method returns the invigilator class that should be used to answer a question.
        The invigilator class is determined by the type of question and the type of agent.

        Args:
            question: The question to determine the invigilator class for.

        Returns:
            Type[InvigilatorBase]: The appropriate invigilator class.

        Examples:
            >>> from edsl.agents import Agent
            >>> from edsl.questions import QuestionFreeText
            >>> agent = Agent(traits={"age": 10})
            >>> q = QuestionFreeText(question_name="test", question_text="Test")
            >>> invigilator_class = agent.invigilator.get_invigilator_class(q)
            >>> invigilator_class.__name__
            'InvigilatorAI'

            >>> # Agent with direct answering gets InvigilatorHuman
            >>> def answer_func(self, question, scenario):
            ...     return "Direct answer"
            >>> agent.direct_answering.add_method(answer_func)
            >>> invigilator_class = agent.invigilator.get_invigilator_class(q)
            >>> invigilator_class.__name__
            'InvigilatorHuman'
        """
        from edsl.invigilators import (
            InvigilatorHuman,
            InvigilatorFunctional,
            InvigilatorAI,
        )

        if hasattr(question, "answer_question_directly"):
            return InvigilatorFunctional
        elif hasattr(self.agent, "answer_question_directly"):
            return InvigilatorHuman
        else:
            return InvigilatorAI

    def create_invigilator(
        self,
        question: "QuestionBase",
        cache: Optional["Cache"] = None,
        scenario: Optional["Scenario"] = None,
        model: Optional["LanguageModel"] = None,
        survey: Optional["Survey"] = None,
        memory_plan: Optional["MemoryPlan"] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        raise_validation_errors: bool = True,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> "InvigilatorBase":
        """Create an Invigilator for handling question answering.

        Args:
            question: The question to be asked
            cache: The cache for storing responses
            scenario: The scenario context
            model: The language model to use
            survey: The survey context
            memory_plan: The memory plan to use
            current_answers: The current answers
            iteration: The iteration number
            raise_validation_errors: Whether to raise validation errors
            key_lookup: The key lookup for API credentials

        Returns:
            An InvigilatorBase instance for handling the question

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={})
            >>> inv = agent.invigilator.create_invigilator(question=None, cache=False)
            >>> type(inv).__name__
            'InvigilatorAI'
        """
        from edsl.language_models import Model
        from edsl.scenarios import Scenario

        model = model or Model()
        scenario = scenario or Scenario()

        if cache is None:
            from edsl.caching import Cache

            cache = Cache()

        invigilator_class = self.get_invigilator_class(question)

        invigilator = invigilator_class(
            self.agent,
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

    def create_invigilator_with_context(
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
        """Create an Invigilator with full context setup.

        This method handles the complete invigilator creation process including
        setting the current question context and transferring response validation
        settings to the invigilator.

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

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={})
            >>> inv = agent.invigilator.create_invigilator_with_context(question=None, cache=False)
            >>> type(inv).__name__
            'InvigilatorAI'

        Note:
            An invigilator is an object that is responsible for administering a question to an agent and
            recording the responses.
        """
        from edsl.language_models import Model
        from edsl.scenarios import Scenario

        # Set the current question context
        self.agent.current_question = question
        model = model or Model()
        scenario = scenario or Scenario()

        invigilator = self.create_invigilator(
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

        # Transfer response validation settings if they exist
        if hasattr(self.agent, "validate_response"):
            invigilator.validate_response = self.agent.validate_response
        if hasattr(self.agent, "translate_response"):
            invigilator.translate_response = self.agent.translate_response

        return invigilator

    async def async_answer_question(
        self,
        *,
        question: "QuestionBase",
        cache: "Cache",
        scenario: Optional["Scenario"] = None,
        survey: Optional["Survey"] = None,
        model: Optional["LanguageModel"] = None,
        debug: bool = False,
        memory_plan: Optional["MemoryPlan"] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> "AgentResponseDict":
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

        Examples:
            >>> from edsl.agents import Agent
            >>> from edsl.questions import QuestionFreeText
            >>> agent = Agent(traits={})
            >>> def answer_func(self, question, scenario):
            ...     return "I am a direct answer."
            >>> agent.direct_answering.add_method(answer_func)
            >>> q = QuestionFreeText.example()
            >>> # result = await agent.invigilator.async_answer_question(question=q, cache=False)
            >>> # result.answer would be 'I am a direct answer.'

        Note:
            This is a function where an agent returns an answer to a particular question.
            However, there are several different ways an agent can answer a question, so the
            actual functionality is delegated to an InvigilatorBase object.
        """
        invigilator = self.create_invigilator_with_context(
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
        response: "AgentResponseDict" = await invigilator.async_answer_question()
        return response

    def answer_question(
        self,
        *,
        question: "QuestionBase",
        cache: "Cache",
        scenario: Optional["Scenario"] = None,
        survey: Optional["Survey"] = None,
        model: Optional["LanguageModel"] = None,
        debug: bool = False,
        memory_plan: Optional["MemoryPlan"] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> "AgentResponseDict":
        """Answer a posed question synchronously.

        This is a synchronous wrapper around async_answer_question.

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

        Examples:
            >>> from edsl.agents import Agent
            >>> from edsl.questions import QuestionFreeText
            >>> agent = Agent(traits={})
            >>> def answer_func(self, question, scenario):
            ...     return "I am a direct answer."
            >>> agent.direct_answering.add_method(answer_func)
            >>> q = QuestionFreeText.example()
            >>> result = agent.invigilator.answer_question(question=q, cache=False)
            >>> result.answer
            'I am a direct answer.'
        """
        return sync_wrapper(self.async_answer_question)(
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

    def __repr__(self) -> str:
        """Return a string representation of the manager.

        Returns:
            String representation showing the manager and agent
        """
        return f"AgentInvigilator(agent={self.agent.name or 'unnamed'})"
