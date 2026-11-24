"""Exact, precomputed treatment assignment schedules for Jobs."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import hashlib
import json
from typing import Any

from .exceptions import JobsValueError


SUPPORTED_UNITS = {
    "agent",
    "agent_model",
    "agent_iteration",
    "agent_model_iteration",
}


@dataclass(frozen=True)
class TreatmentRealization:
    """A persisted condition selection for one logical assignment unit."""

    design_id: str
    assignment_id: str
    assignment_unit: str
    unit_key: str
    condition: str
    scenario_index: int
    balance: str
    schedule_counts: dict[str, int]
    exposure_questions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "design_id": self.design_id,
            "assignment_id": self.assignment_id,
            "assignment_unit": self.assignment_unit,
            "unit_key": self.unit_key,
            "condition": self.condition,
            "scenario_index": self.scenario_index,
            "balance": self.balance,
            "schedule_counts": dict(self.schedule_counts),
            "exposure_questions": list(self.exposure_questions),
        }


@dataclass(frozen=True)
class TreatmentAssignment:
    """A named condition schedule over existing Job scenarios.

    Conditions map to scenario positions in the Jobs scenario list. The schedule
    maps stable unit keys to condition names. This first version accepts an
    explicit schedule only; it does not claim that independent random draws are
    balanced.
    """

    conditions: dict[str, int]
    schedule: dict[str, str]
    unit: str = "agent"
    unit_id_field: str | None = None
    exposure_questions: tuple[str, ...] = ()
    balance: str = "none"
    planned_iterations: int = 1

    def __post_init__(self):
        if not isinstance(self.conditions, dict) or not self.conditions:
            raise JobsValueError("conditions must be a non-empty name-to-index object.")
        if not isinstance(self.schedule, dict) or not self.schedule:
            raise JobsValueError(
                "schedule must be a non-empty unit-key-to-condition object."
            )
        if not isinstance(self.unit, str) or self.unit not in SUPPORTED_UNITS:
            raise JobsValueError(
                f"Unsupported treatment assignment unit {self.unit!r}; "
                f"choose one of {sorted(SUPPORTED_UNITS)}."
            )
        if not isinstance(self.balance, str) or self.balance not in {"none", "exact"}:
            raise JobsValueError("balance must be 'none' or 'exact'.")
        if (
            isinstance(self.planned_iterations, bool)
            or not isinstance(self.planned_iterations, int)
            or self.planned_iterations < 1
        ):
            raise JobsValueError("planned_iterations must be a positive integer.")
        if not all(
            isinstance(name, str)
            and name
            and isinstance(index, int)
            and not isinstance(index, bool)
            for name, index in self.conditions.items()
        ):
            raise JobsValueError(
                "Condition names must be non-empty strings and indices integers."
            )
        if len(set(self.conditions.values())) != len(self.conditions):
            raise JobsValueError(
                "Each treatment condition must map to a distinct scenario."
            )
        if not all(isinstance(key, str) and key for key in self.schedule):
            raise JobsValueError("Schedule unit keys must be non-empty strings.")
        if not all(
            isinstance(condition, str) and condition
            for condition in self.schedule.values()
        ):
            raise JobsValueError("Scheduled condition names must be non-empty strings.")
        unknown = set(self.schedule.values()) - set(self.conditions)
        if unknown:
            raise JobsValueError(
                f"Schedule uses unknown treatment conditions: {sorted(unknown)}."
            )
        if isinstance(self.exposure_questions, str) or not isinstance(
            self.exposure_questions, (list, tuple)
        ):
            raise JobsValueError("exposure_questions must be a list of question names.")
        if self.unit_id_field is not None and (
            not isinstance(self.unit_id_field, str) or not self.unit_id_field
        ):
            raise JobsValueError(
                "unit_id_field must be a non-empty trait name or null."
            )
        if not all(isinstance(name, str) and name for name in self.exposure_questions):
            raise JobsValueError("exposure_questions must contain question names.")
        if len(set(self.exposure_questions)) != len(self.exposure_questions):
            raise JobsValueError("exposure_questions cannot contain duplicates.")

    @cached_property
    def design_id(self) -> str:
        canonical = json.dumps(self.to_dict(include_design_id=False), sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    def to_dict(self, include_design_id: bool = True) -> dict[str, Any]:
        data = {
            "version": 1,
            "conditions": dict(self.conditions),
            "schedule": dict(self.schedule),
            "unit": self.unit,
            "unit_id_field": self.unit_id_field,
            "exposure_questions": list(self.exposure_questions),
            "balance": self.balance,
            "planned_iterations": self.planned_iterations,
        }
        if include_design_id:
            data["design_id"] = self.design_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TreatmentAssignment":
        if (
            not isinstance(data, dict)
            or isinstance(data.get("version"), bool)
            or data.get("version") != 1
        ):
            raise JobsValueError("Unsupported treatment assignment schema version.")
        policy = cls(
            conditions=dict(data.get("conditions", {})),
            schedule=dict(data.get("schedule", {})),
            unit=data.get("unit", "agent"),
            unit_id_field=data.get("unit_id_field"),
            exposure_questions=tuple(data.get("exposure_questions", [])),
            balance=data.get("balance", "none"),
            planned_iterations=data.get("planned_iterations", 1),
        )
        declared_id = data.get("design_id")
        if declared_id is not None and declared_id != policy.design_id:
            raise JobsValueError(
                "Treatment assignment design_id does not match its policy."
            )
        return policy

    def validate_for_job(self, job, iterations: int = 1) -> None:
        # Policy mappings are mutable Python objects; recheck them at execution
        # time in case a caller changed them after the initial validation.
        self.__post_init__()
        # These derived values are reused by every realized unit in this run.
        # Clear prior values because callers may have mutated the public mappings.
        self.__dict__.pop("design_id", None)
        self.__dict__.pop("_condition_counts", None)
        if iterations != self.planned_iterations and self.unit in {
            "agent_iteration",
            "agent_model_iteration",
        }:
            raise JobsValueError(
                f"This schedule covers {self.planned_iterations} iterations, "
                f"but the run requests {iterations}."
            )
        if any(
            index < 0 or index >= len(job.scenarios)
            for index in self.conditions.values()
        ):
            raise JobsValueError(
                "A treatment condition references an unknown scenario index."
            )
        if self.exposure_questions:
            unknown = set(self.exposure_questions) - set(job.survey.question_names)
            if unknown:
                raise JobsValueError(
                    f"Unknown treatment exposure questions: {sorted(unknown)}."
                )
        if job.assignment_plan.mode != "cross":
            raise JobsValueError(
                "Treatment schedules currently require the default Cartesian Jobs "
                "assignment plan. Clear assign(), zip_assign(), or include_when() first."
            )

        if self.unit_id_field:
            agent_keys = [
                self._agent_key(index, agent) for index, agent in enumerate(job.agents)
            ]
            if len(set(agent_keys)) != len(agent_keys):
                raise JobsValueError(
                    f"Agent trait {self.unit_id_field!r} must be unique within the job."
                )

        expected = self.expected_unit_keys(job, iterations)
        actual = set(self.schedule)
        missing = expected - actual
        extra = actual - expected
        if missing or extra:
            details = []
            if missing:
                details.append(
                    f"missing {len(missing)} unit(s), e.g. {sorted(missing)[:3]}"
                )
            if extra:
                details.append(
                    f"unknown {len(extra)} unit(s), e.g. {sorted(extra)[:3]}"
                )
            raise JobsValueError(
                "Treatment schedule does not match Jobs units: " + "; ".join(details)
            )

        if self.balance == "exact":
            counts = {condition: 0 for condition in self.conditions}
            for condition in self.schedule.values():
                counts[condition] += 1
            if len(set(counts.values())) != 1:
                raise JobsValueError(
                    f"Exact balance requires equal assignments per condition; got {counts}."
                )

        _ = self.design_id
        _ = self._condition_counts

    def expected_unit_keys(self, job, iterations: int = 1) -> set[str]:
        return {
            self.unit_key(agent_index, agent, model_index, iteration)
            for agent_index, agent in enumerate(job.agents)
            for model_index, _model in enumerate(job.models)
            for iteration in range(iterations)
        }

    def unit_key(
        self, agent_index: int, agent: Any, model_index: int, iteration: int
    ) -> str:
        agent_key = self._agent_key(agent_index, agent)
        pieces = [f"agent:{agent_key}"]
        if self.unit in {"agent_model", "agent_model_iteration"}:
            pieces.append(f"model:{model_index}")
        if self.unit in {"agent_iteration", "agent_model_iteration"}:
            pieces.append(f"iteration:{iteration}")
        return "|".join(pieces)

    def _agent_key(self, agent_index: int, agent: Any) -> str:
        if not self.unit_id_field:
            return str(agent_index)
        traits = getattr(agent, "traits", {}) or {}
        if self.unit_id_field not in traits:
            raise JobsValueError(
                f"Agent at index {agent_index} has no {self.unit_id_field!r} trait."
            )
        value = traits[self.unit_id_field]
        if value is None:
            raise JobsValueError(
                f"Agent at index {agent_index} has an empty {self.unit_id_field!r} trait."
            )
        return str(value)

    @cached_property
    def _condition_counts(self) -> dict[str, int]:
        counts = {condition: 0 for condition in self.conditions}
        for condition in self.schedule.values():
            counts[condition] += 1
        return counts

    def condition_counts(self) -> dict[str, int]:
        return dict(self._condition_counts)

    def realize(
        self,
        agent_index: int,
        agent: Any,
        model_index: int,
        iteration: int,
    ) -> TreatmentRealization:
        key = self.unit_key(agent_index, agent, model_index, iteration)
        condition = self.schedule[key]
        canonical = f"{self.design_id}:{key}"
        assignment_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
        return TreatmentRealization(
            design_id=self.design_id,
            assignment_id=assignment_id,
            assignment_unit=self.unit,
            unit_key=key,
            condition=condition,
            scenario_index=self.conditions[condition],
            balance=self.balance,
            schedule_counts=self.condition_counts(),
            exposure_questions=list(self.exposure_questions),
        )
