from __future__ import annotations
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario_list import ScenarioList
    from .scenario import Scenario

class ScenarioJoin:
    """Handles join operations between two ScenarioLists.

    This class encapsulates all join-related logic, making it easier to maintain
    and extend with other join types (inner, right, full) in the future.

    >>> from edsl import ScenarioList, Scenario
    >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
    >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
    >>> s3 = s1.left_join(s2, 'name')
    >>> s3 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'}), Scenario({'age': 25, 'location': None, 'name': 'Bob'})])
    True


    """

    def __init__(self, left: "ScenarioList", right: "ScenarioList"):
        """Initialize join operation with two ScenarioLists.

        Args:
            left: The left ScenarioList
            right: The right ScenarioList
        """
        self.left = left
        self.right = right

    def left_join(self, by: Union[str, list[str]]) -> "ScenarioList":
        """Perform a left join between the two ScenarioLists.

        Args:
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        Returns:
            A new ScenarioList containing the joined scenarios

        Raises:
            ValueError: If by is empty or if any join keys don't exist in both ScenarioLists
        """
        from .scenario_list import ScenarioList

        self._validate_join_keys(by)
        by_keys = [by] if isinstance(by, str) else by

        other_dict = self._create_lookup_dict(self.right, by_keys)
        all_keys = self._get_all_keys()

        return ScenarioList(
            self._create_joined_scenarios(by_keys, other_dict, all_keys)
        )

    def _validate_join_keys(self, by: Union[str, list[str]]) -> None:
        """Validate join keys exist in both ScenarioLists."""
        if not by:
            raise ValueError(
                "Join keys cannot be empty. Please specify at least one key to join on."
            )

        by_keys = [by] if isinstance(by, str) else by
        left_keys = set(next(iter(self.left)).keys()) if self.left else set()
        right_keys = set(next(iter(self.right)).keys()) if self.right else set()

        missing_left = set(by_keys) - left_keys
        missing_right = set(by_keys) - right_keys
        if missing_left or missing_right:
            missing = missing_left | missing_right
            raise ValueError(f"Join key(s) {missing} not found in both ScenarioLists")

    @staticmethod
    def _get_key_tuple(scenario: Scenario, keys: list[str]) -> tuple:
        """Create a tuple of values for the join keys."""
        return tuple(scenario[k] for k in keys)

    def _create_lookup_dict(self, scenarios: ScenarioList, by_keys: list[str]) -> dict:
        """Create a lookup dictionary for the right scenarios."""
        return {
            self._get_key_tuple(scenario, by_keys): scenario for scenario in scenarios
        }

    def _get_all_keys(self) -> set:
        """Get all unique keys from both ScenarioLists."""
        all_keys = set()
        for scenario in self.left:
            all_keys.update(scenario.keys())
        for scenario in self.right:
            all_keys.update(scenario.keys())
        return all_keys

    def _create_joined_scenarios(
        self, by_keys: list[str], other_dict: dict, all_keys: set
    ) -> list[Scenario]:
        """Create the joined scenarios."""
        from .scenario import Scenario

        new_scenarios = []

        for scenario in self.left:
            new_scenario = {key: None for key in all_keys}
            new_scenario.update(scenario)

            key_tuple = self._get_key_tuple(scenario, by_keys)
            if matching_scenario := other_dict.get(key_tuple):
                self._handle_matching_scenario(
                    new_scenario, scenario, matching_scenario, by_keys
                )

            new_scenarios.append(Scenario(new_scenario))

        return new_scenarios

    def _handle_matching_scenario(
        self,
        new_scenario: dict,
        left_scenario: "Scenario",
        right_scenario: "Scenario",
        by_keys: list[str],
    ) -> None:
        """Handle merging of matching scenarios and conflict warnings."""
        overlapping_keys = set(left_scenario.keys()) & set(right_scenario.keys())

        for key in overlapping_keys:
            if key not in by_keys and left_scenario[key] != right_scenario[key]:
                join_conditions = [f"{k}='{left_scenario[k]}'" for k in by_keys]
                print(
                    f"Warning: Conflicting values for key '{key}' where "
                    f"{' AND '.join(join_conditions)}. "
                    f"Keeping left value: {left_scenario[key]} "
                    f"(discarding: {right_scenario[key]})"
                )

        # Only update with non-overlapping keys from matching scenario
        new_keys = set(right_scenario.keys()) - set(left_scenario.keys())
        new_scenario.update({k: right_scenario[k] for k in new_keys})


if __name__ == "__main__":
    import doctest
    doctest.testmod()
