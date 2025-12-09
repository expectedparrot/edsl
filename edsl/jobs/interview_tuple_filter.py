"""
Module for filtering interview tuples based on Jinja2 expressions.

This module provides the InterviewTupleFilter class which generates
(agent, scenario, model) tuples that match an optional include expression.
"""

from typing import Generator, Tuple, Optional, Any, Sequence
from itertools import product

from jinja2 import Environment


class InterviewTupleFilter:
    """
    Filters combinations of agents, scenarios, and models based on a Jinja2 expression.

    When iterated, yields (agent, scenario, model) tuples that satisfy the include expression.
    If no expression is provided, yields all combinations (equivalent to itertools.product).

    Example expressions:
        - "{{ scenario._index }} == {{ agent._index }}"  # Only matching indices
        - "{{ agent._index }} < 5"  # First 5 agents only
        - "{{ scenario._index }} % 2 == 0"  # Even-indexed scenarios

    Usage:
        filter = InterviewTupleFilter(agents, scenarios, models, "{{ scenario._index }} == {{ agent._index }}")
        for agent, scenario, model in filter:
            # process matching tuples
    """

    def __init__(
        self,
        agents: Sequence[Any],
        scenarios: Sequence[Any],
        models: Sequence[Any],
        include_expression: Optional[str] = None,
    ):
        self.agents = agents
        self.scenarios = scenarios
        self.models = models
        self.include_expression = include_expression

        if include_expression:
            self._env = Environment()
            self._template = self._env.from_string(include_expression)
        else:
            self._template = None

    def _evaluate_expression(self, agent: Any, scenario: Any, model: Any) -> bool:
        """Evaluate the include expression for a given combination."""
        if self._template is None:
            return True

        result = self._template.render(
            agent=agent,
            scenario=scenario,
            model=model,
        )
        # breakpoint()
        # Handle string results from Jinja2
        result_str = result.strip().lower()
        return result_str == "true"

    def __iter__(self) -> Generator[Tuple[Any, Any, Any], None, None]:
        """Iterate over all valid (agent, scenario, model) tuples."""
        for agent, scenario, model in product(self.agents, self.scenarios, self.models):
            if self._evaluate_expression(agent, scenario, model):
                yield agent, scenario, model

    def __len__(self) -> int:
        """
        Return the count of valid tuples.

        Note: This iterates through all combinations, so use sparingly on large datasets.
        """
        return sum(1 for _ in self)


if __name__ == "__main__":
    # Simple test
    class MockItem:
        def __init__(self, index):
            self._index = index

        def __repr__(self):
            return f"Item({self._index})"

    agents = [MockItem(i) for i in range(3)]
    scenarios = [MockItem(i) for i in range(3)]
    models = [MockItem(0)]

    # Test with no filter
    print("No filter (all combinations):")
    f = InterviewTupleFilter(agents, scenarios, models, None)
    for t in f:
        print(f"  {t}")

    # Test with index equality
    print("\nWith filter (scenario._index == agent._index):")
    f = InterviewTupleFilter(
        agents, scenarios, models, "{{ scenario._index == agent._index }}"
    )
    for t in f:
        print(f"  {t}")
