"""Serializable causal variables and measurement specifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from edsl.surveys import Survey

VARIABLE_TYPES = frozenset({"continuous", "ordinal", "nominal", "binary", "count"})
VISIBILITIES = frozenset({"private", "public", "system"})


@dataclass(frozen=True)
class ParticipantScope:
    role: str

    def __post_init__(self) -> None:
        if not self.role:
            raise ValueError("participant scope role must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "participant", "role": self.role}


@dataclass(frozen=True)
class ScenarioScope:
    def to_dict(self) -> dict[str, Any]:
        return {"type": "scenario"}


def scope_from_dict(data: Mapping[str, Any]) -> ParticipantScope | ScenarioScope:
    if data.get("type") == "participant":
        return ParticipantScope(str(data["role"]))
    if data.get("type") == "scenario":
        return ScenarioScope()
    raise ValueError(f"unsupported causal variable scope {data.get('type')!r}")


@dataclass(frozen=True)
class Measurement:
    respondent_role: str
    survey: Survey
    field: str
    aggregation: str = "single"
    missing: str = "error"

    def __post_init__(self) -> None:
        if self.aggregation not in {"single", "mean", "median", "minimum", "maximum", "mode", "sum"}:
            raise ValueError(f"unsupported measurement aggregation {self.aggregation!r}")
        if self.missing not in {"error", "allow", "allow_if_not_applicable"}:
            raise ValueError(f"unsupported measurement missing policy {self.missing!r}")
        if not self.respondent_role or not self.field:
            raise ValueError("measurement respondent role and field must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {"respondent_role": self.respondent_role, "survey": self.survey.to_dict(), "field": self.field, "aggregation": self.aggregation, "missing": self.missing}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Measurement":
        return cls(str(data["respondent_role"]), Survey.from_dict(dict(data["survey"])), str(data["field"]), str(data.get("aggregation", "single")), str(data.get("missing", "error")))


@dataclass(frozen=True)
class CausalVariable:
    name: str
    dtype: str
    units: str
    operationalization: str
    levels: tuple[Any, ...] = ()

    kind = "variable"

    def __init__(self, name: str, dtype: str, units: str, operationalization: str, levels: Sequence[Any] = ()):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "dtype", dtype)
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "operationalization", operationalization)
        object.__setattr__(self, "levels", tuple(levels))
        if not name or not units or not operationalization:
            raise ValueError("causal variable name, units, and operationalization must be non-empty")
        if dtype not in VARIABLE_TYPES:
            raise ValueError(f"unsupported causal variable type {dtype!r}")
        if dtype == "binary" and len(self.levels) != 2:
            raise ValueError("binary causal variables require exactly two levels")

    def _base_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "dtype": self.dtype, "units": self.units, "operationalization": self.operationalization, "levels": list(self.levels)}


@dataclass(frozen=True, init=False)
class EndogenousVariable(CausalVariable):
    measurement: Measurement
    kind = "endogenous"

    def __init__(self, name: str, dtype: str, units: str, operationalization: str, measurement: Measurement, levels: Sequence[Any] = ()):
        super().__init__(name, dtype, units, operationalization, levels)
        object.__setattr__(self, "measurement", measurement)

    def to_dict(self) -> dict[str, Any]:
        return {**self._base_dict(), "measurement": self.measurement.to_dict()}


@dataclass(frozen=True, init=False)
class ExogenousVariable(CausalVariable):
    scope: ParticipantScope | ScenarioScope
    visibility: str
    treatments: tuple[Any, ...]
    proxy_attribute: str
    kind = "exogenous"

    def __init__(self, name: str, dtype: str, units: str, operationalization: str, scope: ParticipantScope | ScenarioScope, treatments: Sequence[Any], proxy_attribute: str, *, visibility: str = "private", levels: Sequence[Any] = ()):
        super().__init__(name, dtype, units, operationalization, levels)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "visibility", visibility)
        object.__setattr__(self, "treatments", tuple(treatments))
        object.__setattr__(self, "proxy_attribute", proxy_attribute)
        if visibility not in VISIBILITIES:
            raise ValueError(f"unsupported causal variable visibility {visibility!r}")
        if not self.treatments or not proxy_attribute:
            raise ValueError("exogenous variables require treatments and a proxy attribute")

    def to_dict(self) -> dict[str, Any]:
        return {**self._base_dict(), "scope": self.scope.to_dict(), "visibility": self.visibility, "treatments": list(self.treatments), "proxy_attribute": self.proxy_attribute}


def variable_from_dict(data: Mapping[str, Any]) -> CausalVariable:
    common = dict(name=data["name"], dtype=data["dtype"], units=data["units"], operationalization=data["operationalization"], levels=data.get("levels", ()))
    if data.get("kind") == "endogenous":
        return EndogenousVariable(**common, measurement=Measurement.from_dict(data["measurement"]))
    if data.get("kind") == "exogenous":
        return ExogenousVariable(**common, scope=scope_from_dict(data["scope"]), treatments=data["treatments"], proxy_attribute=data["proxy_attribute"], visibility=data.get("visibility", "private"))
    raise ValueError(f"unsupported causal variable kind {data.get('kind')!r}")
