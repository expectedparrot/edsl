from __future__ import annotations

from .scenario_list import ScenarioList
from .dimension import Dimension
from ..base.base_class import Base
import math


class AgentBlueprint(Base):

    def __init__(
        self,
        scenario_list: ScenarioList,
        seed: int | None = None,
        cycle: bool = True,
        *,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: str | None = None,
        dimension_probs_field: str | None = None,
    ):
        # Allow custom field names for the scenario schema. Defaults align with legacy behavior.
        # If no description field is provided, we will accept either
        # "dimension_description" (legacy) or "dimension_desc" (new) when present.
        self._dimension_name_field = dimension_name_field
        self._dimension_values_field = dimension_values_field
        self._dimension_description_field = dimension_description_field
        self._dimension_probs_field = dimension_probs_field
        
        for scenario in scenario_list:
            assert (
                self._dimension_name_field in scenario
            ), "Scenario must have a dimension name field"
            assert (
                self._dimension_values_field in scenario
            ), "Scenario must have a dimension_values field"

        # Optional seed allows deterministic iteration order over the Cartesian product
        # of all dimension values.  The ``cycle`` flag controls whether enumeration
        # restarts with a NEW pseudo-random permutation once every unique agent has
        # been yielded.

        # Map each dimension name → Dimension object
        self._dimension_map: dict[str, Dimension] = {}

        for sc in scenario_list:
            dim_name = sc[self._dimension_name_field]

            # Try to grab an optional description field; default to empty string if absent.
            if self._dimension_description_field is not None:
                dim_desc = sc.get(self._dimension_description_field, "")
            else:
                # Fallback order: legacy "dimension_description" then new "dimension_desc"
                dim_desc = sc.get("dimension_description", sc.get("dimension_desc", ""))

            # The "dimension_values" field may arrive in several shapes:
            #   1. Already a Dimension instance (users may construct Scenarios that way)
            #   2. A plain list of values (e.g., ["left", "right"])  [legacy]
            #   3. A nested list due to previous `collapse` operations (e.g., [["left", "right"]])  [legacy]
            dim_values_field = sc[self._dimension_values_field]

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

                # Optionally read per-value probabilities from a parallel field
                # and construct weighted Dimension values.
                weighted_values = None
                if (
                    self._dimension_probs_field is not None
                    and self._dimension_probs_field in sc
                ):
                    probs_field = sc[self._dimension_probs_field]
                    if (
                        isinstance(probs_field, list)
                        and len(probs_field) == 1
                        and isinstance(probs_field[0], list)
                    ):
                        raw_probs = probs_field[0]
                    else:
                        raw_probs = probs_field  # type: ignore[assignment]

                    # Validate length alignment
                    if not isinstance(raw_values, list) or not isinstance(raw_probs, list):  # type: ignore[unreachable]
                        raise ValueError(
                            "dimension_values and dimension_probs must be list-like when using separate probability field"
                        )
                    if len(raw_values) != len(raw_probs):
                        raise ValueError(
                            f"Length mismatch for dimension '{dim_name}': {len(raw_values)} values but {len(raw_probs)} probabilities. "
                            f"Values: {raw_values}. Probabilities: {raw_probs}"
                        )
                    # Coerce and validate numeric probabilities early for clearer errors
                    weighted_values = []
                    for _val, _prob in zip(raw_values, raw_probs):
                        try:
                            w = float(_prob)
                        except Exception:
                            raise ValueError(
                                f"Non-numeric probability specified for dimension '{dim_name}': {_prob!r} "
                                f"(type: {type(_prob).__name__}). Expected numeric values but got: "
                                f"values={raw_values}, probabilities={raw_probs}"
                            )
                        weighted_values.append((_val, w))

                # Construct a Dimension object, using weights if provided.
                dim_obj = Dimension(
                    name=dim_name,
                    description=dim_desc,
                    values=weighted_values if weighted_values is not None else raw_values,  # type: ignore[arg-type]
                )

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

    def __repr__(self) -> str:  # pragma: no cover
        """Return a concise, human-friendly summary of dimensions and values.

        Example output (weights shown only when relevant):

            AgentBlueprint: 3 dimensions, 18 combinations (seed=42, cycle=True)
              - politics [3]: 'left', 'right', 'center'
              - age [3]: '18-25':2, '26-35':3, '36-45':1
              - gender [2]: 'male', 'female'
        """
        header = (
            f"AgentBlueprint: {len(self.dimensions)} dimensions, {self._total_combinations} combinations "
            f"(seed={self.seed}, cycle={self.cycle})"
        )

        lines: list[str] = [header]
        for dim_name in self.dimensions:
            dim = self._dimension_map[dim_name]
            # Show weights only if any weight differs from the default 1.0
            show_weights = any(dv.weight != 1.0 for dv in dim.values)
            if show_weights:
                values_repr = ", ".join(
                    f"{dv.value!r}:{dv.weight:g}" for dv in dim.values
                )
            else:
                values_repr = ", ".join(repr(v) for v in dim.to_plain_list())
            lines.append(f"  - {dim_name} [{len(dim)}]: {values_repr}")

        return "\n".join(lines)

    def table(self, *args, **kwargs) -> str:
        return self.scenario_list.table(*args, **kwargs)

    def to_dict(self, add_edsl_version=False) -> dict:
        """Serialize the AgentBlueprint to a dictionary.
        
        Args:
            add_edsl_version: If True, include EDSL version information
            
        Returns:
            dict: Dictionary representation of the AgentBlueprint
        """
        d = {
            "scenario_list": self.scenario_list.to_dict(add_edsl_version=False),
            "seed": self.seed,
            "cycle": self.cycle,
            "dimension_name_field": self._dimension_name_field,
            "dimension_values_field": self._dimension_values_field,
            "dimension_description_field": self._dimension_description_field,
            "dimension_probs_field": self._dimension_probs_field,
        }
        
        if add_edsl_version:
            from edsl import __version__
            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__
            
        return d
    
    @classmethod
    def from_dict(cls, d: dict) -> "AgentBlueprint":
        """Create an AgentBlueprint from a dictionary.
        
        Args:
            d: Dictionary representation of an AgentBlueprint
            
        Returns:
            AgentBlueprint: A new AgentBlueprint instance
        """
        from .scenario_list import ScenarioList
        
        scenario_list = ScenarioList.from_dict(d["scenario_list"])
        
        return cls(
            scenario_list=scenario_list,
            seed=d.get("seed"),
            cycle=d.get("cycle", True),
            dimension_name_field=d.get("dimension_name_field", "dimension"),
            dimension_values_field=d.get("dimension_values_field", "dimension_values"),
            dimension_description_field=d.get("dimension_description_field"),
            dimension_probs_field=d.get("dimension_probs_field"),
        )
    
    def code(self) -> str:
        """Generate Python code that recreates this AgentBlueprint.
        
        Returns:
            str: Python code that recreates this object
        """
        lines = ["from edsl.scenarios import AgentBlueprint, Dimension", ""]
        
        # Generate dimension code
        for dim_name in self.dimensions:
            dim = self._dimension_map[dim_name]
            dim_code = dim.code()
            lines.append(dim_code)
        
        # Generate AgentBlueprint instantiation
        dim_names = ", ".join(self.dimensions)
        lines.append("")
        lines.append(f"blueprint = AgentBlueprint.from_dimensions(")
        lines.append(f"    {dim_names},")
        if self.seed is not None:
            lines.append(f"    seed={self.seed},")
        lines.append(f"    cycle={self.cycle}")
        lines.append(")")
        
        return "\n".join(lines)

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

    def _build_codebook(self) -> dict[str, str]:
        """Construct a codebook mapping dimension names to descriptions.

        Excludes the special "name" field which is treated as an Agent parameter,
        not a trait.
        """
        codebook: dict[str, str] = {}
        for dim_name, dim in self._dimension_map.items():
            if dim_name == "name":
                continue
            codebook[dim_name] = dim.description or ""
        return codebook

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

    def create_agent_list(
        self,
        n: int = 10,
        *,
        strategy: str = "permutation",
        unique: bool = False,
        seed: int | None = None,
    ):
        """Create an :class:`edsl.agents.AgentList` using either deterministic permutations or probability sampling.

        Parameters
        ----------
        n: int, default=10
            Number of agents to return.
        strategy: {"permutation", "probability"}, default="permutation"
            - "permutation": enumerate the Cartesian product in a deterministic pseudo-random order
              (seeded by ``self.seed``) and take the first ``n``.
            - "probability": independently sample each dimension according to its weights. If all
              weights are 1.0 this is uniform per-dimension sampling.
        unique: bool, default=False
            When ``strategy='probability'``, attempt to reject duplicate joint trait vectors. If ``n``
            exceeds the number of unique combinations, a ``ValueError`` is raised.
        seed: int | None
            Optional seed used when ``strategy='probability'``. Defaults to ``self.seed`` when omitted.
        """
        if isinstance(n, str):
            n = int(n)

        from ..agents import Agent, AgentList
        import random

        if strategy not in {"permutation", "probability"}:
            raise ValueError("strategy must be either 'permutation' or 'probability'")

        # Build a codebook mapping trait (dimension) names to their descriptions
        codebook = self._build_codebook()

        if strategy == "permutation":
            if n > self._total_combinations:
                raise ValueError(
                    f"Requested {n} agents but only {self._total_combinations} unique permutations exist."
                )
            generator = self.generate_agent()
            return AgentList([next(generator) for _ in range(n)], codebook=codebook)

        # strategy == "probability"
        if unique and n > self._total_combinations:
            raise ValueError(
                f"Requested {n} unique agents but only {self._total_combinations} unique permutations exist."
            )

        rng = random.Random(self.seed if seed is None else seed)

        def _sample_once() -> Agent:
            # Draw one value from each Dimension according to weights
            traits = {}
            for dim_name in self.dimensions:
                dim = self._dimension_map[dim_name]
                traits[dim_name] = dim.sample(rng=rng)

            agent_name = traits.pop("name", None) if "name" in traits else None
            return Agent(traits, name=agent_name)

        if not unique:
            return AgentList([_sample_once() for _ in range(n)], codebook=codebook)

        # unique=True: rejection sampling with a safety cap
        seen: set = set()
        agents: list[Agent] = []
        # Allow generous attempts before giving up (helps when weights are skewed)
        max_attempts = max(1000, 20 * n)
        attempts = 0
        while len(agents) < n and attempts < max_attempts:
            attempts += 1
            agent = _sample_once()
            # Key by ordered tuple of values for stable uniqueness across dimensions
            try:
                key = tuple(agent.traits.get(dim) for dim in self.dimensions)
            except Exception:
                # Fallback to repr-based key if values are problematic
                key = tuple(repr(agent.traits.get(dim)) for dim in self.dimensions)
            if key in seen:
                continue
            seen.add(key)
            agents.append(agent)

        if len(agents) < n:
            raise RuntimeError(
                "Could not generate the requested number of unique agents via probability sampling. "
                "Consider reducing 'n' or using strategy='permutation'."
            )

        return AgentList(agents, codebook=codebook)

    # ------------------------------------------------------------------
    # Convenience constructors / fluent builder
    # ------------------------------------------------------------------

    @classmethod
    def from_dimensions(
        cls,
        *dimensions: Dimension,
        seed: int | None = None,
        cycle: bool = True,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: str | None = None,
    ) -> "AgentBlueprint":
        """Create an *AgentBlueprint* directly from one or more :class:`Dimension` objects.

        Parameters
        ----------
        *dimensions
            One or more Dimension instances describing the categorical axes.
        seed, cycle
            Passed through to the main constructor for determinism and cycling behaviour.
        dimension_name_field, dimension_values_field, dimension_description_field
            Custom field names for scenarios produced by this convenience constructor.
            If no description field name is provided, the legacy key "dimension_description"
            will be used when constructing scenarios, while the main constructor will accept
            either "dimension_description" or "dimension_desc" on ingestion.
        """
        if not dimensions:
            raise ValueError("At least one Dimension must be provided")

        from .scenario import Scenario  # local import to avoid circular deps
        from .scenario_list import ScenarioList

        scenarios = []
        for dim in dimensions:
            data = {
                dimension_name_field: dim.name,
                # Keeping legacy nested list structure for backward compat
                dimension_values_field: [dim.to_plain_list()],
            }
            # Only include description field if the caller specifies a custom key; otherwise
            # use the legacy key to maintain stable behaviour of emitted scenarios.
            if dimension_description_field is not None:
                data[dimension_description_field] = dim.description
            else:
                data["dimension_description"] = dim.description
            scenarios.append(Scenario(data))

        return cls(
            ScenarioList(scenarios),
            seed=seed,
            cycle=cycle,
            dimension_name_field=dimension_name_field,
            dimension_values_field=dimension_values_field,
            dimension_description_field=dimension_description_field,
        )

    @classmethod
    def from_dimensions_dict(
        cls,
        dimensions_dict: dict[str, list],
        seed: int | None = None,
        cycle: bool = True,
    ) -> "AgentBlueprint":
        """Create an *AgentBlueprint* from a simple dictionary mapping dimension names to values.

        This is a convenient constructor for quickly creating blueprints from simple
        data structures without needing to construct Dimension objects explicitly.

        Parameters
        ----------
        dimensions_dict : dict[str, list]
            Dictionary mapping dimension names to lists of possible values.
            Example: {"politics": ["left", "right", "center"], "age": ["young", "old"]}
        seed, cycle
            Passed through to the main constructor for determinism and cycling behaviour.

        Examples
        --------
        >>> blueprint = AgentBlueprint.from_dimensions_dict({
        ...     "politics": ["left", "right", "center"],
        ...     "age": ["young", "old"]
        ... })
        >>> print(blueprint._total_combinations)  # 6 combinations
        """
        if not dimensions_dict:
            raise ValueError("dimensions_dict cannot be empty")

        dimensions = []
        for name, values in dimensions_dict.items():
            if not isinstance(values, list) or not values:
                raise ValueError(f"Dimension '{name}' must have a non-empty list of values")
            dimensions.append(Dimension(name=name, description="", values=values))

        return cls.from_dimensions(*dimensions, seed=seed, cycle=cycle)

    @classmethod
    def example(cls) -> "AgentBlueprint":
        """Create an example AgentBlueprint with sample dimensions for demonstration.

        Returns
        -------
        AgentBlueprint
            A blueprint with politics, age, and gender dimensions showing
            different value types including weighted values.

        Examples
        --------
        >>> blueprint = AgentBlueprint.example()
        >>> print(blueprint)
        >>> # Generate a few sample agents
        >>> agents = blueprint.create_agent_list(n=3)
        >>> for agent in agents:
        ...     print(f"Agent: {agent.traits}")
        """
        politics = Dimension(
            name="politics",
            description="Political leaning",
            values=["left", "right", "center"],
        )
        
        age = Dimension(
            name="age",
            description="Age bracket",
            values=[("18-25", 2), ("26-35", 3), ("36-45", 1)],  # weighted values
        )
        
        gender = Dimension(
            name="gender",
            description="Gender identity",
            values=["male", "female", "non-binary"],
        )
        
        return cls.from_dimensions(politics, age, gender, seed=42)

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
