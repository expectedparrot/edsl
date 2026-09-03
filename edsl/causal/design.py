"""Deterministic experimental designs generated from causal variables."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
from typing import Any, Mapping, Sequence

from .variables import ExogenousVariable


@dataclass(frozen=True)
class TreatmentCell:
    cell_id: str
    values: Mapping[str, Any]
    replication: int

    def to_dict(self) -> dict[str, Any]:
        return {"cell_id": self.cell_id, "values": dict(self.values), "replication": self.replication}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TreatmentCell":
        return cls(str(data["cell_id"]), dict(data["values"]), int(data["replication"]))


@dataclass(frozen=True)
class ExperimentDesign:
    factors: tuple[str, ...]
    cells: tuple[TreatmentCell, ...]
    seed: str
    method: str = "factorial"

    @classmethod
    def factorial(cls, factors: Sequence[ExogenousVariable], *, replications: int = 1, seed: str = "causal-design", max_cells: int | None = None) -> "ExperimentDesign":
        if not factors or replications < 1:
            raise ValueError("factorial design requires factors and positive replications")
        names = [factor.name for factor in factors]
        if len(names) != len(set(names)):
            raise ValueError("factorial design factors must be unique")
        candidates = [dict(zip(names, values)) for values in product(*(factor.treatments for factor in factors))]
        if max_cells is not None:
            if max_cells < 1:
                raise ValueError("max_cells must be positive")
            candidates = sorted(candidates, key=lambda cell: hashlib.sha256(f"{seed}:{cell!r}".encode()).digest())[:max_cells]
        cells = []
        for values in candidates:
            for replication in range(1, replications + 1):
                digest = hashlib.sha256(f"{seed}:{values!r}:{replication}".encode()).hexdigest()[:16]
                cells.append(TreatmentCell(digest, values, replication))
        return cls(tuple(names), tuple(cells), seed)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "experiment_design", "method": self.method, "factors": list(self.factors), "seed": self.seed, "cells": [cell.to_dict() for cell in self.cells]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExperimentDesign":
        if data.get("type") != "experiment_design":
            raise ValueError("not an experiment design")
        return cls(tuple(data["factors"]), tuple(TreatmentCell.from_dict(item) for item in data["cells"]), str(data["seed"]), str(data.get("method", "factorial")))
