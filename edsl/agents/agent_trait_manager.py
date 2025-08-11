"""Agent trait management functionality.

This module provides the AgentTraitManager class that handles trait manipulation
operations for Agent instances, including add, remove, translate, and conditional
operations with proper codebook and trait_categories management.
"""

from __future__ import annotations
from typing import Union, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent
    from ..utilities.similarity_rank import RankableItems


class AgentTraitManager:
    """Manages trait manipulation operations for an Agent instance.
    
    This class provides methods to add, remove, translate, and conditionally filter
    traits while properly managing associated codebooks and trait categories.
    Each Agent instance has its own trait manager.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the trait manager for an agent.
        
        Args:
            agent: The agent instance this manager will handle
        """
        self.agent = agent

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
            >>> from edsl.agents.agent_trait_manager import AgentTraitManager
            >>> # Create a minimal agent instance for testing
            >>> agent = Agent(traits={})  # Start with empty agent
            >>> agent.trait_manager.initialize({'age': 30}, {'age': 'Age in years'})
            >>> agent.traits['age']
            30
            >>> agent.codebook['age']
            'Age in years'

            Initialize with empty values:

            >>> agent2 = Agent(traits={})  # Start with empty agent
            >>> agent2.trait_manager.initialize(None, None)
            >>> agent2.traits
            {}
            >>> agent2.codebook
            {}
        """
        from ..utilities import sanitize_jinja_syntax
        from .agent_traits import AgentTraits
        
        # Sanitize traits and codebook for Jinja2 syntax
        if traits:
            traits = sanitize_jinja_syntax(traits, "traits")
        if codebook:
            codebook = sanitize_jinja_syntax(codebook, "codebook")
            
        self.agent._traits = AgentTraits(traits or {}, parent=self.agent)
        self.agent.codebook = codebook or dict()

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
            >>> results = agent.trait_manager.search_traits("job")
            >>> len(results) >= 1
            True
            >>> results[0]["trait_name"] == "occupation"
            True
            >>> results[0]["score"] > 0.5
            True

            Search traits without codebook:

            >>> agent2 = Agent(traits={"height": 5.5, "weight": 150})
            >>> results2 = agent2.trait_manager.search_traits("height")
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
            if search_lower == trait_name.lower() or search_lower == description.lower():
                exact_matches.append((trait_name, description, 1.0))  # Perfect match
            elif (search_lower in trait_name.lower() or 
                  search_lower in description.lower() or 
                  search_lower in str(trait_value).lower()):
                # Calculate simple similarity based on substring match
                name_match = search_lower in trait_name.lower()
                desc_match = search_lower in description.lower()
                
                # Higher score for name/description matches than value matches
                score = 0.8 if name_match or desc_match else 0.5
                partial_matches.append((trait_name, description, score))

        # Combine results, exact matches first
        all_matches = exact_matches + sorted(partial_matches, key=lambda x: x[2], reverse=True)
        
        # If no matches found, return all traits with low scores
        if not all_matches:
            all_matches = [(trait_name, description, 0.1) for trait_name, description, _ in trait_info]

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
            Add a single trait:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> a_with_trait = a.trait_manager.add_trait("weight", 150)
            >>> a_with_trait.traits
            {'age': 10, 'hair': 'brown', 'height': 5.5, 'weight': 150}

            Add multiple traits with a dictionary:

            >>> traits_to_add = {"weight": 150, "eye_color": "blue"}
            >>> a_with_traits = a.trait_manager.add_trait(traits_to_add)
            >>> "weight" in a_with_traits.traits and "eye_color" in a_with_traits.traits
            True
        """
        from .exceptions import AgentErrors
        
        if isinstance(trait_name_or_dict, dict) and value is None:
            newagent = self.agent.duplicate()
            newagent.traits = {**self.agent.traits, **trait_name_or_dict}
            return newagent

        if isinstance(trait_name_or_dict, dict) and value:
            raise AgentErrors(
                f"You passed a dict: {trait_name_or_dict} and a value: {value}. You should pass only a dict."
            )

        if isinstance(trait_name_or_dict, str):
            newagent = self.agent.duplicate()
            newagent.traits = {**self.agent.traits, **{trait_name_or_dict: value}}
            return newagent

        raise AgentErrors("Something is not right with adding a trait to an Agent")

    def remove_trait(self, trait: str) -> "Agent":
        """Remove a trait from the agent.

        Args:
            trait: The name of the trait to remove

        Returns:
            A new Agent instance without the specified trait

        Examples:
            Remove a single trait:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> a_without_age = a.trait_manager.remove_trait("age")
            >>> a_without_age.traits
            {'hair': 'brown', 'height': 5.5}

            Trait not in agent is handled gracefully:

            >>> a_same = a.trait_manager.remove_trait("nonexistent")
            >>> a_same.traits == a.traits
            True
        """
        newagent = self.agent.duplicate()
        newagent.traits = {k: v for k, v in self.agent.traits.items() if k != trait}
        
        # Clean up codebook for removed trait
        if trait in newagent.codebook:
            newagent.codebook = {k: v for k, v in newagent.codebook.items() if k != trait}
        
        # Clean up trait_categories for removed trait
        new_categories = {}
        for category, trait_list in self.agent.trait_categories.items():
            updated_list = [t for t in trait_list if t != trait]
            if updated_list:
                new_categories[category] = updated_list
            # Skip empty categories
        newagent.trait_categories = new_categories
        
        return newagent

    def translate_traits(self, values_codebook: dict[str, dict[Any, Any]]) -> "Agent":
        """Translate traits to a new codebook.

        This method allows you to transform trait values according to translation
        dictionaries. This is useful for converting coded values to readable ones,
        standardizing formats, or applying any value mapping.

        Args:
            values_codebook: Dictionary mapping trait names to value translation dictionaries.
                Each inner dictionary maps old values to new values.

        Returns:
            A new Agent instance with translated trait values

        Examples:
            Translate coded values to readable ones:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 10, "hair": 1, "height": 5.5, "gender": "M"})
            >>> translations = {
            ...     "hair": {1: "brown", 2: "blonde", 3: "black"},
            ...     "gender": {"M": "male", "F": "female"}
            ... }
            >>> a_translated = a.trait_manager.translate_traits(translations)
            >>> a_translated.traits
            {'age': 10, 'hair': 'brown', 'height': 5.5, 'gender': 'male'}

            Traits not in translation codebook remain unchanged:

            >>> partial_translations = {"hair": {1: "brown"}}
            >>> a_partial = a.trait_manager.translate_traits(partial_translations)
            >>> a_partial.traits["age"] == 10  # unchanged
            True
            >>> a_partial.traits["hair"] == "brown"  # translated
            True

            Values not found in translation dictionary remain unchanged:

            >>> incomplete_translations = {"hair": {2: "blonde"}}  # missing 1
            >>> a_incomplete = a.trait_manager.translate_traits(incomplete_translations)
            >>> a_incomplete.traits["hair"] == 1  # original value kept
            True
        """
        new_traits = {}
        for key, value in self.agent.traits.items():
            if key in values_codebook:
                new_traits[key] = values_codebook[key].get(value, value)
            else:
                new_traits[key] = value
        
        newagent = self.agent.duplicate()
        newagent.traits = new_traits
        return newagent

    def drop_trait_if(self, bad_value: Any) -> "Agent":
        """Drop traits that have a specific bad value.

        Args:
            bad_value: The value to remove from traits

        Returns:
            A new Agent instance with the bad value traits removed

        Examples:
            Drop traits with None values:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': None, 'weight': 150})
            >>> clean_agent = agent.trait_manager.drop_trait_if(None)
            >>> clean_agent.traits
            {'age': 30, 'weight': 150}

            Drop traits with specific values:

            >>> agent = Agent(traits={'score1': -1, 'score2': 85, 'score3': -1})
            >>> no_missing = agent.trait_manager.drop_trait_if(-1)
            >>> no_missing.traits
            {'score2': 85}
        """
        # Find traits to drop
        traits_to_drop = {k for k, v in self.agent.traits.items() if v == bad_value}
        
        if not traits_to_drop:
            return self.agent.duplicate()  # No changes needed
        
        new_agent = self.agent.duplicate()
        
        # Drop the bad traits
        new_agent.traits = {k: v for k, v in self.agent.traits.items() if v != bad_value}
        
        # Clean up codebook for dropped traits
        new_agent.codebook = {
            k: v for k, v in self.agent.codebook.items() if k in new_agent.traits
        }
        
        # Clean up trait_categories for dropped traits
        new_categories = {}
        for category, trait_list in self.agent.trait_categories.items():
            # Remove dropped traits from category lists
            updated_list = [t for t in trait_list if t not in traits_to_drop]
            if updated_list:
                new_categories[category] = updated_list
            # Skip empty categories
        new_agent.trait_categories = new_categories
        
        return new_agent

    def set_all_traits(self, traits: dict[str, Any]) -> None:
        """Set all traits for the agent, replacing the existing traits dictionary.

        This method uses the agent's traits setter to ensure proper validation
        and guard checks are performed.

        Args:
            traits: Dictionary of new traits to set

        Examples:
            Replace all traits:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'hair': 'brown'})
            >>> agent.trait_manager.set_all_traits({'height': 5.5, 'weight': 150})
            >>> agent.traits
            {'height': 5.5, 'weight': 150}

            Empty traits dictionary:

            >>> agent.trait_manager.set_all_traits({})
            >>> agent.traits
            {}
        """
        self.agent.traits = traits

    def __repr__(self) -> str:
        """Return a string representation of the manager.
        
        Returns:
            String representation showing the manager and agent
        """
        return f"AgentTraitManager(agent={self.agent.name or 'unnamed'})" 