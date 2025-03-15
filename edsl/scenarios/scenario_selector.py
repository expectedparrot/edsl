from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .scenario_list import ScenarioList

class ScenarioSelector:
    """
    A class for performing advanced field selection on ScenarioList objects,
    including support for wildcard patterns.

    Args:
        scenario_list: The ScenarioList object to perform selections on

    Examples:
        >>> from edsl import Scenario, ScenarioList
        >>> scenarios = ScenarioList([Scenario({'test_1': 1, 'test_2': 2, 'other': 3}), Scenario({'test_1': 4, 'test_2': 5, 'other': 6})])
        >>> selector = ScenarioSelector(scenarios)
        >>> selector.select('test*')
        ScenarioList([Scenario({'test_1': 1, 'test_2': 2}), Scenario({'test_1': 4, 'test_2': 5})])
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """Initialize with a ScenarioList object."""
        self.scenario_list = scenario_list
        self.available_fields = (
            list(scenario_list.data[0].keys()) if scenario_list.data else []
        )

    def _match_field_pattern(self, pattern: str, field: str) -> bool:
        """
        Checks if a field name matches a pattern with wildcards.
        Supports '*' as wildcard at start or end of pattern.

        Args:
            pattern: The pattern to match against, may contain '*' at start or end
            field: The field name to check

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> selector = ScenarioSelector(ScenarioList([]))
            >>> selector._match_field_pattern('test*', 'test_field')
            True
            >>> selector._match_field_pattern('*field', 'test_field')
            True
            >>> selector._match_field_pattern('test', 'test')
            True
            >>> selector._match_field_pattern('*test*', 'my_test_field')
            True
        """
        if "*" not in pattern:
            return pattern == field

        if pattern.startswith("*") and pattern.endswith("*"):
            return pattern[1:-1] in field
        elif pattern.startswith("*"):
            return field.endswith(pattern[1:])
        elif pattern.endswith("*"):
            return field.startswith(pattern[:-1])
        return pattern == field

    def _get_matching_fields(self, patterns: list[str]) -> list[str]:
        """
        Gets all fields that match any of the given patterns.

        Args:
            patterns: List of field patterns, may contain wildcards

        Returns:
            List of field names that match at least one pattern

        Examples:
            >>> from edsl import Scenario, ScenarioList
            >>> scenarios = ScenarioList([
            ...     Scenario({'test_1': 1, 'test_2': 2, 'other': 3})
            ... ])
            >>> selector = ScenarioSelector(scenarios)
            >>> selector._get_matching_fields(['test*'])
            ['test_1', 'test_2']
        """
        matching_fields = set()
        for pattern in patterns:
            matches = [
                field
                for field in self.available_fields
                if self._match_field_pattern(pattern, field)
            ]
            matching_fields.update(matches)
        return sorted(list(matching_fields))

    def select(self, *fields) -> "ScenarioList":
        """
        Selects scenarios with only the referenced fields.
        Supports wildcard patterns using '*' at the start or end of field names.

        Args:
            *fields: Field names or patterns to select. Patterns may include '*' for wildcards.

        Returns:
            A new ScenarioList containing only the matched fields.

        Raises:
            ValueError: If no fields match the given patterns.

        Examples:
            >>> from edsl import Scenario, ScenarioList
            >>> scenarios = ScenarioList([
            ...     Scenario({'test_1': 1, 'test_2': 2, 'other': 3}),
            ...     Scenario({'test_1': 4, 'test_2': 5, 'other': 6})
            ... ])
            >>> selector = ScenarioSelector(scenarios)
            >>> selector.select('test*')  # Selects all fields starting with 'test'
            ScenarioList([Scenario({'test_1': 1, 'test_2': 2}), Scenario({'test_1': 4, 'test_2': 5})])
            >>> selector.select('*_1')  # Selects all fields ending with '_1'
            ScenarioList([Scenario({'test_1': 1}), Scenario({'test_1': 4})])
            >>> selector.select('test_1', '*_2')  # Multiple patterns
            ScenarioList([Scenario({'test_1': 1, 'test_2': 2}), Scenario({'test_1': 4, 'test_2': 5})])
        """
        if not self.scenario_list.data:
            return self.scenario_list.__class__([])

        # Convert single string to list for consistent processing
        patterns = list(fields)

        # Get all fields that match the patterns
        fields_to_select = self._get_matching_fields(patterns)

        # If no fields match, raise an informative error
        if not fields_to_select:
            raise ValueError(
                f"No fields matched the given patterns: {patterns}. "
                f"Available fields are: {self.available_fields}"
            )

        return self.scenario_list.__class__(
            [scenario.select(fields_to_select) for scenario in self.scenario_list.data]
        )

    def get_available_fields(self) -> list[str]:
        """
        Returns a list of all available fields in the ScenarioList.

        Returns:
            List of field names available for selection.

        Examples:
            >>> from edsl import Scenario, ScenarioList
            >>> scenarios = ScenarioList([Scenario({'test_1': 1, 'test_2': 2, 'other': 3})])
            >>> selector = ScenarioSelector(scenarios)
            >>> selector.get_available_fields()
            ['other', 'test_1', 'test_2']
        """
        return sorted(self.available_fields)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
