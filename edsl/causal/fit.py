"""Reproducible fitting for prespecified linear structural equations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import sqrt
from typing import Any, Mapping, Sequence

import numpy as np

from .model import StructuralCausalModel
from .variables import CausalVariable


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class FittedEquation:
    outcome: str
    family: str
    coefficients: Mapping[str, float]
    standard_errors: Mapping[str, float]
    n: int
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome, "family": self.family, "coefficients": dict(self.coefficients), "standard_errors": dict(self.standard_errors), "n": self.n, "rank": self.rank}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FittedEquation":
        return cls(str(data["outcome"]), str(data["family"]), {str(k): float(v) for k, v in data["coefficients"].items()}, {str(k): float(v) for k, v in data["standard_errors"].items()}, int(data["n"]), int(data["rank"]))


@dataclass(frozen=True)
class FittedSCM:
    scm: StructuralCausalModel
    equations: tuple[FittedEquation, ...]
    specification_hash: str
    data_manifest_hash: str
    estimator: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "fitted_scm", "scm": self.scm.to_dict(), "equations": [item.to_dict() for item in self.equations], "specification_hash": self.specification_hash, "data_manifest_hash": self.data_manifest_hash, "estimator": dict(self.estimator)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FittedSCM":
        if data.get("type") != "fitted_scm":
            raise ValueError("not a fitted SCM")
        return cls(StructuralCausalModel.from_dict(data["scm"]), tuple(FittedEquation.from_dict(item) for item in data["equations"]), str(data["specification_hash"]), str(data["data_manifest_hash"]), dict(data["estimator"]))


def _numeric(variable: CausalVariable, value: Any) -> float:
    if variable.dtype in {"continuous", "count"}:
        return float(value)
    if variable.dtype == "binary":
        if value in variable.levels:
            return float(variable.levels.index(value))
        return float(value)
    if variable.dtype in {"ordinal", "nominal"}:
        if value not in variable.levels:
            raise ValueError(f"value {value!r} is not a declared level of {variable.name!r}")
        return float(variable.levels.index(value))
    raise ValueError(f"cannot encode variable type {variable.dtype!r}")


def fit_linear_scm(scm: StructuralCausalModel, observations: Sequence[Mapping[str, Any]], *, covariance: str = "HC3", standardize: bool = False, missing: str = "complete_case_by_equation") -> FittedSCM:
    if not observations:
        raise ValueError("SCM fitting requires observations")
    variables = {item.name: item for item in scm.variables}
    fitted: list[FittedEquation] = []
    for equation in scm.equations:
        required = (equation.outcome, *equation.parents)
        rows = [row for row in observations if all(row.get(name) is not None for name in required)]
        if missing == "error" and len(rows) != len(observations):
            raise ValueError(f"equation {equation.outcome!r} contains missing observations")
        terms = (["intercept"] if equation.include_intercept else []) + list(equation.parents) + [":".join(term) for term in equation.interactions]
        matrix = []
        outcome_values = []
        for row in rows:
            encoded = {name: _numeric(variables[name], row[name]) for name in required}
            values = ([1.0] if equation.include_intercept else []) + [encoded[name] for name in equation.parents] + [float(np.prod([encoded[name] for name in term])) for term in equation.interactions]
            matrix.append(values)
            outcome_values.append(encoded[equation.outcome])
        x = np.asarray(matrix, dtype=float)
        y = np.asarray(outcome_values, dtype=float)
        if len(y) <= x.shape[1]:
            raise ValueError(f"equation {equation.outcome!r} requires more observations than coefficients")
        if standardize:
            start = 1 if equation.include_intercept else 0
            means, scales = x[:, start:].mean(axis=0), x[:, start:].std(axis=0)
            if np.any(scales == 0) or y.std() == 0:
                raise ValueError("cannot standardize constant variables")
            x[:, start:] = (x[:, start:] - means) / scales
            y = (y - y.mean()) / y.std()
        beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
        if rank < x.shape[1]:
            raise ValueError(f"equation {equation.outcome!r} design matrix is rank deficient")
        residual = y - x @ beta
        bread = np.linalg.inv(x.T @ x)
        if covariance == "classical":
            cov = (residual @ residual / (len(y) - x.shape[1])) * bread
        else:
            leverage = np.sum((x @ bread) * x, axis=1)
            adjustment = {"HC0": residual, "HC1": residual * sqrt(len(y) / (len(y) - x.shape[1])), "HC2": residual / np.sqrt(1 - leverage), "HC3": residual / (1 - leverage)}[covariance]
            cov = bread @ (x.T @ ((adjustment**2)[:, None] * x)) @ bread
        fitted.append(FittedEquation(equation.outcome, equation.family, dict(zip(terms, beta.tolist())), dict(zip(terms, np.sqrt(np.maximum(np.diag(cov), 0)).tolist())), len(y), int(rank)))
    estimator = {"family": "linear_scm", "covariance": covariance, "standardize": standardize, "missing": missing}
    return FittedSCM(scm, tuple(fitted), _hash(scm.to_dict()), _hash([dict(row) for row in observations]), estimator)
