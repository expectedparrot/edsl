"""Agent direct question answering functionality.

This module provides the AgentDirectAnswering class that manages direct question
answering methods for Agent instances, including initialization, validation, and
management of direct answering functions.

>>> import warnings
>>> warnings.filterwarnings("ignore", message="Warning: overwriting existing answer_question_directly method")
"""

from __future__ import annotations
import types
import inspect
import warnings
from typing import Optional, TYPE_CHECKING

from edsl.utilities import create_restricted_function

if TYPE_CHECKING:
    from ..agent import Agent, DirectAnswerMethod


class AgentDirectAnswering:
    """Manages direct question answering functionality for an Agent instance.

    This class provides methods to add, remove, and initialize direct question
    answering methods that allow agents to answer questions programmatically
    without using language models. Each Agent instance has its own manager.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the direct answering manager for an agent.

        Args:
            agent: The agent instance this manager will handle
        """
        self.agent = agent

    def initialize_from_source_code(
        self,
        answer_question_directly_source_code: Optional[str],
        answer_question_directly_function_name: Optional[str],
    ) -> None:
        """Initialize a method for the agent to directly answer questions without using an LLM.

        This allows creating agents that answer programmatically rather than through
        language model generation. The direct answering method can be provided as
        source code that will be compiled and bound to this agent instance.

        Args:
            answer_question_directly_source_code: Source code for the direct answering method
            answer_question_directly_function_name: Name to assign to the method

        Examples:
            Initialize an agent with direct answering from source code:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> code = 'def answer(self, question, scenario): return "Direct answer"'
            >>> agent.direct_answering.initialize_from_source_code(code, 'answer')
            >>> agent.direct_answering.has_method()
            True

            No initialization if no source code provided:

            >>> agent2 = Agent(traits={'age': 25})
            >>> agent2.direct_answering.initialize_from_source_code(None, None)
            >>> agent2.direct_answering.has_method()
            False
        """
        if answer_question_directly_source_code:
            self.agent.answer_question_directly_function_name = (
                answer_question_directly_function_name
            )
            protected_method = create_restricted_function(
                answer_question_directly_function_name,
                answer_question_directly_source_code,
            )
            bound_method = types.MethodType(protected_method, self.agent)
            setattr(self.agent, "answer_question_directly", bound_method)

    def add_method(
        self,
        method: "DirectAnswerMethod",
        validate_response: bool = False,
        translate_response: bool = False,
    ) -> None:
        """Add a method to the agent that can answer a particular question type.

        This method validates the function signature and binds it to the agent instance
        as a direct answering method. The method will be called instead of using a
        language model for question answering.

        Args:
            method: A method that can answer a question directly
            validate_response: Whether to validate the response
            translate_response: Whether to translate the response

        Raises:
            AgentDirectAnswerFunctionError: If the method signature is invalid

        Examples:
            Add a simple direct answering method:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> def answer_func(self, question, scenario):
            ...     return "I am a direct answer."
            >>> agent.direct_answering.add_method(answer_func)
            >>> agent.answer_question_directly(None, None)
            'I am a direct answer.'

            Method validation ensures proper signature:

            >>> def bad_func(question):  # Missing 'self' and 'scenario'
            ...     return "Bad"
            >>> try:
            ...     import warnings
            ...     with warnings.catch_warnings():
            ...         warnings.simplefilter("ignore", UserWarning)
            ...         agent.direct_answering.add_method(bad_func)
            ... except Exception as e:
            ...     print(f"Error: {type(e).__name__}")
            Error: AgentDirectAnswerFunctionError
        """
        from ..exceptions import AgentDirectAnswerFunctionError

        if self.has_method():
            warnings.warn(
                "Warning: overwriting existing answer_question_directly method",
                UserWarning,
                stacklevel=2,
            )

        self.agent.validate_response = validate_response
        self.agent.translate_response = translate_response

        # Validate method signature
        signature = inspect.signature(method)
        for argument in ["question", "scenario", "self"]:
            if argument not in signature.parameters:
                raise AgentDirectAnswerFunctionError(
                    f"The method {method} does not have a '{argument}' parameter."
                )

        bound_method = types.MethodType(method, self.agent)
        setattr(self.agent, "answer_question_directly", bound_method)
        self.agent.answer_question_directly_function_name = bound_method.__name__

    def remove_method(self) -> None:
        """Remove the direct question answering method from the agent.

        This method removes any existing direct answering method, causing the agent
        to fall back to language model-based answering for future questions.

        Examples:
            Remove an existing direct answering method:

            >>> from edsl.agents import Agent
            >>> agent2 = Agent(traits={'age': 30})
            >>> def answer_func(self, question, scenario):
            ...     return "Direct answer"
            >>> agent2.direct_answering.add_method(answer_func)
            >>> agent2.direct_answering.has_method()
            True
            >>> agent2.direct_answering.remove_method()
            >>> agent2.direct_answering.has_method()
            False

            Safe to call even if no method exists:

            >>> agent2 = Agent(traits={'age': 25})
            >>> agent2.direct_answering.remove_method()  # No error
        """
        if hasattr(self.agent, "answer_question_directly"):
            delattr(self.agent, "answer_question_directly")

    def transfer_to(self, target_agent: "Agent") -> None:
        """Transfer the direct answering method to another agent.

        This method is used during agent duplication to preserve direct answering
        functionality in the new agent instance.

        Args:
            target_agent: The agent to copy the method to

        Examples:
            Transfer method during duplication:

            >>> from edsl.agents import Agent
            >>> source = Agent(traits={'age': 30})
            >>> def answer_func(self, question, scenario):
            ...     return "Transferred answer"
            >>> source.direct_answering.add_method(answer_func)
            >>>
            >>> target = Agent(traits={'age': 25})
            >>> source.direct_answering.transfer_to(target)
            >>> target.answer_question_directly(None, None)
            'Transferred answer'

            No effect if source has no method:

            >>> source2 = Agent(traits={'age': 35})
            >>> target2 = Agent(traits={'age': 40})
            >>> source2.direct_answering.transfer_to(target2)
            >>> target2.direct_answering.has_method()
            False
        """
        if self.has_method():
            answer_question_directly = self.agent.answer_question_directly

            def transferred_method(self, question, scenario):
                return answer_question_directly(question, scenario)

            target_agent.direct_answering.add_method(transferred_method)

    def has_method(self) -> bool:
        """Check if the agent has a direct answering method.

        Returns:
            True if the agent has a direct answering method, False otherwise

        Examples:
            Check for direct answering method:

            >>> from edsl.agents import Agent
            >>> agent4 = Agent(traits={'age': 30})
            >>> agent4.direct_answering.has_method()
            False
            >>> def answer_func(self, question, scenario):
            ...     return "Direct"
            >>> agent4.direct_answering.add_method(answer_func)
            >>> agent4.direct_answering.has_method()
            True
        """
        return hasattr(self.agent, "answer_question_directly")

    def get_method(self):
        """Get the direct answering method if it exists.

        Returns:
            The direct answering method if it exists, None otherwise

        Examples:
            Get the method:

            >>> from edsl.agents import Agent
            >>> agent3 = Agent(traits={'age': 30})
            >>> agent3.direct_answering.get_method() is None
            True
            >>> def answer_func(self, question, scenario):
            ...     return "Direct"
            >>> agent3.direct_answering.add_method(answer_func)
            >>> method = agent3.direct_answering.get_method()
            >>> method is not None
            True
        """
        return getattr(self.agent, "answer_question_directly", None)

    def __repr__(self) -> str:
        """Return a string representation of the manager.

        Returns:
            String representation showing the manager and whether it has a method
        """
        has_method = self.has_method()
        method_info = "with method" if has_method else "no method"
        return (
            f"AgentDirectAnswering(agent={self.agent.name or 'unnamed'}, {method_info})"
        )
