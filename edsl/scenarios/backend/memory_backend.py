# memory_backend.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .ops import State, materialize


@dataclass
class MemoryState(State):
    meta: dict = field(default_factory=dict)
    scenarios: List[dict] = field(default_factory=list)
    overrides: Dict[int, dict] = field(default_factory=dict)

    def get_meta(self) -> dict:
        return self.meta

    def set_meta(self, meta: dict) -> None:
        self.meta = meta

    def get_length(self) -> int:
        return len(self.scenarios)

    def insert_scenario(self, position: int, payload: dict) -> None:
        # append-only in this demo: position must be at end
        assert position == len(self.scenarios)
        self.scenarios.append(payload)

    def get_scenario(self, position: int) -> Any:
        return self.scenarios[position]

    def get_all_scenarios(self) -> List[Any]:
        return list(self.scenarios)

    def set_override(self, position: int, payload: dict) -> None:
        self.overrides[position] = payload

    def get_override(self, position: int) -> dict | None:
        return self.overrides.get(position)

    def get_materialized_scenario(self, position: int) -> dict:
        raw = self.get_scenario(position)
        override = self.get_override(position)
        return materialize(raw, self.meta, override)

    def get_all_materialized_scenarios(self) -> List[dict]:
        return [self.get_materialized_scenario(i) for i in range(len(self.scenarios))]
