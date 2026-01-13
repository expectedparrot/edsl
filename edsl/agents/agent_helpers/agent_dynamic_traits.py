"""Agent dynamic traits functionality.

This module provides the AgentDynamicTraits class that manages dynamic traits
functionality for Agent instances, including initialization, validation, and
execution of dynamic traits functions.
"""

from __future__ import annotations
import inspect
from typing import Optional, Callable, Any, TYPE_CHECKING
from contextlib import contextmanager

from edsl.utilities import create_restricted_function

if TYPE_CHECKING:
    from ..agent import Agent


class AgentDynamicTraits:
    """Manages dynamic traits functionality for an Agent instance.

    This class provides methods to initialize, validate, and execute dynamic traits
    functions that allow agents to generate traits dynamically based on questions
    or other context. Each Agent instance has its own manager.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the dynamic traits manager for an agent.

        Args:
            agent: The agent instance this manager will handle
        """
        self.agent = agent
        self.function: Optional[Callable] = None
        self.function_name: str = ""
        self.has_function: bool = False

    def initialize_from_function(
        self,
        dynamic_traits_function: Optional[Callable],
        dynamic_traits_function_source_code: Optional[str] = None,
        dynamic_traits_function_name: Optional[str] = None,
    ) -> None:
        """Initialize a function that can dynamically modify agent traits based on questions.

        This allows traits to change based on the question being asked, enabling
        more sophisticated agent behaviors. The function can be provided directly
        or as source code that will be compiled.

        Args:
            dynamic_traits_function: Function object that returns a dictionary of traits
            dynamic_traits_function_source_code: Source code string for the function
            dynamic_traits_function_name: Name to assign to the function

        Examples:
            Initialize with a function object:

            >>> from edsl.agents import Agent
            >>> def dynamic_func():
            ...     return {'age': 25, 'mood': 'dynamic'}
            >>> agent = Agent(traits={'age': 30})
            >>> agent.dynamic_traits.initialize_from_function(dynamic_func)
            >>> agent.dynamic_traits.has_function
            True

            Initialize with source code:

            >>> agent2 = Agent(traits={'age': 30})
            >>> code = 'def age_func(): return {"age": 40}'
            >>> agent2.dynamic_traits.initialize_from_function(None, code, 'age_func')
            >>> agent2.dynamic_traits.has_function
            True

            No initialization if no function provided:

            >>> agent3 = Agent(traits={'age': 30})
            >>> agent3.dynamic_traits.initialize_from_function(None, None, None)
            >>> agent3.dynamic_traits.has_function
            False
        """
        # Handle direct function object
        self.function = dynamic_traits_function

        if self.function:
            self.function_name = self.function.__name__
            self.has_function = True
        else:
            self.has_function = False

        # Handle source code compilation
        if dynamic_traits_function_source_code:
            self.function_name = dynamic_traits_function_name or "dynamic_traits"
            self.function = create_restricted_function(
                self.function_name, dynamic_traits_function_source_code
            )
            self.has_function = True

    def validate_function(self) -> None:
        """Validate that the dynamic traits function has the correct signature.

        This method checks if the dynamic traits function (if present) has the correct
        parameter list. The function should either take no parameters or a single
        parameter named 'question'.

        Raises:
            AgentDynamicTraitsFunctionError: If the function signature is invalid

        Examples:
            Valid function with 'question' parameter:

            >>> from edsl.agents import Agent
            >>> def f(question):
            ...     return {"age": 10, "hair": "brown", "height": 5.5}
            >>> agent = Agent(traits={'age': 30})
            >>> agent.dynamic_traits.initialize_from_function(f)
            >>> agent.dynamic_traits.validate_function()

            Valid function with no parameters:

            >>> def g():
            ...     return {"age": 20}
            >>> agent.dynamic_traits.initialize_from_function(g)
            >>> agent.dynamic_traits.validate_function()

            Invalid function with extra parameters:

            >>> def bad_func(question, extra):
            ...     return {"age": 10}
            >>> agent.dynamic_traits.initialize_from_function(bad_func)
            >>> try:
            ...     agent.dynamic_traits.validate_function()
            ... except Exception as e:
            ...     print(f"Error: {type(e).__name__}")
            Error: AgentDynamicTraitsFunctionError
        """
        from ..exceptions import AgentDynamicTraitsFunctionError

        if self.has_function:
            sig = inspect.signature(self.function)

            if "question" in sig.parameters:
                # If it has 'question' parameter, it should be the only one
                if len(sig.parameters) > 1:
                    raise AgentDynamicTraitsFunctionError(
                        message=f"The dynamic traits function {self.function} has too many parameters. It should only have one parameter: 'question'."
                    )
            else:
                # If it doesn't have 'question', it shouldn't have any parameters
                if len(sig.parameters) > 0:
                    raise AgentDynamicTraitsFunctionError(
                        f"The dynamic traits function {self.function} has too many parameters. It should have no parameters or just a single parameter: 'question'."
                    )

    def get_traits(self, current_question: Any = None) -> dict[str, Any]:
        """Get traits using the dynamic traits function if available.

        This method calls the dynamic traits function to generate traits based on the
        current question context, or returns the stored traits if no dynamic function
        is available.

        Args:
            current_question: The current question context for dynamic generation

        Returns:
            Dictionary of agent traits (key-value pairs)

        Examples:
            Get traits with no dynamic function:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30, "hair": "brown"})
            >>> agent.dynamic_traits.get_traits()
            {'age': 30, 'hair': 'brown'}

            Get traits with dynamic function (no question parameter):

            >>> def static_func():
            ...     return {"age": 25, "dynamic": True}
            >>> agent.dynamic_traits.initialize_from_function(static_func)
            >>> agent.dynamic_traits.get_traits()
            {'age': 25, 'dynamic': True}

            Get traits with dynamic function (question parameter):

            >>> def question_func(question):
            ...     base = {"age": 30}
            ...     if question and hasattr(question, 'question_name'):
            ...         base["context"] = question.question_name
            ...     return base
            >>> agent.dynamic_traits.initialize_from_function(question_func)
            >>> agent.dynamic_traits.get_traits()
            {'age': 30}
        """
        if self.has_function:
            try:
                # Check if the function expects a question parameter
                sig = inspect.signature(self.function)

                if "question" in sig.parameters:
                    # Call with the current question
                    return self.function(question=current_question)
                else:
                    # Call without parameters
                    return self.function()
            except Exception:
                # If the dynamic function fails, fall back to stored traits
                # This maintains backward compatibility and prevents property lookup failures
                return self.agent._traits
        else:
            # Return the stored traits from the agent
            return self.agent._traits

    def check_before_modifying_traits(self) -> None:
        """Check if traits can be modified (no dynamic function present).

        Raises:
            AgentErrors: If the agent has a dynamic traits function.

        Examples:
            Allow modification when no dynamic function:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 10})
            >>> agent.dynamic_traits.check_before_modifying_traits()  # Should not raise

            Prevent modification when dynamic function exists:

            >>> def f():
            ...     return {"age": 20}
            >>> agent.dynamic_traits.initialize_from_function(f)
            >>> try:
            ...     agent.dynamic_traits.check_before_modifying_traits()
            ... except Exception as e:
            ...     print(f"Error: {type(e).__name__}")
            Error: AgentErrors
        """
        from ..exceptions import AgentErrors

        if self.has_function:
            raise AgentErrors(
                "You cannot modify the traits of an agent that has a dynamic traits function. "
                "If you want to modify the traits, you should remove the dynamic traits function."
            )

    @contextmanager
    def modify_traits_context(self):
        """Context manager for modifying traits safely.

        Ensures traits can be modified and properly wrapped after modification.

        Yields:
            None

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> with agent.dynamic_traits.modify_traits_context():
            ...     agent._traits = {'age': 31}
            >>> agent.traits['age']
            31
        """
        from .agent_traits import AgentTraits

        self.check_before_modifying_traits()
        try:
            yield
        finally:
            # re-wrap the possibly mutated mapping so future writes remain guarded
            self.agent._traits = AgentTraits(
                dict(self.agent._traits), parent=self.agent
            )

    def transfer_to(self, target_agent: "Agent") -> None:
        """Transfer the dynamic traits function to another agent.

        This method is used during agent duplication to preserve dynamic traits
        functionality in the new agent instance.

        Args:
            target_agent: The agent to copy the function to

        Examples:
            Transfer function during duplication:

            >>> from edsl.agents import Agent
            >>> source = Agent(traits={'age': 30})
            >>> def dynamic_func():
            ...     return {"age": 25, "transferred": True}
            >>> source.dynamic_traits.initialize_from_function(dynamic_func)
            >>>
            >>> target = Agent(traits={'age': 35})
            >>> source.dynamic_traits.transfer_to(target)
            >>> target.dynamic_traits.has_function
            True
            >>> target.dynamic_traits.get_traits()
            {'age': 25, 'transferred': True}

            No effect if source has no function:

            >>> source2 = Agent(traits={'age': 40})
            >>> target2 = Agent(traits={'age': 45})
            >>> source2.dynamic_traits.transfer_to(target2)
            >>> target2.dynamic_traits.has_function
            False
        """
        if self.has_function:
            target_agent.dynamic_traits.function = self.function
            target_agent.dynamic_traits.function_name = self.function_name
            target_agent.dynamic_traits.has_function = True

    def remove_function(self) -> None:
        """Remove the dynamic traits function from the agent.

        This method removes any existing dynamic traits function, causing the agent
        to fall back to using stored traits.

        Examples:
            Remove an existing dynamic function:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> def dynamic_func():
            ...     return {"age": 25}
            >>> agent.dynamic_traits.initialize_from_function(dynamic_func)
            >>> agent.dynamic_traits.has_function
            True
            >>> agent.dynamic_traits.remove_function()
            >>> agent.dynamic_traits.has_function
            False

            Safe to call even if no function exists:

            >>> agent2 = Agent(traits={'age': 35})
            >>> agent2.dynamic_traits.remove_function()  # No error
        """
        self.function = None
        self.function_name = ""
        self.has_function = False

    def get_function(self) -> Optional[Callable]:
        """Get the dynamic traits function if it exists.

        Returns:
            The dynamic traits function if it exists, None otherwise

        Examples:
            Get the function:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent.dynamic_traits.get_function() is None
            True
            >>> def dynamic_func():
            ...     return {"age": 25}
            >>> agent.dynamic_traits.initialize_from_function(dynamic_func)
            >>> func = agent.dynamic_traits.get_function()
            >>> func is not None
            True
        """
        return self.function

    def __repr__(self) -> str:
        """Return a string representation of the manager.

        Returns:
            String representation showing the manager and whether it has a function
        """
        has_func = self.has_function
        func_info = (
            f"with function '{self.function_name}'" if has_func else "no function"
        )
        return f"AgentDynamicTraits(agent={self.agent.name or 'unnamed'}, {func_info})"
