"""Unified agent traits management functionality.

This module provides the AgentTraitsManager class that handles all trait-related
operations for Agent instances, including static traits, dynamic traits, codebooks,
context management, and guarding logic.
"""

from __future__ import annotations
import inspect
from typing import Union, Optional, Any, Callable, TYPE_CHECKING
from contextlib import contextmanager

from ..utilities import sanitize_jinja_syntax, create_restricted_function
from .exceptions import AgentErrors, AgentDynamicTraitsFunctionError

if TYPE_CHECKING:
    from .agent import Agent
    from ..utilities.similarity_rank import RankableItems


class AgentTraitsManager:
    """Unified manager for all trait-related operations on an Agent instance.

    This class provides comprehensive trait management including:
    - Static trait operations (add, remove, translate, search)
    - Dynamic traits functionality
    - Codebook management
    - Context management for safe trait modification
    - Validation and guarding logic

    Each Agent instance has its own unified traits manager.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the unified traits manager for an agent.

        Args:
            agent: The agent instance this manager will handle
        """
        self.agent = agent

        # Dynamic traits functionality
        self.dynamic_function: Optional[Callable] = None
        self.dynamic_function_name: str = ""
        self.has_dynamic_function: bool = False

    # ========== INITIALIZATION ==========

    def initialize(self, traits: Optional[dict], codebook: Optional[dict]) -> None:
        """Initialize the agent's traits and codebook.

        This method sets up the agent's traits and codebook, including sanitization
        for Jinja2 syntax and proper wrapping of traits in the AgentTraits class.

        Args:
            traits: Dictionary of agent characteristics
            codebook: Dictionary mapping trait keys to descriptions

        Examples:
            Initialize with traits and codebook:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={})  # Start with empty agent
            >>> agent.traits_manager.initialize({'age': 30}, {'age': 'Age in years'})
            >>> agent.traits['age']
            30
            >>> agent.codebook['age']
            'Age in years'

            Initialize with empty values:

            >>> agent2 = Agent(traits={})  # Start with empty agent
            >>> agent2.traits_manager.initialize(None, None)
            >>> agent2.traits
            {}
            >>> agent2.codebook
            {}
        """
        from .agent_traits import AgentTraits

        # Sanitize traits and codebook for Jinja2 syntax
        if traits:
            traits = sanitize_jinja_syntax(traits, "traits")
        if codebook:
            codebook = sanitize_jinja_syntax(codebook, "codebook")

        self.agent._traits = AgentTraits(traits or {}, parent=self.agent)
        self.agent.codebook = codebook or dict()

    # ========== DYNAMIC TRAITS ==========

    def initialize_dynamic_function(
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
            >>> from edsl.agents import Agent
            >>> def dynamic_func(): return {'age': 25}
            >>> agent = Agent(traits={'age': 30})
            >>> agent.traits_manager.initialize_dynamic_function(dynamic_func)
            >>> agent.traits_manager.has_dynamic_function
            True
        """
        if dynamic_traits_function is not None:
            self.dynamic_function = dynamic_traits_function
            self.dynamic_function_name = getattr(
                dynamic_traits_function, "__name__", "dynamic_traits_function"
            )
            self.has_dynamic_function = True
        elif dynamic_traits_function_source_code is not None:
            self._initialize_from_source_code(
                dynamic_traits_function_source_code, dynamic_traits_function_name
            )

    def _initialize_from_source_code(
        self, source_code: str, function_name: Optional[str]
    ) -> None:
        """Initialize dynamic traits function from source code."""
        try:
            func_name = function_name or "dynamic_traits_function"
            func = create_restricted_function(func_name, source_code)
            self.dynamic_function = func
            self.dynamic_function_name = func_name
            self.has_dynamic_function = True
        except Exception as e:
            raise AgentDynamicTraitsFunctionError(
                f"Error creating dynamic traits function: {e}"
            )

    def get_traits(self, current_question=None) -> dict[str, Any]:
        """Get the agent's traits, potentially using dynamic generation.

        This method provides access to the agent's traits, either from the stored
        traits dictionary or by calling a dynamic traits function if one is defined.

        When no dynamic function is present, returns the actual AgentTraits object
        to support direct mutation (e.g., traits.update()). When a dynamic function
        is present, returns a new dict from the function.

        Args:
            current_question: The current question context for dynamic trait generation

        Returns:
            dict: Dictionary of agent traits (key-value pairs), or the AgentTraits
            object itself when no dynamic function is present

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent.traits_manager.get_traits()
            {'age': 30}
        """
        if self.has_dynamic_function and self.dynamic_function:
            try:
                # Check if the function expects a question parameter
                sig = inspect.signature(self.dynamic_function)

                if "question" in sig.parameters:
                    # Call with the current question
                    return self.dynamic_function(question=current_question)
                else:
                    # Call without parameters
                    return self.dynamic_function()
            except Exception:
                # If the dynamic function fails, fall back to stored traits
                # This maintains backward compatibility and prevents property lookup failures
                return self.agent._traits
        else:
            # Return the actual AgentTraits object to support direct mutation
            return self.agent._traits

    def validate_dynamic_function(self) -> None:
        """Validate the dynamic traits function if one exists.

        This method checks if the dynamic traits function (if present) has the correct
        parameter list. The function should either take no parameters or a single
        parameter named 'question'.

        Raises:
            AgentDynamicTraitsFunctionError: If the function signature is invalid
        """
        if self.has_dynamic_function and self.dynamic_function:
            sig = inspect.signature(self.dynamic_function)

            if "question" in sig.parameters:
                # If it has 'question' parameter, it should be the only one
                if len(sig.parameters) > 1:
                    raise AgentDynamicTraitsFunctionError(
                        f"The dynamic traits function {self.dynamic_function} has too many parameters. It should only have one parameter: 'question'."
                    )
            else:
                # If it doesn't have 'question', it shouldn't have any parameters
                if len(sig.parameters) > 0:
                    raise AgentDynamicTraitsFunctionError(
                        f"The dynamic traits function {self.dynamic_function} has too many parameters. It should have no parameters or just a single parameter: 'question'."
                    )

    # ========== CONTEXT MANAGEMENT & GUARDING ==========

    def check_before_modifying_traits(self) -> None:
        """Check if traits can be modified safely.

        Raises:
            AgentErrors: If the agent has a dynamic traits function that prevents modification
        """
        if self.has_dynamic_function:
            raise AgentErrors(
                "Cannot modify traits directly when agent has a dynamic traits function. "
                "The traits are generated dynamically and modifications would be overridden."
            )

    @contextmanager
    def modify_traits_context(self):
        """Context manager for modifying traits safely.

        Ensures traits are properly wrapped after modification and validates
        that modification is allowed.

        Yields:
            None

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> with agent.traits_manager.modify_traits_context():
            ...     agent._traits = {'age': 31}
            >>> agent.traits['age']
            31
        """
        self.check_before_modifying_traits()
        try:
            yield
        finally:
            # re-wrap the possibly mutated mapping so future writes remain guarded
            from .agent_traits import AgentTraits

            self.agent._traits = AgentTraits(
                dict(self.agent._traits), parent=self.agent
            )

    def set_traits_safely(self, new_traits: dict[str, Any]) -> None:
        """Set traits using the safe context manager.

        Args:
            new_traits: Dictionary of new traits to set

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent.traits_manager.set_traits_safely({'age': 31, 'height': 5.5})
            >>> agent.traits
            {'age': 31, 'height': 5.5}
        """
        with self.modify_traits_context():
            self.agent._traits = new_traits

    # ========== TRAIT OPERATIONS ==========

    def add_trait(
        self,
        trait_name_or_dict: Union[str, dict[str, Any]],
        value: Optional[Any] = None,
    ) -> "Agent":
        """Add a trait to the agent and return a new agent.

        Args:
            trait_name_or_dict: Either a trait name string or a dictionary of traits
            value: The trait value if trait_name_or_dict is a string

        Returns:
            A new Agent instance with the added trait(s)

        Raises:
            AgentErrors: If both a dictionary and a value are provided

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> new_agent = agent.traits_manager.add_trait('height', 5.5)
            >>> new_agent.traits
            {'age': 30, 'height': 5.5}
        """
        if isinstance(trait_name_or_dict, dict) and value is not None:
            raise AgentErrors("Cannot provide both a dictionary and a value")

        new_agent = self.agent.duplicate()

        if isinstance(trait_name_or_dict, dict):
            new_traits = dict(new_agent.traits)
            new_traits.update(trait_name_or_dict)
        else:
            new_traits = dict(new_agent.traits)
            new_traits[trait_name_or_dict] = value

        new_agent.traits_manager.set_traits_safely(new_traits)
        return new_agent

    def remove_trait(self, trait: str) -> "Agent":
        """Remove a trait from the agent.

        Args:
            trait: The name of the trait to remove

        Returns:
            A new Agent instance without the specified trait

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': 5.5})
            >>> new_agent = agent.traits_manager.remove_trait('age')
            >>> new_agent.traits
            {'height': 5.5}
        """
        new_agent = self.agent.duplicate()
        new_traits = dict(new_agent.traits)
        if trait in new_traits:
            del new_traits[trait]
        new_agent.traits_manager.set_traits_safely(new_traits)
        return new_agent

    def update_trait(self, trait_name: str, value: Any) -> "Agent":
        """Update an existing trait value.

        This method modifies the value of an existing trait. If the trait
        doesn't exist, it raises an AgentErrors exception.

        Args:
            trait_name: The name of the trait to update
            value: The new value for the trait

        Returns:
            A new Agent instance with the updated trait value

        Raises:
            AgentErrors: If the trait doesn't exist

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': 5.5})
            >>> new_agent = agent.traits_manager.update_trait('age', 31)
            >>> new_agent.traits
            {'age': 31, 'height': 5.5}

            Updating a non-existent trait raises an error:

            >>> agent.traits_manager.update_trait('weight', 150)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentErrors: ...
        """
        if trait_name not in self.agent.traits:
            raise AgentErrors(
                f"Cannot update trait '{trait_name}': trait does not exist. "
                f"Available traits: {list(self.agent.traits.keys())}. "
                f"Use add_trait() to add new traits."
            )

        new_agent = self.agent.duplicate()
        new_traits = dict(new_agent.traits)
        new_traits[trait_name] = value
        new_agent.traits_manager.set_traits_safely(new_traits)
        return new_agent

    def set_all_traits(self, new_traits: dict[str, Any]) -> None:
        """Set all traits, replacing existing ones.

        Args:
            new_traits: Dictionary of new traits

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent.traits_manager.set_all_traits({'height': 5.5, 'weight': 150})
            >>> agent.traits
            {'height': 5.5, 'weight': 150}
        """
        self.set_traits_safely(new_traits)

    def drop_trait_if(self, bad_value: Any) -> "Agent":
        """Drop traits that have a specific bad value.

        Args:
            bad_value: The value to remove from traits

        Returns:
            A new Agent instance with the bad value traits removed

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': None, 'weight': 150})
            >>> clean_agent = agent.traits_manager.drop_trait_if(None)
            >>> clean_agent.traits
            {'age': 30, 'weight': 150}
        """
        new_agent = self.agent.duplicate()
        new_traits = {k: v for k, v in new_agent.traits.items() if v != bad_value}
        new_agent.traits_manager.set_traits_safely(new_traits)
        return new_agent

    def translate_traits(self, values_codebook: dict[str, dict[Any, Any]]) -> "Agent":
        """Translate traits to a new codebook.

        Args:
            values_codebook: Dictionary mapping trait names to value translation dictionaries

        Returns:
            A new Agent instance with translated trait values

        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'hair': 1, 'eyes': 2})
            >>> translation = {'hair': {1: 'brown'}, 'eyes': {2: 'blue'}}
            >>> new_agent = agent.traits_manager.translate_traits(translation)
            >>> new_agent.traits
            {'hair': 'brown', 'eyes': 'blue'}
        """
        new_agent = self.agent.duplicate()
        new_traits = dict(new_agent.traits)

        for trait_name, translation_dict in values_codebook.items():
            if trait_name in new_traits:
                old_value = new_traits[trait_name]
                if old_value in translation_dict:
                    new_traits[trait_name] = translation_dict[old_value]

        new_agent.traits_manager.set_traits_safely(new_traits)
        return new_agent

    # ========== SEARCH ==========

    def search_traits(self, search_string: str) -> "RankableItems":
        """Search the agent's traits for a string.

        This method searches through the agent's trait descriptions (using codebook
        descriptions when available) and returns ranked matches based on similarity
        to the search string.

        Args:
            search_string: The string to search for in trait descriptions

        Returns:
            A ScenarioList containing ranked trait matches with description,
            trait_name, and similarity score

        Examples:
            Search traits with codebook descriptions:

            >>> from edsl.agents import Agent
            >>> codebook = {"age": "How old the person is", "occupation": "Their job"}
            >>> agent = Agent(traits={"age": 30, "occupation": "doctor"}, codebook=codebook)
            >>> results = agent.traits_manager.search_traits("job")
            >>> len(results) >= 1
            True
            >>> results[0]["trait_name"] == "occupation"
            True
            >>> results[0]["score"] > 0.5
            True

            Search traits without codebook:

            >>> agent2 = Agent(traits={"height": 5.5, "weight": 150})
            >>> results2 = agent2.traits_manager.search_traits("height")
            >>> len(results2) >= 1
            True
            >>> results2[0]["trait_name"] == "height"
            True
            >>> results2[0]["score"] == 1.0
            True
        """
        from ..scenarios import ScenarioList, Scenario

        # Create list of trait information for searching
        trait_info = []
        for trait_name, trait_value in self.agent.traits.items():
            if trait_name in self.agent.codebook:
                description = self.agent.codebook[trait_name]
            else:
                description = trait_name
            trait_info.append((trait_name, description, trait_value))

        # Simple string matching - prioritize exact matches, then substring matches
        search_lower = search_string.lower()
        exact_matches = []
        partial_matches = []

        for trait_name, description, trait_value in trait_info:
            # Check if search string matches trait name or description
            if (
                search_lower == trait_name.lower()
                or search_lower == description.lower()
            ):
                exact_matches.append((trait_name, description, 1.0))  # Perfect match
            elif (
                search_lower in trait_name.lower()
                or search_lower in description.lower()
                or search_lower in str(trait_value).lower()
            ):
                # Calculate simple similarity based on substring match
                name_match = search_lower in trait_name.lower()
                desc_match = search_lower in description.lower()

                # Higher score for name/description matches than value matches
                score = 0.8 if name_match or desc_match else 0.5
                partial_matches.append((trait_name, description, score))

        # Combine results, exact matches first
        all_matches = exact_matches + sorted(
            partial_matches, key=lambda x: x[2], reverse=True
        )

        # If no matches found, return all traits with low scores
        if not all_matches:
            all_matches = [
                (trait_name, description, 0.1)
                for trait_name, description, _ in trait_info
            ]

        # Create scenario list with results
        sl = ScenarioList([])
        for trait_name, description, score in all_matches:
            sl.append(
                Scenario(
                    {
                        "description": description,
                        "trait_name": trait_name,
                        "score": score,
                    }
                )
            )
        return sl

    # ========== TRANSFER METHODS (for duplication) ==========

    def transfer_to(self, new_agent: "Agent") -> None:
        """Transfer dynamic traits function to a new agent.

        Args:
            new_agent: The agent to transfer the function to
        """
        if self.has_dynamic_function:
            new_agent.traits_manager.dynamic_function = self.dynamic_function
            new_agent.traits_manager.dynamic_function_name = self.dynamic_function_name
            new_agent.traits_manager.has_dynamic_function = True

    # ========== BACKWARD COMPATIBILITY ALIASES ==========
    # These methods provide compatibility with the old AgentDynamicTraits interface

    def initialize_from_function(
        self,
        dynamic_traits_function: Optional[Callable],
        dynamic_traits_function_source_code: Optional[str] = None,
        dynamic_traits_function_name: Optional[str] = None,
    ) -> None:
        """Backward compatibility alias for initialize_dynamic_function."""
        self.initialize_dynamic_function(
            dynamic_traits_function,
            dynamic_traits_function_source_code,
            dynamic_traits_function_name,
        )

    def validate_function(self) -> None:
        """Backward compatibility alias for validate_dynamic_function."""
        self.validate_dynamic_function()

    def get_function(self) -> Optional[Callable]:
        """Get the dynamic traits function if one exists.

        Returns:
            The dynamic traits function if it exists, None otherwise

        Examples:
            Get the function:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30})
            >>> agent.dynamic_traits.get_function() is None
            True
        """
        return self.dynamic_function

    def remove_function(self) -> None:
        """Remove the dynamic traits function.

        This clears the dynamic function, causing the agent to fall back
        to using stored traits.

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
        """
        self.dynamic_function = None
        self.dynamic_function_name = ""
        self.has_dynamic_function = False

    # Additional backward compatibility properties
    @property
    def has_function(self) -> bool:
        """Backward compatibility alias for has_dynamic_function."""
        return self.has_dynamic_function

    @property
    def function(self) -> Optional[Callable]:
        """Backward compatibility alias for dynamic_function."""
        return self.dynamic_function

    @property
    def function_name(self) -> str:
        """Backward compatibility alias for dynamic_function_name."""
        return self.dynamic_function_name
