"""Interview assignment plans for Jobs.

An assignment plan is the normalized list of source-collection indices that
will be used to construct interviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .exceptions import JobsValueError
from .interview_tuple_filter import InterviewTupleFilter


AXES = ("agent", "scenario", "model")
PLURAL_AXES = {"agents": "agent", "scenarios": "scenario", "models": "model"}


@dataclass(frozen=True)
class AssignmentRow:
    agent_index: int
    scenario_index: int
    model_index: int

    @classmethod
    def from_input(cls, row: Mapping[str, Any] | Sequence[int]) -> "AssignmentRow":
        if isinstance(row, Mapping):
            values = {axis: row.get(axis, row.get(f"{axis}_index")) for axis in AXES}
            missing = [axis for axis, value in values.items() if value is None]
            if missing:
                raise JobsValueError(
                    f"Assignment row is missing index for: {', '.join(missing)}"
                )
            return cls(
                agent_index=cls._validate_index_value(values["agent"], "agent"),
                scenario_index=cls._validate_index_value(
                    values["scenario"], "scenario"
                ),
                model_index=cls._validate_index_value(values["model"], "model"),
            )

        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            raise JobsValueError(
                "Assignment rows must be mappings or 3-item index sequences"
            )
        if len(row) != 3:
            raise JobsValueError("Assignment index sequences must have 3 items")
        return cls(
            agent_index=cls._validate_index_value(row[0], "agent"),
            scenario_index=cls._validate_index_value(row[1], "scenario"),
            model_index=cls._validate_index_value(row[2], "model"),
        )

    @staticmethod
    def _validate_index_value(value: Any, axis: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise JobsValueError(f"Assignment {axis} index must be an integer")
        return value

    def to_dict(self) -> dict[str, int]:
        return {
            "agent": self.agent_index,
            "scenario": self.scenario_index,
            "model": self.model_index,
        }


class AssignmentPlan:
    def __init__(
        self,
        rows: Iterable[AssignmentRow],
        mode: str = "explicit",
        *,
        length: int | None = None,
        materialize: bool = True,
    ):
        self.rows = list(rows) if materialize else rows
        self.mode = mode
        self._length = length

    @classmethod
    def from_explicit(
        cls,
        assignments: Iterable[Mapping[str, Any] | Sequence[int]],
        agents: Sequence[Any],
        scenarios: Sequence[Any],
        models: Sequence[Any],
    ) -> "AssignmentPlan":
        rows = [AssignmentRow.from_input(row) for row in assignments]
        plan = cls(rows, mode="explicit")
        plan.validate(agents, scenarios, models)
        return plan

    @classmethod
    def from_cross(
        cls,
        agents: Sequence[Any],
        scenarios: Sequence[Any],
        models: Sequence[Any],
    ) -> "AssignmentPlan":
        rows = (
            AssignmentRow(agent_index, scenario_index, model_index)
            for agent_index, scenario_index, model_index in product(
                range(len(agents)), range(len(scenarios)), range(len(models))
            )
        )
        return cls(
            rows,
            mode="cross",
            length=len(agents) * len(scenarios) * len(models),
            materialize=False,
        )

    @classmethod
    def from_filter(
        cls,
        agents: Sequence[Any],
        scenarios: Sequence[Any],
        models: Sequence[Any],
        include_expression: str,
    ) -> "AssignmentPlan":
        tuple_filter = InterviewTupleFilter(
            agents,
            scenarios,
            models,
            include_expression,
        )
        rows = (
            AssignmentRow(
                agent._position_index,
                scenario._position_index,
                model._position_index,
            )
            for agent, scenario, model in tuple_filter
        )
        return cls(rows, mode="filtered")

    @classmethod
    def from_zip(
        cls,
        agents: Sequence[Any],
        scenarios: Sequence[Any],
        models: Sequence[Any],
        over: Sequence[str] = ("agents", "scenarios"),
        strict: bool = True,
        cross_remaining: bool = True,
    ) -> "AssignmentPlan":
        axes = tuple(cls._normalize_axis(axis) for axis in over)
        if len(set(axes)) != len(axes):
            raise JobsValueError("zip_assign axes must be unique")
        if not axes:
            raise JobsValueError("zip_assign requires at least one axis")
        if not cross_remaining and set(axes) != set(AXES):
            raise JobsValueError(
                "zip_assign(cross_remaining=False) requires all three axes"
            )

        lengths = {
            "agent": len(agents),
            "scenario": len(scenarios),
            "model": len(models),
        }
        zipped_lengths = [lengths[axis] for axis in axes]
        if strict and len(set(zipped_lengths)) > 1:
            raise JobsValueError("zip_assign strict=True requires equal axis lengths")

        rows: list[AssignmentRow] = []
        remaining_axes = tuple(axis for axis in AXES if axis not in axes)
        zipped_count = min(zipped_lengths)
        remaining_ranges = (
            [range(lengths[axis]) for axis in remaining_axes]
            if cross_remaining
            else [range(1)]
        )
        for zipped_index in range(zipped_count):
            base = {axis: zipped_index for axis in axes}
            for remaining_indices in product(*remaining_ranges):
                values = dict(base)
                values.update(zip(remaining_axes, remaining_indices))
                rows.append(
                    AssignmentRow(
                        values["agent"],
                        values["scenario"],
                        values["model"],
                    )
                )
        return cls(rows, mode="zip")

    @staticmethod
    def _normalize_axis(axis: str) -> str:
        normalized = PLURAL_AXES.get(axis, axis)
        if normalized not in AXES:
            raise JobsValueError(
                f"Unknown assignment axis {axis!r}; expected agents, scenarios, or models"
            )
        return normalized

    def validate(
        self,
        agents: Sequence[Any],
        scenarios: Sequence[Any],
        models: Sequence[Any],
    ) -> None:
        lengths = {
            "agent": len(agents),
            "scenario": len(scenarios),
            "model": len(models),
        }
        for row_number, row in enumerate(self.rows):
            for axis, index in row.to_dict().items():
                if index < 0 or index >= lengths[axis]:
                    raise JobsValueError(
                        f"Assignment row {row_number} has {axis} index {index}, "
                        f"but there are {lengths[axis]} {axis}s"
                    )

    def iter_indices(self) -> Iterator[tuple[int, int, int]]:
        for row in self.rows:
            yield row.agent_index, row.scenario_index, row.model_index

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_mode": self.mode,
            "assignments": [row.to_dict() for row in self.rows],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AssignmentPlan":
        return cls(
            [AssignmentRow.from_input(row) for row in data.get("assignments", [])],
            mode=data.get("assignment_mode", "explicit"),
        )

    def __len__(self) -> int:
        if self._length is not None:
            return self._length
        return len(self.rows)
