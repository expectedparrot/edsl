"""Serializable estimands and prespecified causal analysis plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import StructuralCausalModel
from .variables import CausalVariable


@dataclass(frozen=True)
class PathEffect:
    cause: str
    outcome: str

    def __init__(self, cause: str | CausalVariable, outcome: str | CausalVariable):
        object.__setattr__(self, "cause", cause.name if isinstance(cause, CausalVariable) else str(cause))
        object.__setattr__(self, "outcome", outcome.name if isinstance(outcome, CausalVariable) else str(outcome))
        if not self.cause or not self.outcome or self.cause == self.outcome:
            raise ValueError("path effect requires distinct cause and outcome")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "path_effect", "cause": self.cause, "outcome": self.outcome}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PathEffect":
        return cls(data["cause"], data["outcome"])


@dataclass(frozen=True)
class EstimatorSpec:
    family: str = "linear_scm"
    standardize: bool = False
    covariance: str = "HC3"

    def __post_init__(self) -> None:
        if self.family not in {"linear_scm"}:
            raise ValueError(f"unsupported causal estimator {self.family!r}")
        if self.covariance not in {"classical", "HC0", "HC1", "HC2", "HC3"}:
            raise ValueError(f"unsupported covariance estimator {self.covariance!r}")

    def to_dict(self) -> dict[str, Any]:
        return {"family": self.family, "standardize": self.standardize, "covariance": self.covariance}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EstimatorSpec":
        return cls(str(data.get("family", "linear_scm")), bool(data.get("standardize", False)), str(data.get("covariance", "HC3")))


@dataclass(frozen=True)
class CausalAnalysisPlan:
    scm: StructuralCausalModel
    estimands: tuple[PathEffect, ...]
    estimator: EstimatorSpec = EstimatorSpec()
    missing: str = "complete_case_by_equation"
    multiplicity: str = "report_all"

    def __init__(self, scm: StructuralCausalModel, estimands: Sequence[PathEffect], estimator: EstimatorSpec | None = None, *, missing: str = "complete_case_by_equation", multiplicity: str = "report_all"):
        object.__setattr__(self, "scm", scm)
        object.__setattr__(self, "estimands", tuple(estimands))
        object.__setattr__(self, "estimator", estimator or EstimatorSpec())
        object.__setattr__(self, "missing", missing)
        object.__setattr__(self, "multiplicity", multiplicity)
        paths = {(parent, equation.outcome) for equation in scm.equations for parent in equation.parents}
        if not self.estimands or any((item.cause, item.outcome) not in paths for item in self.estimands):
            raise ValueError("every estimand must name a direct path in the SCM")
        if missing not in {"complete_case_by_equation", "error"}:
            raise ValueError(f"unsupported missing-data policy {missing!r}")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "causal_analysis_plan", "scm": self.scm.to_dict(), "estimands": [item.to_dict() for item in self.estimands], "estimator": self.estimator.to_dict(), "missing": self.missing, "multiplicity": self.multiplicity}

    def fit(self, observations: Sequence[Mapping[str, Any]]):
        """Fit the frozen plan without an LLM or workflow dependency."""
        from .fit import fit_linear_scm
        return fit_linear_scm(self.scm, observations, covariance=self.estimator.covariance, standardize=self.estimator.standardize, missing=self.missing)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CausalAnalysisPlan":
        if data.get("type") != "causal_analysis_plan":
            raise ValueError("not a causal analysis plan")
        return cls(StructuralCausalModel.from_dict(data["scm"]), [PathEffect.from_dict(item) for item in data["estimands"]], EstimatorSpec.from_dict(data["estimator"]), missing=str(data.get("missing", "complete_case_by_equation")), multiplicity=str(data.get("multiplicity", "report_all")))
