"""Structural causal model specification and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .variables import CausalVariable, EndogenousVariable, ExogenousVariable, variable_from_dict

EQUATION_FAMILIES = frozenset({"linear", "linear_probability", "logit", "probit", "poisson", "ordinal_logit"})


@dataclass(frozen=True)
class Equation:
    outcome: str
    parents: tuple[str, ...]
    family: str = "linear"
    interactions: tuple[tuple[str, ...], ...] = ()
    include_intercept: bool = True

    def __init__(self, outcome: str | CausalVariable, parents: Sequence[str | CausalVariable], family: str = "linear", interactions: Sequence[Sequence[str | CausalVariable]] = (), include_intercept: bool = True):
        object.__setattr__(self, "outcome", outcome.name if isinstance(outcome, CausalVariable) else str(outcome))
        object.__setattr__(self, "parents", tuple(item.name if isinstance(item, CausalVariable) else str(item) for item in parents))
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "interactions", tuple(tuple(item.name if isinstance(item, CausalVariable) else str(item) for item in term) for term in interactions))
        object.__setattr__(self, "include_intercept", include_intercept)
        if family not in EQUATION_FAMILIES:
            raise ValueError(f"unsupported equation family {family!r}")
        if not self.outcome or not self.parents or len(set(self.parents)) != len(self.parents):
            raise ValueError("equation requires an outcome and unique parents")

    def to_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "parents": list(self.parents), "family": self.family, "interactions": [list(term) for term in self.interactions], "include_intercept": self.include_intercept}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Equation":
        return cls(data["outcome"], data["parents"], data.get("family", "linear"), data.get("interactions", ()), bool(data.get("include_intercept", True)))


@dataclass(frozen=True)
class StructuralCausalModel:
    variables: tuple[CausalVariable, ...]
    equations: tuple[Equation, ...]
    name: str = "causal-model"
    metadata: Mapping[str, Any] | None = None

    def __init__(self, variables: Sequence[CausalVariable], equations: Sequence[Equation], name: str = "causal-model", metadata: Mapping[str, Any] | None = None):
        object.__setattr__(self, "variables", tuple(variables))
        object.__setattr__(self, "equations", tuple(equations))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "metadata", dict(metadata or {}))
        self._validate()

    def _validate(self) -> None:
        names = [item.name for item in self.variables]
        if not names or len(names) != len(set(names)):
            raise ValueError("SCM variable names must be nonempty and unique")
        by_name = {item.name: item for item in self.variables}
        outcomes = [item.outcome for item in self.equations]
        if len(outcomes) != len(set(outcomes)):
            raise ValueError("each SCM outcome may have at most one equation")
        for equation in self.equations:
            if equation.outcome not in by_name or any(parent not in by_name for parent in equation.parents):
                raise ValueError(f"equation for {equation.outcome!r} references an unknown variable")
            if not isinstance(by_name[equation.outcome], EndogenousVariable):
                raise ValueError("equation outcomes must be endogenous variables")
            if equation.outcome in equation.parents:
                raise ValueError("SCM equations cannot contain self-cycles")
            if any(any(name not in equation.parents for name in term) or len(term) < 2 for term in equation.interactions):
                raise ValueError("interaction terms must contain at least two declared parents")
        graph = {name: set() for name in names}
        for equation in self.equations:
            for parent in equation.parents:
                graph[parent].add(equation.outcome)
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(name: str) -> None:
            if name in visiting:
                raise ValueError("SCM causal graph must be acyclic")
            if name in visited:
                return
            visiting.add(name)
            for child in graph[name]:
                visit(child)
            visiting.remove(name)
            visited.add(name)
        for name in names:
            visit(name)

    @property
    def exogenous_variables(self) -> tuple[ExogenousVariable, ...]:
        return tuple(item for item in self.variables if isinstance(item, ExogenousVariable))

    @property
    def endogenous_variables(self) -> tuple[EndogenousVariable, ...]:
        return tuple(item for item in self.variables if isinstance(item, EndogenousVariable))

    def to_dict(self) -> dict[str, Any]:
        return {"type": "structural_causal_model", "name": self.name, "variables": [item.to_dict() for item in self.variables], "equations": [item.to_dict() for item in self.equations], "metadata": dict(self.metadata or {})}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StructuralCausalModel":
        if data.get("type") != "structural_causal_model":
            raise ValueError("not a structural causal model")
        return cls([variable_from_dict(item) for item in data["variables"]], [Equation.from_dict(item) for item in data["equations"]], str(data.get("name", "causal-model")), data.get("metadata"))
