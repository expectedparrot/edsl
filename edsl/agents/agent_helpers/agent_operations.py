"""Agent operations functionality.

This module provides the AgentOperations class that handles trait manipulation
operations for Agent instances, including drop, keep, rename, and conditional
drop operations with proper codebook and trait_categories management.
"""

from __future__ import annotations
from typing import Union, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent import Agent


class AgentOperations:
    """Handles trait manipulation operations for Agent instances.

    This class provides methods to drop, keep, rename, and conditionally filter
    traits while properly managing associated codebooks and trait categories.
    """

    @staticmethod
    def drop(agent: "Agent", *field_names: Union[str, List[str]]) -> "Agent":
        """Drop field(s) from the agent.

        Args:
            agent: The agent instance to operate on
            *field_names: The name(s) of the field(s) to drop. Can be:
                - Single field name: drop("age")
                - Multiple field names: drop("age", "height")
                - List of field names: drop(["age", "height"])

        Returns:
            A new Agent instance with the specified fields dropped

        Raises:
            AgentErrors: If no field names provided or if fields don't exist

        Examples:
            Drop a single trait from the agent:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_dropped = AgentOperations.drop(a, "age")
            >>> a_dropped.traits
            {'hair': 'brown', 'height': 5.5}

            Drop multiple traits using separate arguments:

            >>> a_dropped = AgentOperations.drop(a, "age", "height")
            >>> a_dropped.traits
            {'hair': 'brown'}

            Drop an agent field like name:

            >>> a = Agent(traits={"age": 30}, name="John")
            >>> a_dropped = AgentOperations.drop(a, "name")
            >>> a_dropped.name is None
            True
        """
        from ..exceptions import AgentErrors

        # Handle different input formats
        if len(field_names) == 1 and isinstance(field_names[0], list):
            # Case: drop(["field1", "field2"])
            fields_to_drop = field_names[0]
        else:
            # Case: drop("field1") or drop("field1", "field2")
            fields_to_drop = list(field_names)

        if not fields_to_drop:
            raise AgentErrors("No field names provided to drop")

        d = agent.to_dict()

        # Check that all fields exist before dropping any
        missing_fields = []
        for field_name in fields_to_drop:
            if field_name not in d.get("traits", {}) and field_name not in d:
                missing_fields.append(field_name)

        if missing_fields:
            raise AgentErrors(
                f"Field(s) {missing_fields} not found in agent. "
                f"Available fields: {list(d.keys())}. "
                f"Available traits: {list(d.get('traits', {}).keys())}"
            )

        # Track which traits are being dropped for codebook cleanup
        dropped_traits = []

        # Drop all the fields
        for field_name in fields_to_drop:
            if field_name in d.get("traits", {}):
                d["traits"].pop(field_name)
                dropped_traits.append(field_name)
            elif field_name in d:
                d.pop(field_name)

        # Fix: Clean up codebook entries for dropped traits
        if "codebook" in d and dropped_traits:
            for trait in dropped_traits:
                d["codebook"].pop(trait, None)
            # Remove codebook entirely if it's now empty
            if not d["codebook"]:
                d.pop("codebook", None)

        # Fix: Clean up trait_categories for dropped traits
        if "trait_categories" in d and dropped_traits:
            for category, trait_list in list(d["trait_categories"].items()):
                # Remove dropped traits from category lists
                updated_list = [t for t in trait_list if t not in dropped_traits]
                if updated_list:
                    d["trait_categories"][category] = updated_list
                else:
                    # Remove empty categories
                    d["trait_categories"].pop(category)
            # Remove trait_categories entirely if it's now empty
            if not d["trait_categories"]:
                d.pop("trait_categories", None)

        from ..agent import Agent

        return Agent.from_dict(d)

    @staticmethod
    def keep(agent: "Agent", *field_names: Union[str, List[str]]) -> "Agent":
        """Keep only the specified fields from the agent.

        Args:
            agent: The agent instance to operate on
            *field_names: The name(s) of the field(s) to keep. Can be:
                - Single field name: keep("age")
                - Multiple field names: keep("age", "height")
                - List of field names: keep(["age", "height"])

        Returns:
            A new Agent instance with only the specified fields kept

        Raises:
            AgentErrors: If no field names provided or if fields don't exist

        Examples:
            Keep a single trait:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5})
            >>> a_kept = AgentOperations.keep(a, "age")
            >>> a_kept.traits
            {'age': 30}

            Keep multiple traits using separate arguments:

            >>> a_kept = AgentOperations.keep(a, "age", "height")
            >>> a_kept.traits
            {'age': 30, 'height': 5.5}

            Keep agent fields and traits:

            >>> a = Agent(traits={"age": 30, "hair": "brown"}, name="John")
            >>> a_kept = AgentOperations.keep(a, "name", "age")
            >>> a_kept.name
            'John'
            >>> a_kept.traits
            {'age': 30}
        """
        from ..exceptions import AgentErrors

        # Handle different input formats
        if len(field_names) == 1 and isinstance(field_names[0], list):
            # Case: keep(["field1", "field2"])
            fields_to_keep = field_names[0]
        else:
            # Case: keep("field1") or keep("field1", "field2")
            fields_to_keep = list(field_names)

        if not fields_to_keep:
            raise AgentErrors("No field names provided to keep")

        d = agent.to_dict()

        # Check that all requested fields exist
        available_fields = set(d.keys()) | set(d.get("traits", {}).keys())
        missing_fields = set(fields_to_keep) - available_fields
        if missing_fields:
            raise AgentErrors(
                f"Field(s) {missing_fields} not found in agent. "
                f"Available fields: {list(d.keys())}. "
                f"Available traits: {list(d.get('traits', {}).keys())}"
            )

        # Create new dictionary with only the requested fields
        new_d = {}

        # Keep top-level fields that were requested
        for field_name in fields_to_keep:
            if field_name in d and field_name != "traits":
                new_d[field_name] = d[field_name]

        # Handle traits separately
        requested_traits = [f for f in fields_to_keep if f in d.get("traits", {})]
        if requested_traits:
            new_d["traits"] = {trait: d["traits"][trait] for trait in requested_traits}

        # Fix: Keep only relevant codebook entries
        if "codebook" in d and requested_traits:
            relevant_codebook = {
                trait: d["codebook"][trait]
                for trait in requested_traits
                if trait in d["codebook"]
            }
            if relevant_codebook:
                new_d["codebook"] = relevant_codebook

        # Fix: Keep only relevant trait_categories
        if "trait_categories" in d and requested_traits:
            relevant_categories = {}
            for category, trait_list in d["trait_categories"].items():
                # Keep traits that are both in the category and requested
                kept_traits = [t for t in trait_list if t in requested_traits]
                if kept_traits:
                    relevant_categories[category] = kept_traits
            if relevant_categories:
                new_d["trait_categories"] = relevant_categories

        # Always include edsl metadata if present
        if "edsl_version" in d:
            new_d["edsl_version"] = d["edsl_version"]
        if "edsl_class_name" in d:
            new_d["edsl_class_name"] = d["edsl_class_name"]

        from ..agent import Agent

        return Agent.from_dict(new_d)

    @staticmethod
    def rename(
        agent: "Agent",
        old_name_or_dict: Union[str, dict[str, str]],
        new_name: Optional[str] = None,
    ) -> "Agent":
        """Rename a trait.

        Args:
            agent: The agent instance to operate on
            old_name_or_dict: The old name of the trait or a dictionary of old names and new names
            new_name: The new name of the trait (required if old_name_or_dict is a string)

        Returns:
            A new Agent instance with renamed traits

        Raises:
            AgentErrors: If invalid arguments are provided or traits don't exist

        Examples:
            Rename a single trait:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> newa = AgentOperations.rename(a, "age", "years")
            >>> newa.traits
            {'years': 10, 'hair': 'brown', 'height': 5.5}

            Rename multiple traits using a dictionary:

            >>> newa = AgentOperations.rename(a, {'age': 'years', 'height': 'tall'})
            >>> newa.traits
            {'years': 10, 'hair': 'brown', 'tall': 5.5}
        """
        from ..exceptions import AgentErrors

        agent.traits_manager.check_before_modifying_traits()

        if isinstance(old_name_or_dict, dict) and new_name:
            raise AgentErrors(
                f"You passed a dict: {old_name_or_dict} and a new name: {new_name}. You should pass only a dict."
            )

        if isinstance(old_name_or_dict, dict) and new_name is None:
            return AgentOperations._rename_dict(agent, old_name_or_dict)

        if isinstance(old_name_or_dict, str):
            return AgentOperations._rename_single(agent, old_name_or_dict, new_name)

        raise AgentErrors("Something is not right with Agent renaming")

    @staticmethod
    def _rename_dict(agent: "Agent", renaming_dict: dict[str, str]) -> "Agent":
        """Internal method to rename traits using a dictionary.

        The keys should all be old names and the values should all be new names.

        Args:
            agent: The agent instance to operate on
            renaming_dict: Dictionary mapping old trait names to new names

        Returns:
            A new Agent instance with renamed traits

        Raises:
            AgentErrors: If any specified trait names don't exist
        """
        from ..exceptions import AgentErrors

        try:
            assert all(k in agent.traits for k in renaming_dict.keys())
        except AssertionError:
            raise AgentErrors(
                f"The trait(s) {set(renaming_dict.keys()) - set(agent.traits.keys())} do not exist in the agent's traits, which are {agent.traits}."
            )

        new_agent = agent.duplicate()
        new_agent.traits = {renaming_dict.get(k, k): v for k, v in agent.traits.items()}

        # Fix: Update codebook keys for dict renames
        new_codebook = {}
        for old_key, description in agent.codebook.items():
            new_key = renaming_dict.get(old_key, old_key)
            new_codebook[new_key] = description
        new_agent.codebook = new_codebook

        # Fix: Update trait_categories for dict renames
        new_categories = {}
        for category, trait_list in agent.trait_categories.items():
            new_trait_list = [renaming_dict.get(trait, trait) for trait in trait_list]
            new_categories[category] = new_trait_list
        new_agent.trait_categories = new_categories

        return new_agent

    @staticmethod
    def _rename_single(agent: "Agent", old_name: str, new_name: str) -> "Agent":
        """Rename a single trait.

        Args:
            agent: The agent instance to operate on
            old_name: The current name of the trait
            new_name: The new name for the trait

        Returns:
            A new Agent instance with the renamed trait

        Raises:
            AgentErrors: If the specified trait name doesn't exist
        """
        from ..exceptions import AgentErrors

        try:
            assert old_name in agent.traits
        except AssertionError:
            raise AgentErrors(
                f"The trait '{old_name}' does not exist in the agent's traits, which are {agent.traits}."
            )

        newagent = agent.duplicate()
        newagent.traits = {
            new_name if k == old_name else k: v for k, v in agent.traits.items()
        }
        newagent.codebook = {
            new_name if k == old_name else k: v for k, v in agent.codebook.items()
        }

        # Fix: Update trait_categories for single renames
        new_categories = {}
        for category, trait_list in agent.trait_categories.items():
            new_trait_list = [
                new_name if trait == old_name else trait for trait in trait_list
            ]
            new_categories[category] = new_trait_list
        newagent.trait_categories = new_categories

        return newagent

    @staticmethod
    def select(agent: "Agent", *traits: str) -> "Agent":
        """Select agents with only the referenced traits.

        This method is implemented using the robust keep() logic but only operates
        on traits (not agent fields), maintaining backward compatibility with the
        original select() behavior while providing better data integrity.

        Args:
            agent: The agent instance to operate on
            *traits: The trait names to select

        Returns:
            A new Agent instance with only the selected traits

        Examples:
            Select specific traits from an agent:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 30, "hair": "brown", "height": 5.5},
            ...           codebook={'age': 'Age in years', 'hair': 'Hair color'})
            >>> selected = AgentOperations.select(a, "age", "hair")
            >>> selected.traits
            {'age': 30, 'hair': 'brown'}

            Select with trait_categories properly cleaned up:

            >>> a = Agent(traits={"age": 30, "height": 5.8, "weight": 150},
            ...           trait_categories={'personal': ['age'], 'physical': ['height', 'weight']})
            >>> selected = AgentOperations.select(a, "age")
            >>> selected.traits
            {'age': 30}
            >>> selected.trait_categories
            {'personal': ['age']}

            Gracefully handle non-existent traits (unlike keep, this doesn't error):

            >>> selected = AgentOperations.select(a, "age", "nonexistent")
            >>> selected.traits
            {'age': 30}
        """
        # Filter traits to only include those that exist in the agent
        existing_traits = [trait for trait in traits if trait in agent.traits]

        if not existing_traits:
            # If no valid traits specified, return agent with empty traits but preserve structure
            from ..agent import Agent

            return Agent(
                traits={},
                name=agent.name,
                instruction=agent.instruction if agent.set_instructions else None,
                codebook={},
                trait_categories={},
            )

        # Use the robust keep() implementation, but only pass trait names
        # This ensures proper codebook and trait_categories management
        return AgentOperations.keep(agent, *existing_traits)

    @staticmethod
    def drop_trait_if(agent: "Agent", bad_value: Any) -> "Agent":
        """Drop traits that have a specific bad value.

        Args:
            agent: The agent instance to operate on
            bad_value: The value to remove from traits

        Returns:
            A new Agent instance with the bad value traits removed

        Examples:
            Remove traits with None values:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30, 'height': None, 'weight': 150})
            >>> clean_agent = AgentOperations.drop_trait_if(agent, None)
            >>> clean_agent.traits
            {'age': 30, 'weight': 150}

            Remove traits with zero values:

            >>> agent = Agent(traits={'age': 30, 'score1': 0, 'score2': 85, 'score3': 0})
            >>> no_zeros = AgentOperations.drop_trait_if(agent, 0)
            >>> no_zeros.traits
            {'age': 30, 'score2': 85}
        """
        new_agent = agent.duplicate()

        # Find traits to drop
        traits_to_drop = [k for k, v in agent.traits.items() if v == bad_value]

        # Drop the bad traits
        new_agent.traits = {k: v for k, v in agent.traits.items() if v != bad_value}

        # Clean up codebook for dropped traits
        new_agent.codebook = {
            k: v for k, v in agent.codebook.items() if k in new_agent.traits
        }

        # Fix: Clean up trait_categories for dropped traits
        new_categories = {}
        for category, trait_list in agent.trait_categories.items():
            # Remove dropped traits from category lists
            updated_list = [t for t in trait_list if t not in traits_to_drop]
            if updated_list:
                new_categories[category] = updated_list
            # Skip empty categories
        new_agent.trait_categories = new_categories

        return new_agent

    @staticmethod
    def add_trait(
        agent: "Agent",
        trait_name_or_dict: Union[str, dict[str, Any]],
        value: Optional[Any] = None,
    ) -> "Agent":
        """Add a trait to an agent and return a new agent.

        Args:
            agent: The agent instance to operate on
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
            >>> a_with_trait = AgentOperations.add_trait(a, "weight", 150)
            >>> a_with_trait.traits
            {'age': 10, 'hair': 'brown', 'height': 5.5, 'weight': 150}

            Add multiple traits with a dictionary:

            >>> traits_to_add = {"weight": 150, "eye_color": "blue"}
            >>> a_with_traits = AgentOperations.add_trait(a, traits_to_add)
            >>> "weight" in a_with_traits.traits and "eye_color" in a_with_traits.traits
            True
        """
        from ..exceptions import AgentErrors

        if isinstance(trait_name_or_dict, dict) and value is None:
            newagent = agent.duplicate()
            newagent.traits = {**agent.traits, **trait_name_or_dict}
            return newagent

        if isinstance(trait_name_or_dict, dict) and value:
            raise AgentErrors(
                f"You passed a dict: {trait_name_or_dict} and a value: {value}. You should pass only a dict."
            )

        if isinstance(trait_name_or_dict, str):
            newagent = agent.duplicate()
            newagent.traits = {**agent.traits, **{trait_name_or_dict: value}}
            return newagent

        raise AgentErrors("Something is not right with adding a trait to an Agent")

    @staticmethod
    def remove_trait(agent: "Agent", trait: str) -> "Agent":
        """Remove a trait from the agent.

        Args:
            agent: The agent instance to operate on
            trait: The name of the trait to remove

        Returns:
            A new Agent instance without the specified trait

        Examples:
            Remove a single trait:

            >>> from edsl.agents import Agent
            >>> a = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
            >>> a_without_age = AgentOperations.remove_trait(a, "age")
            >>> a_without_age.traits
            {'hair': 'brown', 'height': 5.5}

            Trait not in agent is handled gracefully:

            >>> a_same = AgentOperations.remove_trait(a, "nonexistent")
            >>> a_same.traits == a.traits
            True
        """
        newagent = agent.duplicate()
        newagent.traits = {k: v for k, v in agent.traits.items() if k != trait}

        # Clean up codebook for removed trait
        if trait in newagent.codebook:
            newagent.codebook = {
                k: v for k, v in newagent.codebook.items() if k != trait
            }

        # Clean up trait_categories for removed trait
        new_categories = {}
        for category, trait_list in agent.trait_categories.items():
            updated_list = [t for t in trait_list if t != trait]
            if updated_list:
                new_categories[category] = updated_list
            # Skip empty categories
        newagent.trait_categories = new_categories

        return newagent

    @staticmethod
    def translate_traits(
        agent: "Agent", values_codebook: dict[str, dict[Any, Any]]
    ) -> "Agent":
        """Translate traits to a new codebook.

        This method allows you to transform trait values according to translation
        dictionaries. This is useful for converting coded values to readable ones,
        standardizing formats, or applying any value mapping.

        Args:
            agent: The agent instance to operate on
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
            >>> a_translated = AgentOperations.translate_traits(a, translations)
            >>> a_translated.traits
            {'age': 10, 'hair': 'brown', 'height': 5.5, 'gender': 'male'}

            Traits not in translation codebook remain unchanged:

            >>> partial_translations = {"hair": {1: "brown"}}
            >>> a_partial = AgentOperations.translate_traits(a, partial_translations)
            >>> a_partial.traits["age"] == 10  # unchanged
            True
            >>> a_partial.traits["hair"] == "brown"  # translated
            True

            Values not found in translation dictionary remain unchanged:

            >>> incomplete_translations = {"hair": {2: "blonde"}}  # missing 1
            >>> a_incomplete = AgentOperations.translate_traits(a, incomplete_translations)
            >>> a_incomplete.traits["hair"] == 1  # original value kept
            True
        """
        new_traits = {}
        for key, value in agent.traits.items():
            if key in values_codebook:
                new_traits[key] = values_codebook[key].get(value, value)
            else:
                new_traits[key] = value

        newagent = agent.duplicate()
        newagent.traits = new_traits
        return newagent
