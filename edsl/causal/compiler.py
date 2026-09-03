"""Compile a causal design into durable, role-aware experiment assignments."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from .analysis import CausalAnalysisPlan
from .design import ExperimentDesign
from .variables import ParticipantScope, ScenarioScope


@dataclass(frozen=True)
class AgentRole:
    role: str
    goal: str
    constraint: str
    name_prefix: str | None = None

    def __post_init__(self) -> None:
        if not self.role or not self.goal or not self.constraint:
            raise ValueError("agent role, goal, and constraint must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "goal": self.goal, "constraint": self.constraint, "name_prefix": self.name_prefix}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentRole":
        return cls(str(data["role"]), str(data["goal"]), str(data["constraint"]), data.get("name_prefix"))


@dataclass(frozen=True)
class ParticipantAssignment:
    participant_id: str
    role: str
    traits: Mapping[str, Any]
    private_context: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"participant_id": self.participant_id, "role": self.role, "traits": dict(self.traits), "private_context": dict(self.private_context)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ParticipantAssignment":
        return cls(str(data["participant_id"]), str(data["role"]), dict(data["traits"]), dict(data.get("private_context", {})))

    def to_agent(self):
        """Materialize an EDSL Agent at the compiler boundary."""
        from edsl.agents import Agent
        instructions = [f"Your role is {self.role}.", f"Your goal: {self.traits['goal']}", f"Constraint: {self.traits['constraint']}"]
        instructions.extend(str(value) for value in self.private_context.values())
        return Agent(name=self.participant_id, traits=dict(self.traits), instruction="\n".join(instructions))


@dataclass(frozen=True)
class CompiledReplication:
    instance_id: str
    cell_id: str
    replication: int
    participants: tuple[ParticipantAssignment, ...]
    public_context: Mapping[str, Any]
    system_context: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"instance_id": self.instance_id, "cell_id": self.cell_id, "replication": self.replication, "participants": [item.to_dict() for item in self.participants], "public_context": dict(self.public_context), "system_context": dict(self.system_context)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompiledReplication":
        return cls(str(data["instance_id"]), str(data["cell_id"]), int(data["replication"]), tuple(ParticipantAssignment.from_dict(item) for item in data["participants"]), dict(data.get("public_context", {})), dict(data.get("system_context", {})))


@dataclass(frozen=True)
class MeasurementManifest:
    variable: str
    respondent_role: str
    field: str
    aggregation: str
    missing: str
    survey: Mapping[str, Any]
    dtype: str = "continuous"
    units: str = "unit"
    levels: tuple[Any, ...] = ()
    operationalization: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"variable": self.variable, "respondent_role": self.respondent_role, "field": self.field, "aggregation": self.aggregation, "missing": self.missing, "survey": dict(self.survey), "dtype": self.dtype, "units": self.units, "levels": list(self.levels), "operationalization": self.operationalization}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MeasurementManifest":
        return cls(str(data["variable"]), str(data["respondent_role"]), str(data["field"]), str(data["aggregation"]), str(data["missing"]), dict(data["survey"]), str(data.get("dtype", "continuous")), str(data.get("units", "unit")), tuple(data.get("levels", ())), str(data.get("operationalization", "")))


@dataclass(frozen=True)
class CompiledExperiment:
    study_name: str
    specification_hash: str
    design: ExperimentDesign
    roles: tuple[AgentRole, ...]
    replications: tuple[CompiledReplication, ...]
    measurements: tuple[MeasurementManifest, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"type": "compiled_causal_experiment", "study_name": self.study_name, "specification_hash": self.specification_hash, "design": self.design.to_dict(), "roles": [item.to_dict() for item in self.roles], "replications": [item.to_dict() for item in self.replications], "measurements": [item.to_dict() for item in self.measurements]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompiledExperiment":
        if data.get("type") != "compiled_causal_experiment":
            raise ValueError("not a compiled causal experiment")
        return cls(str(data["study_name"]), str(data["specification_hash"]), ExperimentDesign.from_dict(data["design"]), tuple(AgentRole.from_dict(item) for item in data["roles"]), tuple(CompiledReplication.from_dict(item) for item in data["replications"]), tuple(MeasurementManifest.from_dict(item) for item in data["measurements"]))


class ExperimentCompiler:
    """Mechanically translate a frozen causal plan and design into assignments."""

    def compile(self, *, plan: CausalAnalysisPlan, design: ExperimentDesign, roles: Sequence[AgentRole]) -> CompiledExperiment:
        role_map = {item.role: item for item in roles}
        if len(role_map) != len(roles):
            raise ValueError("experiment roles must be unique")
        if set(design.factors) != {item.name for item in plan.scm.exogenous_variables}:
            raise ValueError("experiment design factors must exactly match SCM exogenous variables")
        required_roles = {item.scope.role for item in plan.scm.exogenous_variables if isinstance(item.scope, ParticipantScope)} | {item.measurement.respondent_role for item in plan.scm.endogenous_variables}
        missing_roles = required_roles - set(role_map)
        if missing_roles:
            raise ValueError(f"experiment is missing roles required by the SCM: {sorted(missing_roles)}")
        spec_hash = hashlib.sha256(json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        replications = []
        variables = {item.name: item for item in plan.scm.exogenous_variables}
        for cell in design.cells:
            public_context: dict[str, Any] = {}
            system_context: dict[str, Any] = dict(cell.values)
            private_by_role: dict[str, dict[str, Any]] = {role: {} for role in role_map}
            for name, value in cell.values.items():
                variable = variables[name]
                rendered = variable.proxy_attribute.replace("{{ value }}", str(value))
                if isinstance(variable.scope, ScenarioScope):
                    if variable.visibility == "private":
                        raise ValueError(f"scenario variable {name!r} cannot have private visibility without an owning role")
                    (public_context if variable.visibility == "public" else system_context)[name] = value
                    if variable.visibility == "public":
                        public_context[f"{name}_instruction"] = rendered
                elif variable.visibility == "private":
                    private_by_role[variable.scope.role][name] = rendered
                elif variable.visibility == "public":
                    public_context[name] = value
                    public_context[f"{name}_instruction"] = rendered
            participants = []
            for role_name, role in role_map.items():
                prefix = role.name_prefix or role_name.replace(" ", "-")
                participant_id = f"{prefix}-{cell.cell_id}"
                participants.append(ParticipantAssignment(participant_id, role_name, {"role": role_name, "goal": role.goal, "constraint": role.constraint, "cell_id": cell.cell_id, "replication": cell.replication}, private_by_role[role_name]))
            instance_id = f"{plan.scm.name}-{cell.cell_id}"
            replications.append(CompiledReplication(instance_id, cell.cell_id, cell.replication, tuple(participants), public_context, system_context))
        measurements = tuple(MeasurementManifest(item.name, item.measurement.respondent_role, item.measurement.field, item.measurement.aggregation, item.measurement.missing, item.measurement.survey.to_dict(), item.dtype, item.units, item.levels, item.operationalization) for item in plan.scm.endogenous_variables)
        return CompiledExperiment(plan.scm.name, spec_hash, design, tuple(roles), tuple(replications), measurements)
