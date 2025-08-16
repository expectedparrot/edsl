"""Agent combination functionality.

This module provides the AgentCombination class that handles merging and combining
Agent instances with different conflict resolution strategies for overlapping traits.
"""

from __future__ import annotations
import copy
from typing import Optional, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent

# Type variable for the Agent class
A = TypeVar("A", bound="Agent")


class AgentCombination:
    """Handles combination and merging of Agent instances.

    This class provides methods to combine agents with different strategies
    for handling trait conflicts, including numeric suffixes, error raising,
    and repeated observation merging.
    """

    @staticmethod
    def add(
        first_agent: A,
        other_agent: Optional[A] = None,
        *,
        conflict_strategy: str = "numeric",
    ) -> A:
        """Combine first_agent with other_agent and return a new Agent.

        Args:
            first_agent: The base agent to merge with
            other_agent: The second agent to merge with first_agent. If None, first_agent is returned unchanged
            conflict_strategy: How to handle overlapping trait names:
                - "numeric" (default): rename conflicting traits from other_agent by appending suffix (_1, _2, ...)
                - "error": raise AgentCombinationError if traits overlap
                - "repeated_observation": merge trait values into lists if codebook entries match

        Returns:
            A new Agent instance containing the merged traits and codebooks

        Raises:
            ValueError: If conflict_strategy is not one of the valid options
            AgentCombinationError: If conflict_strategy is "error" and traits overlap, or if
                "repeated_observation" is used with differing codebook descriptions

        Examples:
            Basic combination with numeric strategy (default):

            >>> from edsl.agents import Agent
            >>> a1 = Agent(traits={'age': 30, 'hair': 'brown'})
            >>> a2 = Agent(traits={'age': 25, 'height': 5.5})
            >>> combined = AgentCombination.add(a1, a2)
            >>> combined.traits
            {'age': 30, 'hair': 'brown', 'age_1': 25, 'height': 5.5}

            Error strategy raises exception on conflicts:

            >>> try:
            ...     AgentCombination.add(a1, a2, conflict_strategy="error")
            ... except Exception as e:
            ...     print(f"Raised: {type(e).__name__}")
            Raised: AgentCombinationError

            Repeated observation merges values into lists:

            >>> combined = AgentCombination.add(a1, a2, conflict_strategy="repeated_observation")
            >>> combined.traits['age']
            [30, 25]
        """
        from .exceptions import AgentCombinationError

        if other_agent is None:
            return first_agent

        if conflict_strategy not in {"numeric", "error", "repeated_observation"}:
            raise ValueError(
                "conflict_strategy must be 'numeric', 'error', or 'repeated_observation', got "
                f"{conflict_strategy!r}"
            )

        # Quick path: raise if user asked for error strategy and there is a clash
        if conflict_strategy == "error":
            common = set(first_agent.traits) & set(other_agent.traits)
            if common:
                raise AgentCombinationError(
                    f"The agents have overlapping traits: {common}."
                )

        # Create new agent based on first agent
        newagent = first_agent.duplicate()

        combined_traits: dict = dict(first_agent.traits)
        combined_codebook: dict = copy.deepcopy(first_agent.codebook)

        def _unique_name(base_name: str, existing_keys: set[str]) -> str:
            """Return base_name or base_name_N to avoid duplicates."""
            if base_name not in existing_keys:
                return base_name

            idx = 1
            while f"{base_name}_{idx}" in existing_keys:
                idx += 1
            return f"{base_name}_{idx}"

        rename_map: dict[str, str] = {}

        # Process traits from other_agent
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
                desc_self = first_agent.codebook.get(key)
                desc_other = other_agent.codebook.get(key)
                if desc_self != desc_other:
                    raise AgentCombinationError(
                        f"Trait conflict on '{key}' with differing codebook descriptions."
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

        # Process codebook from other_agent
        for key, description in other_agent.codebook.items():
            if key in rename_map:
                target_key = rename_map[key]
            elif conflict_strategy == "numeric":
                target_key = _unique_name(key, combined_codebook.keys())
            else:
                target_key = key
            combined_codebook[target_key] = description

        # Handle trait_categories from other_agent
        combined_categories = copy.deepcopy(first_agent.trait_categories)
        for category, trait_list in other_agent.trait_categories.items():
            if category not in combined_categories:
                # New category - map trait names according to rename_map
                mapped_traits = [rename_map.get(trait, trait) for trait in trait_list]
                combined_categories[category] = mapped_traits
            else:
                # Existing category - merge trait lists, mapping names
                existing_traits = set(combined_categories[category])
                for trait in trait_list:
                    mapped_trait = rename_map.get(trait, trait)
                    if mapped_trait not in existing_traits:
                        combined_categories[category].append(mapped_trait)
                        existing_traits.add(mapped_trait)

        # Apply the combined data to the new agent
        newagent.traits = combined_traits
        newagent.codebook = combined_codebook
        newagent.trait_categories = combined_categories

        return newagent

    @staticmethod
    def add_with_plus_operator(
        first_agent: "Agent", other_agent: Optional["Agent"] = None
    ) -> "Agent":
        """Implement the + operator for agents using numeric conflict strategy.

        This method provides the implementation for the __add__ magic method,
        maintaining backward compatibility with the existing + operator behavior.

        Args:
            first_agent: The left operand agent
            other_agent: The right operand agent

        Returns:
            A new Agent instance with combined traits using numeric strategy

        Examples:
            >>> from edsl.agents import Agent
            >>> a1 = Agent(traits={'age': 30})
            >>> a2 = Agent(traits={'height': 5.5})
            >>> combined = AgentCombination.add_with_plus_operator(a1, a2)
            >>> combined.traits
            {'age': 30, 'height': 5.5}
        """
        return AgentCombination.add(
            first_agent, other_agent, conflict_strategy="numeric"
        )
