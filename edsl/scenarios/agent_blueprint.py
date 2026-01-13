from __future__ import annotations

from .scenario_list import ScenarioList
from .agent_blueprint_helpers.dimension import Dimension
from edsl.base.base_class import Base
import math


class AgentBlueprint(Base):
    def __init__(
        self,
        dimension_map: dict[str, Dimension],
        *,
        seed: int | None = None,
        cycle: bool = True,
    ):
        """Initialize an AgentBlueprint with processed dimensions.

        This is the clean constructor that takes already-processed Dimension objects.
        For most use cases, prefer using classmethods like `from_dimensions` or
        `from_scenario_list`.

        Args:
            dimension_map: Dictionary mapping dimension names to Dimension objects.
            seed: Optional seed for deterministic iteration order.
            cycle: Whether to cycle through permutations indefinitely.

        Examples:
            >>> from edsl.scenarios import Dimension
            >>> politics = Dimension(name="politics", description="Political leaning", values=["left", "right"])
            >>> age = Dimension(name="age", description="Age group", values=["young", "old"])
            >>> blueprint = AgentBlueprint(
            ...     dimension_map={"politics": politics, "age": age},
            ...     seed=42
            ... )
            >>> blueprint.dimensions
            ['politics', 'age']
        """
        if not dimension_map:
            raise ValueError("dimension_map cannot be empty")

        # Store the dimension map
        self._dimension_map: dict[str, Dimension] = dimension_map

        # Maintain a stable ordered view for mixed-radix indexing
        self.dimensions: list[str] = list(self._dimension_map.keys())
        self.dimension_values: list[list] = [
            self._dimension_map[d].to_plain_list() for d in self.dimensions
        ]

        # Pre-compute the radix sizes and total Cartesian product size
        self._radix_sizes = [len(v) for v in self.dimension_values]
        self._total_combinations = math.prod(self._radix_sizes)

        self.seed = seed
        self.cycle = cycle

    @classmethod
    def from_scenario_list(
        cls,
        scenario_list: ScenarioList,
        seed: int | None = None,
        cycle: bool = True,
        *,
        dimension_name_field: str = "dimension",
        dimension_values_field: str = "dimension_values",
        dimension_description_field: str | None = None,
        dimension_probs_field: str | None = None,
    ) -> "AgentBlueprint":
        """Create an AgentBlueprint from a ScenarioList with dimension definitions.

        This method performs ETL (Extract, Transform, Load) operations to convert
        a ScenarioList containing dimension definitions into an AgentBlueprint.

        Args:
            scenario_list: ScenarioList where each scenario defines one dimension.
            seed: Optional seed for deterministic iteration order.
            cycle: Whether to cycle through permutations indefinitely.
            dimension_name_field: Field name containing the dimension name (default: "dimension").
            dimension_values_field: Field name containing dimension values (default: "dimension_values").
            dimension_description_field: Optional field name for dimension descriptions.
            dimension_probs_field: Optional field name for probability weights.

        Returns:
            A new AgentBlueprint instance.

        Raises:
            AssertionError: If required fields are missing from scenarios.
            ValueError: If probability data is malformed or misaligned with values.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> scenarios = ScenarioList([
            ...     Scenario({"dimension": "politics", "dimension_values": ["left", "right"]}),
            ...     Scenario({"dimension": "age", "dimension_values": ["young", "old"]})
            ... ])
            >>> blueprint = AgentBlueprint.from_scenario_list(scenarios, seed=42)
            >>> blueprint.dimensions
            ['politics', 'age']
        """
        # Validate required fields
        for scenario in scenario_list:
            assert (
                dimension_name_field in scenario
            ), f"Scenario must have a '{dimension_name_field}' field"
            assert (
                dimension_values_field in scenario
            ), f"Scenario must have a '{dimension_values_field}' field"

        # Build dimension map through ETL process
        dimension_map: dict[str, Dimension] = {}

        for sc in scenario_list:
            dim_name = sc[dimension_name_field]

            # Extract description field
            if dimension_description_field is not None:
                dim_desc = sc.get(dimension_description_field, "")
            else:
                # Fallback order: legacy "dimension_description" then new "dimension_desc"
                dim_desc = sc.get("dimension_description", sc.get("dimension_desc", ""))

            # Extract and transform dimension values
            dim_values_field = sc[dimension_values_field]

            if isinstance(dim_values_field, Dimension):
                # Already a Dimension instance
                dim_obj = dim_values_field
            else:
                # Transform raw values
                # Handle nested lists from collapse() operations
                if (
                    isinstance(dim_values_field, list)
                    and len(dim_values_field) == 1
                    and isinstance(dim_values_field[0], list)
                ):
                    raw_values = dim_values_field[0]
                else:
                    raw_values = dim_values_field  # type: ignore[assignment]

                # Extract and align probability weights if provided
                weighted_values = None
                if dimension_probs_field is not None and dimension_probs_field in sc:
                    probs_field = sc[dimension_probs_field]
                    # Handle nested lists
                    if (
                        isinstance(probs_field, list)
                        and len(probs_field) == 1
                        and isinstance(probs_field[0], list)
                    ):
                        raw_probs = probs_field[0]
                    else:
                        raw_probs = probs_field  # type: ignore[assignment]

                    # Validate alignment
                    if not isinstance(raw_values, list) or not isinstance(raw_probs, list):  # type: ignore[unreachable]
                        raise ValueError(
                            "dimension_values and dimension_probs must be list-like when using separate probability field"
                        )
                    if len(raw_values) != len(raw_probs):
                        raise ValueError(
                            f"Length mismatch for dimension '{dim_name}': {len(raw_values)} values but {len(raw_probs)} probabilities. "
                            f"Values: {raw_values}. Probabilities: {raw_probs}"
                        )

                    # Coerce and validate numeric probabilities
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

                # Construct Dimension object
                dim_obj = Dimension(
                    name=dim_name,
                    description=dim_desc,
                    values=weighted_values if weighted_values is not None else raw_values,  # type: ignore[arg-type]
                )

            dimension_map[dim_name] = dim_obj

        # Create blueprint using clean constructor
        return cls(dimension_map, seed=seed, cycle=cycle)

    def _repr_html_(self) -> str:
        return self.table()._repr_html_()

    def _rich_repr(self) -> str:  # pragma: no cover
        """Return a Rich-formatted representation with dimension details.

        Example output (weights shown only when relevant):

            AgentBlueprint: 3 dimensions, 18 combinations (seed=42, cycle=True)
              - politics [3]: 'left', 'right', 'center'
              - age [3]: '18-25':2, '26-35':3, '36-45':1
              - gender [2]: 'male', 'female'
        """
        from rich.console import Console
        from rich.text import Text
        import io

        output = Text()

        # Header
        output.append("AgentBlueprint(\n", style="bold cyan")
        output.append(f"    num_dimensions={len(self.dimensions)},\n", style="white")
        output.append(
            f"    total_combinations={self._total_combinations},\n", style="white"
        )
        output.append(f"    seed={self.seed},\n", style="white")
        output.append(f"    cycle={self.cycle},\n", style="white")
        output.append("    dimensions:\n", style="white")

        # Dimension details
        for dim_name in self.dimensions:
            dim = self._dimension_map[dim_name]
            # Show weights only if any weight differs from the default 1.0
            show_weights = any(dv.weight != 1.0 for dv in dim.values)

            output.append(f"        {dim_name}", style="bold yellow")
            output.append(f" [{len(dim)}]: ", style="dim")

            if show_weights:
                values_repr = ", ".join(
                    f"{dv.value!r}:{dv.weight:g}" for dv in dim.values
                )
            else:
                values_repr = ", ".join(repr(v) for v in dim.to_plain_list())

            output.append(f"{values_repr}\n", style="white")

            # Show description if available
            if dim.description:
                output.append("            → ", style="green")
                output.append(f"{repr(dim.description)}\n", style="dim")

        output.append(")", style="bold cyan")

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()

    def table(self, *args, **kwargs) -> str:
        """Return a table representation of the blueprint's dimensions.

        Returns:
            A formatted table string showing dimension details.
        """
        from . import ScenarioList, Scenario

        # Build scenarios from dimension map
        new_scenarios = []
        for dim_name in self.dimensions:
            dim = self._dimension_map[dim_name]
            new_scenario = Scenario(
                {
                    "dimension_name": dim_name,
                    "dimension_values": dim.to_plain_list(),
                    "dimension_description": dim.description,
                }
            )
            # Add weights if any are non-default
            if any(dv.weight != 1.0 for dv in dim.values):
                new_scenario["dimension_probs"] = [dv.weight for dv in dim.values]
            new_scenarios.append(new_scenario)

        sl = ScenarioList(new_scenarios)
        return sl.table(*args, **kwargs)

    def to_dict(self, add_edsl_version=False) -> dict:
        """Serialize the AgentBlueprint to a dictionary.

        Args:
            add_edsl_version: If True, include EDSL version information

        Returns:
            dict: Dictionary representation of the AgentBlueprint
        """
        # Serialize dimensions directly
        dimensions_data = {}
        for dim_name, dim in self._dimension_map.items():
            dimensions_data[dim_name] = dim.to_dict(add_edsl_version=False)

        d = {
            "dimensions": dimensions_data,
            "seed": self.seed,
            "cycle": self.cycle,
        }

        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = self.__class__.__name__

        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AgentBlueprint":
        """Create an AgentBlueprint from a dictionary.

        Supports both the new format (with "dimensions" key) and legacy format
        (with "scenario_list" key) for backward compatibility.

        Args:
            d: Dictionary representation of an AgentBlueprint

        Returns:
            AgentBlueprint: A new AgentBlueprint instance
        """
        # Handle new format with direct dimension serialization
        if "dimensions" in d:
            dimension_map = {}
            for dim_name, dim_data in d["dimensions"].items():
                dimension_map[dim_name] = Dimension.from_dict(dim_data)

            return cls(
                dimension_map=dimension_map,
                seed=d.get("seed"),
                cycle=d.get("cycle", True),
            )

        # Legacy format with scenario_list
        elif "scenario_list" in d:
            from .scenario_list import ScenarioList

            scenario_list = ScenarioList.from_dict(d["scenario_list"])

            return cls.from_scenario_list(
                scenario_list=scenario_list,
                seed=d.get("seed"),
                cycle=d.get("cycle", True),
                dimension_name_field=d.get("dimension_name_field", "dimension"),
                dimension_values_field=d.get(
                    "dimension_values_field", "dimension_values"
                ),
                dimension_description_field=d.get("dimension_description_field"),
                dimension_probs_field=d.get("dimension_probs_field"),
            )

        else:
            raise ValueError(
                "Dictionary must contain either 'dimensions' or 'scenario_list' key"
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
        lines.append("blueprint = AgentBlueprint.from_dimensions(")
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

        Each generated agent includes a '_naive_log_probability' trait containing
        the sum of log probabilities for its dimension values.
        """

        from edsl.agents import Agent

        for combo_idx in self._permutation_stream():
            traits = self._index_to_traits(combo_idx)

            # Add the log probability trait (before removing name)
            traits["_naive_log_probability"] = self.naive_log_probability(traits)

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

        Each agent includes a '_naive_log_probability' trait containing the sum of log
        probabilities for its dimension values.

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

        from edsl.agents import Agent, AgentList
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

            # Add the log probability trait (before removing name)
            traits["_naive_log_probability"] = self.naive_log_probability(traits)

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
    ) -> "AgentBlueprint":
        """Create an *AgentBlueprint* directly from one or more :class:`Dimension` objects.

        This is the recommended way to create an AgentBlueprint with explicit dimensions.

        Parameters
        ----------
        *dimensions
            One or more Dimension instances describing the categorical axes.
        seed
            Optional seed for deterministic iteration order.
        cycle
            Whether to cycle through permutations indefinitely.

        Returns
        -------
        AgentBlueprint
            A new blueprint with the specified dimensions.

        Examples
        --------
        >>> from edsl.scenarios import Dimension
        >>> politics = Dimension(name="politics", description="Political leaning", values=["left", "right"])
        >>> age = Dimension(name="age", description="Age group", values=["young", "old"])
        >>> blueprint = AgentBlueprint.from_dimensions(politics, age, seed=42)
        >>> blueprint.dimensions
        ['politics', 'age']
        """
        if not dimensions:
            raise ValueError("At least one Dimension must be provided")

        # Build dimension map directly
        dimension_map = {dim.name: dim for dim in dimensions}

        # Use clean constructor
        return cls(dimension_map, seed=seed, cycle=cycle)

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
        >>> blueprint._total_combinations  # 6 combinations
        6
        >>> blueprint.dimensions
        ['politics', 'age']
        """
        if not dimensions_dict:
            raise ValueError("dimensions_dict cannot be empty")

        dimensions = []
        for name, values in dimensions_dict.items():
            if not isinstance(values, list) or not values:
                raise ValueError(
                    f"Dimension '{name}' must have a non-empty list of values"
                )
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
        >>> blueprint
        AgentBlueprint(dimensions=[politics, age, gender])
        >>> blueprint._total_combinations
        27
        >>> len(blueprint.dimensions)
        3
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

    def drop(self, dimension_name: str) -> "AgentBlueprint":
        """Return a new AgentBlueprint with the specified dimension removed.

        Parameters
        ----------
        dimension_name : str
            The name of the dimension to drop.

        Returns
        -------
        AgentBlueprint
            A new blueprint without the specified dimension.

        Raises
        ------
        ValueError
            If the dimension does not exist in the blueprint.

        Examples
        --------
        >>> blueprint = AgentBlueprint.example()
        >>> blueprint_without_politics = blueprint.drop("politics")
        >>> blueprint_without_politics._total_combinations  # Should be 9 instead of 27
        9
        >>> blueprint_without_politics.dimensions
        ['age', 'gender']
        """
        if dimension_name not in self._dimension_map:
            raise ValueError(
                f"Dimension '{dimension_name}' does not exist in blueprint"
            )

        # Create new dimension map without the dropped dimension
        new_dimension_map = {
            name: dim
            for name, dim in self._dimension_map.items()
            if name != dimension_name
        }

        if not new_dimension_map:
            raise ValueError(
                "Cannot drop the last dimension; blueprint must have at least one dimension"
            )

        # Create new blueprint with filtered dimensions using clean constructor
        return AgentBlueprint(
            new_dimension_map,
            seed=self.seed,
            cycle=self.cycle,
        )

    def add_dimension_value(
        self, dimension_name: str, value, weight: float = 1.0
    ) -> "AgentBlueprint":
        """Return a new AgentBlueprint with a value added to the specified dimension.

        Parameters
        ----------
        dimension_name : str
            The name of the dimension to modify.
        value
            The value to add to the dimension.
        weight : float, default=1.0
            The probability weight for the new value.

        Returns
        -------
        AgentBlueprint
            A new blueprint with the value added to the specified dimension.

        Raises
        ------
        ValueError
            If the dimension does not exist in the blueprint or if the value already exists.

        Examples
        --------
        >>> blueprint = AgentBlueprint.example()
        >>> new_blueprint = blueprint.add_dimension_value("politics", "libertarian")
        >>> new_blueprint._total_combinations  # Should be 36 instead of 27
        36
        """
        if dimension_name not in self._dimension_map:
            raise ValueError(
                f"Dimension '{dimension_name}' does not exist in blueprint"
            )

        old_dimension = self._dimension_map[dimension_name]

        # Check if value already exists
        if value in old_dimension.to_plain_list():
            raise ValueError(
                f"Value {value!r} already exists in dimension '{dimension_name}'"
            )

        # Create new dimension with the added value
        new_values = [(dv.value, dv.weight) for dv in old_dimension.values]
        new_values.append((value, weight))

        new_dimension = Dimension(
            name=old_dimension.name,
            description=old_dimension.description,
            values=new_values,
        )

        # Create new dimension map with the updated dimension
        new_dimension_map = {
            name: (new_dimension if name == dimension_name else dim)
            for name, dim in self._dimension_map.items()
        }

        return AgentBlueprint(
            new_dimension_map,
            seed=self.seed,
            cycle=self.cycle,
        )

    def drop_dimension_value(self, dimension_name: str, value) -> "AgentBlueprint":
        """Return a new AgentBlueprint with a value removed from the specified dimension.

        Parameters
        ----------
        dimension_name : str
            The name of the dimension to modify.
        value
            The value to remove from the dimension.

        Returns
        -------
        AgentBlueprint
            A new blueprint with the value removed from the specified dimension.

        Raises
        ------
        ValueError
            If the dimension does not exist, if the value does not exist in the dimension,
            or if removing the value would leave the dimension empty.

        Examples
        --------
        >>> blueprint = AgentBlueprint.example()
        >>> new_blueprint = blueprint.drop_dimension_value("politics", "center")
        >>> new_blueprint._total_combinations  # Should be 18 instead of 27
        18
        """
        if dimension_name not in self._dimension_map:
            raise ValueError(
                f"Dimension '{dimension_name}' does not exist in blueprint"
            )

        old_dimension = self._dimension_map[dimension_name]

        # Check if value exists
        if value not in old_dimension.to_plain_list():
            raise ValueError(
                f"Value {value!r} does not exist in dimension '{dimension_name}'"
            )

        # Create new dimension without the dropped value
        new_values = [
            (dv.value, dv.weight) for dv in old_dimension.values if dv.value != value
        ]

        if not new_values:
            raise ValueError(
                f"Cannot drop the last value from dimension '{dimension_name}'; dimension must have at least one value"
            )

        new_dimension = Dimension(
            name=old_dimension.name,
            description=old_dimension.description,
            values=new_values,
        )

        # Create new dimension map with the updated dimension
        new_dimension_map = {
            name: (new_dimension if name == dimension_name else dim)
            for name, dim in self._dimension_map.items()
        }

        return AgentBlueprint(
            new_dimension_map,
            seed=self.seed,
            cycle=self.cycle,
        )

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
        from edsl.agents import Agent as _Agent  # type: ignore
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

    def naive_log_probability(self, agent_or_traits) -> float:
        """Compute the log of the naive joint probability of *agent_or_traits*.

        The log probability is obtained by summing the log of the marginal
        probabilities of each dimension value, assuming independence among
        dimensions (i.e., it *ignores* any conditional relationships).

        Parameters
        ----------
        agent_or_traits: Union[edsl.agents.Agent, Mapping[str, Any]]
            Either an :class:`edsl.agents.Agent` instance or a plain mapping that
            contains a key for **every** dimension in this blueprint.
        """
        import math
        from edsl.agents import Agent as _Agent  # type: ignore
        from typing import Mapping, Any

        if isinstance(agent_or_traits, _Agent):
            traits: Mapping[str, Any] = agent_or_traits.traits
        else:
            traits = agent_or_traits  # type: ignore[assignment]

        log_prob = 0.0
        for dim_name, dimension in self._dimension_map.items():
            if dim_name not in traits:
                raise ValueError(
                    f"Traits mapping missing value for dimension '{dim_name}'"
                )
            prob = dimension.probability_of(traits[dim_name])
            log_prob += math.log(prob)

        return log_prob

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the AgentBlueprint.

        Returns:
            str: A string that can be evaluated to recreate the AgentBlueprint
        """
        dims = ", ".join(self.dimensions)
        return f"AgentBlueprint(dimensions=[{dims}])"

    def _summary_repr(self) -> str:
        """Generate a summary representation of the AgentBlueprint with Rich formatting.

        Returns:
            str: A formatted summary representation of the AgentBlueprint
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        output = Text()
        output.append("AgentBlueprint(", style=RICH_STYLES["primary"])
        output.append(
            f"dimensions={len(self.dimensions)}", style=RICH_STYLES["default"]
        )
        output.append(", ", style=RICH_STYLES["default"])
        output.append(
            f"combinations={self._total_combinations}", style=RICH_STYLES["secondary"]
        )
        output.append(")", style=RICH_STYLES["primary"])

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()


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
