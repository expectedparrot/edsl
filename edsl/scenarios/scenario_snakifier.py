"""
Module for converting Scenario keys to valid Python identifiers (snake_case).

This module provides the ScenarioSnakifier class, which handles the transformation
of Scenario keys in a ScenarioList to valid Python identifiers by converting them
to snake_case format, handling special characters, duplicates, and Python keywords.
"""

from __future__ import annotations
import re
import keyword
from typing import TYPE_CHECKING, Dict, Set

if TYPE_CHECKING:
    from .scenario_list import ScenarioList


class ScenarioSnakifier:
    """
    Handles conversion of Scenario keys to valid Python identifiers (snake_case).

    This class provides functionality to transform all keys in a ScenarioList to
    lowercase snake_case format, ensuring they are valid Python identifiers. It
    handles special characters, spaces, duplicates, Python keywords, and edge cases.
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """
        Initialize the ScenarioSnakifier.

        Args:
            scenario_list: The ScenarioList whose keys should be snakified.
        """
        self.scenario_list = scenario_list

    @staticmethod
    def snakify_key(key: str) -> str:
        """
        Convert a single key to snake_case format.

        This method:
        - Converts to lowercase
        - Replaces spaces with underscores
        - Replaces special characters with underscores
        - Removes consecutive underscores
        - Prepends underscore if starts with a digit
        - Appends underscore if it's a Python keyword

        Args:
            key: The key string to convert.

        Returns:
            The snakified key as a valid Python identifier.

        Examples:
            >>> ScenarioSnakifier.snakify_key('First Name')
            'first_name'
            >>> ScenarioSnakifier.snakify_key('User-ID')
            'user_id'
            >>> ScenarioSnakifier.snakify_key('123field')
            '_123field'
            >>> ScenarioSnakifier.snakify_key('class')
            'class_'
        """
        # Convert to lowercase and replace spaces with underscores
        result = key.lower().replace(" ", "_")

        # Replace any non-alphanumeric characters (except underscore) with underscore
        result = re.sub(r"[^a-z0-9_]", "_", result)

        # Remove consecutive underscores
        result = re.sub(r"_+", "_", result)

        # Remove leading and trailing underscores
        result = result.strip("_")

        # If empty, use a default name
        if not result:
            result = "field"

        # If starts with a number, prepend underscore
        if result[0].isdigit():
            result = "_" + result

        # If it's a Python keyword, append underscore
        if keyword.iskeyword(result):
            result = result + "_"

        return result

    def create_key_mapping(self) -> Dict[str, str]:
        """
        Create a mapping from original keys to snakified keys.

        This method collects all keys across all scenarios in the ScenarioList
        and creates a mapping that ensures uniqueness by appending numbers to
        duplicate snakified keys.

        Returns:
            A dictionary mapping original keys to their snakified versions.

        Examples:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> sl = ScenarioList([Scenario({'First Name': 'Alice', 'Last Name': 'Smith'})])
            >>> snakifier = ScenarioSnakifier(sl)
            >>> mapping = snakifier.create_key_mapping()
            >>> sorted(mapping.items())
            [('First Name', 'first_name'), ('Last Name', 'last_name')]
        """
        # Collect all keys across all scenarios
        all_keys: Set[str] = set()
        for scenario in self.scenario_list:
            all_keys.update(scenario.keys())

        # Create the mapping from old keys to new keys
        replacement_dict: Dict[str, str] = {}
        used_names: Set[str] = set()

        for old_key in sorted(all_keys):  # Sort for deterministic behavior
            new_key = self.snakify_key(old_key)

            # Ensure uniqueness by appending numbers if needed
            if new_key in used_names:
                counter = 1
                while f"{new_key}_{counter}" in used_names:
                    counter += 1
                new_key = f"{new_key}_{counter}"

            used_names.add(new_key)
            replacement_dict[old_key] = new_key

        return replacement_dict

    def snakify(self) -> "ScenarioList":
        """
        Convert all scenario keys to valid Python identifiers (snake_case).

        This method creates a new ScenarioList with all keys transformed to
        snake_case format. The original ScenarioList remains unchanged.

        Returns:
            A new ScenarioList with snakified keys.

        Examples:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> sl = ScenarioList([Scenario({'First Name': 'Alice', 'Age Group': '30s'})])
            >>> snakifier = ScenarioSnakifier(sl)
            >>> result = snakifier.snakify()
            >>> sorted(result[0].keys())
            ['age_group', 'first_name']
            >>> result[0]['first_name']
            'Alice'
        """
        # Create the key mapping
        replacement_dict = self.create_key_mapping()

        # Use the existing rename method to apply the transformation
        return self.scenario_list.rename(replacement_dict)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
