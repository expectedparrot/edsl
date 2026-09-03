"""Serializable blueprints joining causal design, interaction, and execution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import prod
from typing import Any, Mapping, Sequence

from edsl.conversations import Conversation

from .analysis import CausalAnalysisPlan
from .compiler import AgentRole, CompiledExperiment, CompiledReplication, ExperimentCompiler, ParticipantAssignment
from .design import ExperimentDesign


@dataclass(frozen=True)
class ResearchQuestion:
    question: str
    population: str
    setting: str
    hypotheses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "hypotheses", tuple(str(item) for item in self.hypotheses))
        if not self.question.strip() or not self.population.strip() or not self.setting.strip():
            raise ValueError("research question, population, and setting must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        return {"question": self.question, "population": self.population, "setting": self.setting, "hypotheses": list(self.hypotheses)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResearchQuestion":
        return cls(str(data["question"]), str(data["population"]), str(data["setting"]), tuple(str(item) for item in data.get("hypotheses", ())))


@dataclass(frozen=True)
class ExecutionChannel:
    kind: str
    options: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"llm", "human", "service"}:
            raise ValueError(f"unsupported execution channel {self.kind!r}")
        object.__setattr__(self, "options", dict(self.options or {}))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "options": dict(self.options or {})}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExecutionChannel":
        return cls(str(data["kind"]), data.get("options"))


@dataclass(frozen=True)
class StudyRole:
    role: str
    goal: str
    constraints: tuple[str, ...]
    execution: ExecutionChannel
    name_prefix: str | None = None

    def __init__(self, role: str, goal: str, constraints: Sequence[str], execution: ExecutionChannel, name_prefix: str | None = None):
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "goal", goal)
        object.__setattr__(self, "constraints", tuple(str(item) for item in constraints))
        object.__setattr__(self, "execution", execution)
        object.__setattr__(self, "name_prefix", name_prefix)
        if not role.strip() or not goal.strip() or not self.constraints or any(not item.strip() for item in self.constraints):
            raise ValueError("study role, goal, and constraints must be non-empty")

    def to_agent_role(self) -> AgentRole:
        return AgentRole(self.role, self.goal, "\n".join(self.constraints), self.name_prefix)

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "goal": self.goal, "constraints": list(self.constraints), "execution": self.execution.to_dict(), "name_prefix": self.name_prefix}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StudyRole":
        return cls(str(data["role"]), str(data["goal"]), data["constraints"], ExecutionChannel.from_dict(data["execution"]), data.get("name_prefix"))


@dataclass(frozen=True)
class InformationPolicy:
    variable: str
    visibility: str
    audience: tuple[str, ...] = ()

    def __init__(self, variable: str, visibility: str, audience: Sequence[str] = ()):
        object.__setattr__(self, "variable", variable)
        object.__setattr__(self, "visibility", visibility)
        object.__setattr__(self, "audience", tuple(str(item) for item in audience))
        if not variable or visibility not in {"private", "shared", "public", "system"}:
            raise ValueError("information policy requires a variable and supported visibility")

    def to_dict(self) -> dict[str, Any]:
        return {"variable": self.variable, "visibility": self.visibility, "audience": list(self.audience)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "InformationPolicy":
        return cls(str(data["variable"]), str(data["visibility"]), data.get("audience", ()))


@dataclass(frozen=True)
class DesignPolicy:
    method: str = "factorial"
    replications: int = 1
    seed: str = "causal-blueprint"
    max_cells: int | None = None

    def __post_init__(self) -> None:
        if self.replications < 1 or not self.seed or (self.max_cells is not None and self.max_cells < 1):
            raise ValueError("design requires positive replications, a seed, and a positive max_cells when supplied")

    def to_dict(self) -> dict[str, Any]:
        return {"method": self.method, "replications": self.replications, "seed": self.seed, "max_cells": self.max_cells}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DesignPolicy":
        return cls(str(data.get("method", "factorial")), int(data.get("replications", 1)), str(data.get("seed", "causal-blueprint")), data.get("max_cells"))


@dataclass(frozen=True)
class ProcedureRequirement:
    kind: str
    options: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", dict(self.options or {}))

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "options": dict(self.options or {})}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProcedureRequirement":
        return cls(str(data["kind"]), data.get("options"))


@dataclass(frozen=True)
class ValidationFinding:
    severity: str
    code: str
    path: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {"severity": self.severity, "code": self.code, "path": self.path, "message": self.message}
        if self.suggestion:
            data["suggestion"] = self.suggestion
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ValidationFinding":
        return cls(str(data["severity"]), str(data["code"]), str(data["path"]), str(data["message"]), data.get("suggestion"))


@dataclass(frozen=True)
class BlueprintValidation:
    findings: tuple[ValidationFinding, ...]
    projected_runs: int

    @property
    def is_valid(self) -> bool:
        return not any(item.severity == "error" for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "blueprint_validation", "valid": self.is_valid, "projected_runs": self.projected_runs, "findings": [item.to_dict() for item in self.findings]}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BlueprintValidation":
        if data.get("type") != "blueprint_validation":
            raise ValueError("not a blueprint validation")
        return cls(tuple(ValidationFinding.from_dict(item) for item in data.get("findings", ())), int(data["projected_runs"]))


@dataclass(frozen=True)
class CausalStudyBlueprint:
    name: str
    research_question: ResearchQuestion
    analysis_plan: CausalAnalysisPlan
    roles: tuple[StudyRole, ...]
    information: tuple[InformationPolicy, ...]
    design: DesignPolicy
    interaction: Conversation
    procedure_requirements: tuple[ProcedureRequirement, ...] = ()
    metadata: Mapping[str, Any] | None = None
    schema_version: int = 1

    def __init__(self, name: str, research_question: ResearchQuestion, analysis_plan: CausalAnalysisPlan, roles: Sequence[StudyRole], information: Sequence[InformationPolicy], design: DesignPolicy, interaction: Conversation, procedure_requirements: Sequence[ProcedureRequirement] = (), metadata: Mapping[str, Any] | None = None, schema_version: int = 1):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "research_question", research_question)
        object.__setattr__(self, "analysis_plan", analysis_plan)
        object.__setattr__(self, "roles", tuple(roles))
        object.__setattr__(self, "information", tuple(information))
        object.__setattr__(self, "design", design)
        object.__setattr__(self, "interaction", interaction)
        object.__setattr__(self, "procedure_requirements", tuple(procedure_requirements))
        object.__setattr__(self, "metadata", dict(metadata or {}))
        object.__setattr__(self, "schema_version", schema_version)
        if not name or schema_version != 1:
            raise ValueError("blueprint requires a name and supported schema_version 1")

    def to_dict(self) -> dict[str, Any]:
        return {"type": "causal_study_blueprint", "schema_version": self.schema_version, "name": self.name, "research_question": self.research_question.to_dict(), "analysis_plan": self.analysis_plan.to_dict(), "roles": [item.to_dict() for item in self.roles], "information": [item.to_dict() for item in self.information], "design": self.design.to_dict(), "interaction": self.interaction.to_dict(), "procedure_requirements": [item.to_dict() for item in self.procedure_requirements], "metadata": dict(self.metadata or {})}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CausalStudyBlueprint":
        if data.get("type") != "causal_study_blueprint":
            raise ValueError("not a causal study blueprint")
        return cls(str(data["name"]), ResearchQuestion.from_dict(data["research_question"]), CausalAnalysisPlan.from_dict(data["analysis_plan"]), [StudyRole.from_dict(item) for item in data["roles"]], [InformationPolicy.from_dict(item) for item in data["information"]], DesignPolicy.from_dict(data["design"]), Conversation.from_dict(data["interaction"]), [ProcedureRequirement.from_dict(item) for item in data.get("procedure_requirements", ())], data.get("metadata"), int(data.get("schema_version", 1)))

    @property
    def specification_hash(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def validate(self, *, large_run_threshold: int = 10_000) -> BlueprintValidation:
        findings: list[ValidationFinding] = []
        role_names = [item.role for item in self.roles]
        role_set = set(role_names)
        if len(role_names) != len(role_set):
            findings.append(ValidationFinding("error", "duplicate-role", "$.roles", "Study role names must be unique."))
        required = {item.measurement.respondent_role for item in self.analysis_plan.scm.endogenous_variables}
        required |= {getattr(item.scope, "role", None) for item in self.analysis_plan.scm.exogenous_variables}
        required.discard(None)
        for role in sorted(required - role_set):
            findings.append(ValidationFinding("error", "missing-role", "$.roles", f"SCM references undeclared role {role!r}."))
        interaction_roles = set(self.interaction.roles)
        if not interaction_roles.issubset(role_set):
            findings.append(ValidationFinding("error", "interaction-role-mismatch", "$.interaction.roles", f"Interaction references undeclared roles: {sorted(interaction_roles - role_set)}."))
        variable_names = {item.name for item in self.analysis_plan.scm.exogenous_variables}
        policies: dict[str, list[tuple[int, InformationPolicy]]] = {}
        for index, policy in enumerate(self.information):
            policies.setdefault(policy.variable, []).append((index, policy))
            path = f"$.information[{index}]"
            if policy.variable not in variable_names:
                findings.append(ValidationFinding("error", "unknown-information-variable", path + ".variable", f"Unknown exogenous variable {policy.variable!r}."))
            invalid = set(policy.audience) - role_set
            if invalid:
                findings.append(ValidationFinding("error", "invalid-information-audience", path + ".audience", f"Unknown audience roles: {sorted(invalid)}."))
            count = len(set(policy.audience))
            valid_cardinality = (policy.visibility == "private" and count == 1) or (policy.visibility == "shared" and count >= 2) or (policy.visibility in {"public", "system"} and count == 0)
            if not valid_cardinality:
                findings.append(ValidationFinding("error", "invalid-information-cardinality", path + ".audience", f"Visibility {policy.visibility!r} has an invalid audience cardinality."))
        for name in sorted(variable_names):
            if name not in policies:
                findings.append(ValidationFinding("error", "missing-information-policy", "$.information", f"Variable {name!r} has no information policy."))
            elif len(policies[name]) > 1:
                findings.append(ValidationFinding("error", "duplicate-information-policy", "$.information", f"Variable {name!r} has multiple information policies."))
        if self.design.method != "factorial":
            findings.append(ValidationFinding("error", "unsupported-design-method", "$.design.method", f"Design method {self.design.method!r} is not implemented."))
        factors = self.analysis_plan.scm.exogenous_variables
        for index, factor in enumerate(factors):
            if len(set(map(repr, factor.treatments))) < 2:
                findings.append(ValidationFinding("warning", "constant-factor", f"$.analysis_plan.scm.variables[{index}].treatments", f"Factor {factor.name!r} does not vary."))
        factorial_cells = prod(len(item.treatments) for item in factors) if factors else 0
        selected_cells = min(factorial_cells, self.design.max_cells) if self.design.max_cells is not None else factorial_cells
        projected_runs = selected_cells * self.design.replications
        if self.design.max_cells is not None and self.design.max_cells < factorial_cells:
            findings.append(ValidationFinding("warning", "design-truncated", "$.design.max_cells", f"The factorial has {factorial_cells} cells; a stable subset of {self.design.max_cells} will be used."))
        if projected_runs > large_run_threshold:
            findings.append(ValidationFinding("warning", "design-too-large", "$.design", f"The design projects {projected_runs} runs before retries."))
        parameters = max((len(eq.parents) + int(eq.include_intercept) + len(eq.interactions) for eq in self.analysis_plan.scm.equations), default=0)
        if projected_runs <= parameters:
            findings.append(ValidationFinding("error", "insufficient-observations", "$.design", f"Projected runs ({projected_runs}) do not exceed the largest equation parameter count ({parameters})."))
        for index, requirement in enumerate(self.procedure_requirements):
            findings.append(ValidationFinding("error", "unsupported-procedure-requirement", f"$.procedure_requirements[{index}]", f"Procedure requirement {requirement.kind!r} is not implemented."))
        return BlueprintValidation(tuple(findings), projected_runs)


@dataclass(frozen=True)
class CompiledCausalStudy:
    blueprint_hash: str
    experiment: CompiledExperiment
    interaction: Conversation
    execution_channels: Mapping[str, ExecutionChannel]
    validation: BlueprintValidation

    def to_dict(self) -> dict[str, Any]:
        return {"type": "compiled_causal_study", "blueprint_hash": self.blueprint_hash, "experiment": self.experiment.to_dict(), "interaction": self.interaction.to_dict(), "execution_channels": {role: channel.to_dict() for role, channel in self.execution_channels.items()}, "validation": self.validation.to_dict()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CompiledCausalStudy":
        if data.get("type") != "compiled_causal_study":
            raise ValueError("not a compiled causal study")
        return cls(str(data["blueprint_hash"]), CompiledExperiment.from_dict(data["experiment"]), Conversation.from_dict(data["interaction"]), {str(role): ExecutionChannel.from_dict(channel) for role, channel in data["execution_channels"].items()}, BlueprintValidation.from_dict(data["validation"]))


class BlueprintCompiler:
    """Validate and deterministically compile a causal study blueprint."""

    def compile(self, blueprint: CausalStudyBlueprint) -> CompiledCausalStudy:
        validation = blueprint.validate()
        if not validation.is_valid:
            codes = [item.code for item in validation.findings if item.severity == "error"]
            raise ValueError(f"invalid causal study blueprint: {codes}")
        factors = blueprint.analysis_plan.scm.exogenous_variables
        design = ExperimentDesign.factorial(factors, replications=blueprint.design.replications, seed=blueprint.design.seed, max_cells=blueprint.design.max_cells)
        # Information access belongs to the blueprint, not to the legacy
        # visibility field on an SCM variable. Compile every assignment as
        # system-only first, then distribute only what policy permits.
        compiler_plan_data = blueprint.analysis_plan.to_dict()
        for variable in compiler_plan_data["scm"]["variables"]:
            if variable.get("kind") == "exogenous":
                variable["visibility"] = "system"
        compiler_plan = CausalAnalysisPlan.from_dict(compiler_plan_data)
        experiment = ExperimentCompiler().compile(plan=compiler_plan, design=design, roles=[item.to_agent_role() for item in blueprint.roles])
        policy_by_variable = {item.variable: item for item in blueprint.information}
        variables = {item.name: item for item in factors}
        rewritten = []
        for replication in experiment.replications:
            public_context: dict[str, Any] = {}
            private_by_role: dict[str, dict[str, Any]] = {item.role: {} for item in blueprint.roles}
            for name, value in replication.system_context.items():
                if name not in variables:
                    continue
                variable = variables[name]
                policy = policy_by_variable[name]
                rendered = variable.proxy_attribute.replace("{{ value }}", str(value))
                if policy.visibility == "public":
                    public_context[name] = value
                    public_context[f"{name}_instruction"] = rendered
                elif policy.visibility in {"private", "shared"}:
                    for role in policy.audience:
                        private_by_role[role][name] = rendered
            participants = tuple(ParticipantAssignment(item.participant_id, item.role, item.traits, private_by_role[item.role]) for item in replication.participants)
            rewritten.append(CompiledReplication(replication.instance_id, replication.cell_id, replication.replication, participants, public_context, replication.system_context))
        experiment = CompiledExperiment(blueprint.name, blueprint.specification_hash, experiment.design, experiment.roles, tuple(rewritten), experiment.measurements)
        channels = {item.role: item.execution for item in blueprint.roles}
        return CompiledCausalStudy(blueprint.specification_hash, experiment, blueprint.interaction, channels, validation)
