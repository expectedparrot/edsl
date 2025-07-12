from __future__ import annotations

from .scenario_list import ScenarioList
from .dimension import Dimension
import math


class AgentBlueprint:

    def __init__(
        self, scenario_list: ScenarioList, seed: int | None = None, cycle: bool = True
    ):
        for scenario in scenario_list:
            assert "dimension" in scenario, "Scenario must have a dimension field"
            assert (
                "dimension_values" in scenario
            ), "Scenario must have a dimension_values field"

        # Optional seed allows deterministic iteration order over the Cartesian product
        # of all dimension values.  The ``cycle`` flag controls whether enumeration
        # restarts with a NEW pseudo-random permutation once every unique agent has
        # been yielded.

        # Map each dimension name → Dimension object
        self._dimension_map: dict[str, Dimension] = {}

        for sc in scenario_list:
            dim_name = sc["dimension"]

            # Try to grab an optional description field; default to empty string if absent.
            dim_desc = sc.get("dimension_description", "")

            # The "dimension_values" field may arrive in several shapes:
            #   1. Already a Dimension instance (users may construct Scenarios that way)
            #   2. A plain list of values (e.g., ["left", "right"])  [legacy]
            #   3. A nested list due to previous `collapse` operations (e.g., [["left", "right"]])  [legacy]
            dim_values_field = sc["dimension_values"]

            if isinstance(dim_values_field, Dimension):
                dim_obj = dim_values_field
            else:
                # Unpack potential single nesting introduced by collapse().
                if (
                    isinstance(dim_values_field, list)
                    and len(dim_values_field) == 1
                    and isinstance(dim_values_field[0], list)
                ):
                    raw_values = dim_values_field[0]
                else:
                    raw_values = dim_values_field  # type: ignore[assignment]

                # Construct a Dimension object from the legacy representation.
                dim_obj = Dimension(name=dim_name, description=dim_desc, values=raw_values)  # type: ignore[arg-type]

            self._dimension_map[dim_name] = dim_obj

        # Maintain a stable ordered view for mixed-radix indexing
        self.dimensions: list[str] = list(self._dimension_map.keys())
        self.dimension_values: list[list] = [
            self._dimension_map[d].to_plain_list() for d in self.dimensions
        ]

        # Pre-compute the radix sizes and total Cartesian product size.
        self._radix_sizes = [len(v) for v in self.dimension_values]
        self._total_combinations = math.prod(self._radix_sizes)

        self.seed = seed
        self.cycle = cycle

        self.scenario_list = scenario_list

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _index_to_traits(self, index: int) -> dict:
        """Convert a mixed-radix integer *index* into a traits dict.

        The least-significant dimension is the first scenario in ``scenario_list``.
        """
        traits = {}
        remaining = index
        for dimension, values, base in zip(
            self.dimensions, self.dimension_values, self._radix_sizes
        ):
            idx = remaining % base
            remaining //= base
            traits[dimension] = values[idx]
        return traits

    def _permutation_stream(self):
        """Yield a pseudo-random permutation of ``range(self._total_combinations)``.

        A simple affine cipher (a * i + b) mod N is used which is guaranteed to be
        a permutation when *a* is coprime with *N*.  The parameters a and b are
        drawn from a Random instance seeded with ``self.seed`` so that the order
        is completely reproducible given the same seed.
        """
        import math
        import random

        rng = random.Random(self.seed)
        N = self._total_combinations
        if N == 1:
            while True:
                yield 0
                if not self.cycle:
                    break
            return
        while True:
            # Choose an "a" that is coprime with N so that the mapping is bijective.
            a = rng.randrange(1, N)
            while math.gcd(a, N) != 1:
                a = rng.randrange(1, N)
            # Any b works.
            b = rng.randrange(N)

            for i in range(N):
                yield (a * i + b) % N

            if not self.cycle:
                break

    def generate_agent(self):
        """Yield :class:`edsl.agents.Agent` objects in a deterministic, non-repeating
        order determined by *seed*.

        The generator cycles through **all** possible combinations of the provided
        dimension values exactly once before repeating (unless ``cycle=False`` was
        passed to the constructor, in which case it will terminate after a single
        full pass).
        """

        from ..agents import Agent

        for combo_idx in self._permutation_stream():
            traits = self._index_to_traits(combo_idx)

            # Pull out a possible name field.
            agent_name = traits.pop("name", None) if "name" in traits else None

            yield Agent(traits, name=agent_name)

    def create_agent_list(self, n: int = 10):
        """Create a list of agents by randomly sampling a value from each dimension_values field"""
        if n > self._total_combinations:
            raise ValueError(
                f"Requested {n} agents but only {self._total_combinations} unique permutations exist."
            )

        from ..agents import AgentList

        generator = self.generate_agent()
        return AgentList([next(generator) for _ in range(n)])

    # ------------------------------------------------------------------
    # Convenience constructors / fluent builder
    # ------------------------------------------------------------------

    @classmethod
    def from_dimensions(
        cls,
        *dimensions: Dimension,
        seed: int | None = None,
        cycle: bool = True,
    ) -> "AgentBlueprint":
        """Create an *AgentBlueprint* directly from one or more :class:`Dimension` objects.

        Parameters
        ----------
        *dimensions
            One or more Dimension instances describing the categorical axes.
        seed, cycle
            Passed through to the main constructor for determinism and cycling behaviour.
        """
        if not dimensions:
            raise ValueError("At least one Dimension must be provided")

        from .scenario import Scenario  # local import to avoid circular deps
        from .scenario_list import ScenarioList

        scenarios = [
            Scenario(
                {
                    "dimension": dim.name,
                    "dimension_description": dim.description,
                    # Keeping legacy nested list structure for backward compat
                    "dimension_values": [dim.to_plain_list()],
                }
            )
            for dim in dimensions
        ]

        return cls(ScenarioList(scenarios), seed=seed, cycle=cycle)

    # Fluent API --------------------------------------------------------

    def add_dimension(self, dimension: Dimension) -> "AgentBlueprint":
        """Fluently add another *Dimension* **in-place** and return *self*.

        This recalculates the Cartesian product sizes so subsequent calls to
        ``generate_agent`` or ``create_agent_list`` will include the new
        dimension.
        """

        if dimension.name in self._dimension_map:
            raise ValueError(
                f"Dimension '{dimension.name}' already exists in blueprint"
            )

        # Add to core structures
        self._dimension_map[dimension.name] = dimension
        self.dimensions.append(dimension.name)
        self.dimension_values.append(dimension.to_plain_list())
        self._radix_sizes.append(len(dimension))

        # Recompute total combinations
        import math

        self._total_combinations = math.prod(self._radix_sizes)

        return self

    # ------------------------------------------------------------------
    # Probability utilities
    # ------------------------------------------------------------------

    def implied_probability(self, agent_or_traits) -> float:
        """Compute the naive joint probability of *agent_or_traits*.

        The probability is obtained by multiplying the marginal probabilities of
        each dimension value, assuming independence among dimensions (i.e., it
        *ignores* any conditional relationships).

        Parameters
        ----------
        agent_or_traits: Union[edsl.agents.Agent, Mapping[str, Any]]
            Either an :class:`edsl.agents.Agent` instance or a plain mapping that
            contains a key for **every** dimension in this blueprint.
        """

        # Lazy import to avoid circular dependency
        from ..agents import Agent as _Agent  # type: ignore
        from typing import Mapping, Any

        if isinstance(agent_or_traits, _Agent):
            traits: Mapping[str, Any] = agent_or_traits.traits
        else:
            traits = agent_or_traits  # type: ignore[assignment]

        prob = 1.0
        for dim_name, dimension in self._dimension_map.items():
            if dim_name not in traits:
                raise ValueError(
                    f"Traits mapping missing value for dimension '{dim_name}'"
                )
            prob *= dimension.probability_of(traits[dim_name])

        return prob


# ------------------------------------------------------------------
# Usage examples (run "python agent_blueprint.py" to see output)
# ------------------------------------------------------------------

if __name__ == "__main__":
    # Example dimensions
    politics = Dimension(
        name="politics",
        description="Political leaning",
        values=["left", "right", "center"],
    )

    age = Dimension(
        name="age",
        description="Age bracket",
        values=[("18-25", 2), ("26-35", 3), ("36-45", 1)],  # weighted
    )

    # 1. Build blueprint directly from dimensions
    blueprint = AgentBlueprint.from_dimensions(politics, age, seed=42)
    print("Total combinations (politics x age):", blueprint._total_combinations)

    print("First 5 generated agents (deterministic order):")
    for _, agent in zip(range(5), blueprint.generate_agent()):
        p = blueprint.implied_probability(agent)
        print(f"   traits={agent.traits}, p={p:.4f}")

    # 2. Fluent addition of a new dimension
    gender = Dimension(
        name="gender",
        description="Gender",
        values=["male", "female"],
    )

    blueprint.add_dimension(gender)
    print(
        "\nAfter adding gender dimension → combinations:", blueprint._total_combinations
    )

    # Sample a few agents post-addition
    agent_list = blueprint.create_agent_list(n=3)
    print("Sampled agents with probabilities:")
    for agent in agent_list:
        print(f"   traits={agent.traits}, p={blueprint.implied_probability(agent):.4f}")
