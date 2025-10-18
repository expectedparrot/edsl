"""
ConjointProfileGenerator creates random product profiles from attribute definitions.

This module provides functionality for generating conjoint analysis profiles by randomly
sampling from predefined attribute levels. It takes a ScenarioList containing attribute
definitions and produces new Scenarios representing product profiles with randomly
selected levels for each attribute.

The generator is designed to work with the output from conjoint analysis setup tools,
where each scenario in the input contains an attribute name, its possible levels, and
optionally a current/default level.

Key features:
- Configurable field mappings for attribute names and levels
- Random sampling from attribute levels with optional seeding
- Generation of individual profiles or batches of profiles
- Support for different sampling strategies (with/without replacement)

Example:
    >>> from edsl.scenarios import ConjointProfileGenerator, ScenarioList, Scenario
    >>> # Create attribute definitions for conjoint analysis
    >>> conjoint_attributes = ScenarioList([
    ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
    ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']})
    ... ])
    >>> generator = ConjointProfileGenerator(
    ...     conjoint_attributes,
    ...     attribute_field='attribute',
    ...     levels_field='levels'
    ... )
    >>> profile = generator.generate()  # Single random profile
    >>> profiles = generator.generate_batch(10)  # 10 random profiles
"""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from collections.abc import Iterator

from .scenario import Scenario
from .scenario_list import ScenarioList
from .exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class ConjointProfileGenerator:
    """
    Generates random product profiles for conjoint analysis from attribute definitions.

    This class takes a ScenarioList containing attribute definitions (each with an
    attribute name and its possible levels) and generates random product profiles
    by sampling from those levels.

    The input ScenarioList should have scenarios where each scenario represents
    one attribute with fields for the attribute name and its possible levels.

    Args:
        attribute_scenarios: ScenarioList containing attribute definitions
        attribute_field: Field name containing the attribute name (default: 'attribute')
        levels_field: Field name containing the list of levels (default: 'levels')
        random_seed: Optional seed for reproducible random sampling

    Example:
        >>> from edsl.scenarios import ConjointProfileGenerator, ScenarioList, Scenario
        >>> # Create attribute definitions
        >>> attributes = ScenarioList([
        ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
        ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']}),
        ...     Scenario({'attribute': 'size', 'levels': ['Small', 'Medium', 'Large']})
        ... ])
        >>> generator = ConjointProfileGenerator(attributes)
        >>> profile = generator.generate()
        >>> # Results in something like: Scenario({'price': '$200', 'color': 'Red', 'size': 'Large'})
    """

    def __init__(
        self,
        attribute_scenarios: ScenarioList,
        attribute_field: str = "attribute",
        levels_field: str = "levels",
        random_seed: Optional[int] = None,
    ):
        """
        Initialize the ConjointProfileGenerator.

        Args:
            attribute_scenarios: ScenarioList with attribute definitions
            attribute_field: Field name for attribute names
            levels_field: Field name for level lists
            random_seed: Optional seed for reproducible generation
        """
        # Initialize the ConjointProfileGenerator
        self.attribute_scenarios = attribute_scenarios
        self.attribute_field = attribute_field
        self.levels_field = levels_field
        self._random = random.Random(random_seed)

        # Validate input scenarios
        self._validate_scenarios()

        # Cache the attributes for efficient generation
        self._attributes = self._extract_attributes()

    def _validate_scenarios(self) -> None:
        """Validate that all scenarios have required fields."""
        if not self.attribute_scenarios:
            raise ScenarioError("Attribute scenarios list cannot be empty")

        for i, scenario in enumerate(self.attribute_scenarios):
            if self.attribute_field not in scenario:
                raise ScenarioError(
                    f"Scenario {i} missing required field '{self.attribute_field}'"
                )
            if self.levels_field not in scenario:
                raise ScenarioError(
                    f"Scenario {i} missing required field '{self.levels_field}'"
                )

            levels = scenario[self.levels_field]
            if not isinstance(levels, (list, tuple)) or len(levels) == 0:
                raise ScenarioError(
                    f"Scenario {i}: '{self.levels_field}' must be a non-empty list"
                )

    def _extract_attributes(self) -> Dict[str, List[Any]]:
        """Extract attributes and their levels into a dictionary for fast access."""
        attributes = {}
        for scenario in self.attribute_scenarios:
            attr_name = scenario[self.attribute_field]
            levels = scenario[self.levels_field]
            attributes[attr_name] = list(levels)  # Ensure it's a list
        return attributes

    def generate(self) -> Scenario:
        """
        Generate a single random product profile.

        Returns:
            Scenario with randomly selected levels for each attribute

        Example:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> attributes = ScenarioList([
            ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
            ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']})
            ... ])
            >>> generator = ConjointProfileGenerator(attributes)
            >>> profile = generator.generate()
            >>> isinstance(profile, Scenario)
            True
        """
        profile_data = {}

        for attr_name, levels in self._attributes.items():
            selected_level = self._random.choice(levels)
            profile_data[attr_name] = selected_level

        return Scenario(profile_data)

    def generate_batch(self, count: int) -> ScenarioList:
        """
        Generate multiple random product profiles.

        Args:
            count: Number of profiles to generate

        Returns:
            ScenarioList containing the generated profiles

        Example:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> attributes = ScenarioList([
            ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
            ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']})
            ... ])
            >>> generator = ConjointProfileGenerator(attributes)
            >>> profiles = generator.generate_batch(5)
            >>> len(profiles)
            5
        """
        if count <= 0:
            raise ValueError("Count must be positive")

        profiles = []
        for _ in range(count):
            profiles.append(self.generate())

        return ScenarioList(profiles)

    def generate_iterator(self, count: Optional[int] = None) -> Iterator[Scenario]:
        """
        Generate profiles as an iterator for memory-efficient processing.

        Args:
            count: Number of profiles to generate, or None for infinite iterator

        Yields:
            Scenario objects with random attribute levels

        Example:
            >>> from edsl.scenarios import ScenarioList, Scenario
            >>> attributes = ScenarioList([
            ...     Scenario({'attribute': 'price', 'levels': ['$100', '$200', '$300']}),
            ...     Scenario({'attribute': 'color', 'levels': ['Red', 'Blue', 'Green']})
            ... ])
            >>> generator = ConjointProfileGenerator(attributes)
            >>> count = 0
            >>> for profile in generator.generate_iterator():
            ...     if count >= 3:  # Generate 3 profiles for testing
            ...         break
            ...     count += 1
            >>> count
            3
        """
        generated = 0
        while count is None or generated < count:
            yield self.generate()
            generated += 1

    def get_attribute_count(self) -> int:
        """Return the number of attributes."""
        return len(self._attributes)

    def get_attributes(self) -> List[str]:
        """Return list of attribute names."""
        return list(self._attributes.keys())

    def get_levels(self, attribute: str) -> List[Any]:
        """
        Get the levels for a specific attribute.

        Args:
            attribute: Name of the attribute

        Returns:
            List of levels for the attribute

        Raises:
            KeyError: If attribute not found
        """
        if attribute not in self._attributes:
            raise KeyError(f"Attribute '{attribute}' not found")
        return self._attributes[attribute].copy()

    def get_total_combinations(self) -> int:
        """
        Calculate total number of possible unique profiles.

        Returns:
            Total combinations possible from all attribute levels
        """
        total = 1
        for levels in self._attributes.values():
            total *= len(levels)
        return total

    def generate_all_combinations(self) -> ScenarioList:
        """
        Generate all possible combinations of attribute levels.

        Warning: This can generate very large lists for many attributes/levels.
        Use with caution for large attribute spaces.

        Returns:
            ScenarioList containing all possible profiles
        """
        import itertools

        attr_names = list(self._attributes.keys())
        level_lists = [self._attributes[attr] for attr in attr_names]

        all_combinations = list(itertools.product(*level_lists))

        profiles = []
        for combination in all_combinations:
            profile_data = dict(zip(attr_names, combination))
            profiles.append(Scenario(profile_data))

        return ScenarioList(profiles)

    def __repr__(self) -> str:
        """String representation of the generator."""
        return (
            f"ConjointProfileGenerator("
            f"attributes={len(self._attributes)}, "
            f"combinations={self.get_total_combinations()})"
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
