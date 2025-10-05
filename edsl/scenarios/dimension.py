from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, List, Sequence, Tuple, TypeVar, Union, overload, Optional
import random

T = TypeVar("T")


@dataclass
class DimensionValue(Generic[T]):
    """Represents a single value for a :class:`Dimension` with an optional probability *weight*.

    Attributes
    ----------
    value: T
        The concrete value for the dimension (e.g., ``"male"`` or ``42``).
    weight: float, default=1.0
        A non-negative weight expressing the relative probability of this value when
        random sampling is desired.  Weights are *relative* – they do **not** need
        to sum to 1.  A weight of ``0.0`` means the value will never be sampled.
    """

    value: T
    weight: float = 1.0

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ValueError("weight must be non-negative")


@dataclass
class Dimension(Generic[T]):
    """A helper class capturing a **dimension** used when generating agents.

    A *dimension* is defined by a ``name`` (e.g., ``"age"``), a free-text
    ``description`` (e.g., "Age bracket in years"), and a finite set of
    admissible ``values``.  Each value can optionally carry a *weight* that is
    utilised when *random* values need to be drawn from the dimension.

    Examples
    --------
    >>> dim = Dimension(
    ...     name="politics",
    ...     description="Political leaning on the left/right spectrum",
    ...     values=[
    ...         ("left", 1),
    ...         ("right", 1),
    ...         ("center", 2),  # twice as likely
    ...     ],
    ... )
    >>> import random
    >>> rng = random.Random(42)
    >>> dim.sample(rng=rng)
    'center'
    """

    name: str
    description: str
    values: List[DimensionValue[T]] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    @overload
    def __init__(self, *, name: str, description: str, values: Sequence[T]): ...

    @overload
    def __init__(
        self, *, name: str, description: str, values: Sequence[Tuple[T, float]]
    ): ...

    def __init__(
        self,
        *,
        name: str,
        description: str,
        values: Sequence[Union[T, Tuple[T, float]]],
    ):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", description)

        dim_values: List[DimensionValue[T]] = []
        for v in values:
            if isinstance(v, tuple):
                # Only treat as a weighted pair when the second element is numeric.
                if len(v) == 2 and isinstance(v[1], (int, float)):
                    value, weight = v  # type: ignore[misc]
                    dim_values.append(DimensionValue(value=value, weight=float(weight)))
                else:
                    # Treat arbitrary tuples as a single categorical value.
                    dim_values.append(DimensionValue(value=v))
            else:
                dim_values.append(DimensionValue(value=v))

        object.__setattr__(self, "values", dim_values)

        if not self.values:
            raise ValueError("Dimension must contain at least one value")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def to_plain_list(self) -> List[T]:
        """Return the dimension values as a plain list (weights discarded)."""
        return [dv.value for dv in self.values]

    def sample(
        self, *, k: int = 1, rng: Optional[random.Random] = None
    ) -> Union[T, List[T]]:
        """Randomly sample *k* value(s) according to the weights.

        Parameters
        ----------
        k: int, default=1
            Number of samples to draw.  When *k* == 1 the single sampled value is
            returned directly; otherwise a list of length *k* is returned.
        rng: random.Random, optional
            A pre-seeded :pyclass:`random.Random` instance to control
            determinism.  When *None* the global RNG is used.
        """
        _rng = rng or random
        population = [dv.value for dv in self.values]
        weights = [dv.weight for dv in self.values]
        samples = _rng.choices(population, weights=weights, k=k)
        return samples[0] if k == 1 else samples

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------
    def __iter__(self):
        """Iterate over the underlying :class:`DimensionValue` objects."""
        return iter(self.values)

    def __len__(self):
        return len(self.values)

    def __repr__(self) -> str:  # pragma: no cover
        vals_repr = ", ".join(
            f"{dv.value!r}:{dv.weight}" if dv.weight != 1.0 else repr(dv.value)
            for dv in self.values
        )
        return f"Dimension(name={self.name!r}, values=[{vals_repr}])"

    # ------------------------------------------------------------------
    # Probability helpers
    # ------------------------------------------------------------------

    @property
    def total_weight(self) -> float:
        """Return the sum of all value weights."""
        return sum(dv.weight for dv in self.values)

    def probability_of(self, value: T) -> float:
        """Return the *marginal* probability of *value* under this dimension.

        The probability is computed as ``weight(value) / total_weight``.
        Raises ``ValueError`` if the value is not found.
        """
        total = self.total_weight
        for dv in self.values:
            if dv.value == value:
                return dv.weight / total if total > 0 else 0.0
        raise ValueError(
            f"{value!r} is not a valid option for dimension '{self.name}'."
        )
