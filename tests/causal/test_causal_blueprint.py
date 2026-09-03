import json

import pytest

from edsl.causal import (
    BlueprintCompiler,
    CausalStudyBlueprint,
    CompiledCausalStudy,
    DesignPolicy,
    InformationPolicy,
    ProcedureRequirement,
)
from examples.automated_social_science.mug_blueprint import build_mug_blueprint


def round_trip(value):
    return json.loads(json.dumps(value))


def test_blueprint_and_compilation_are_serializable_and_deterministic():
    blueprint = build_mug_blueprint()
    restored = CausalStudyBlueprint.from_dict(round_trip(blueprint.to_dict()))
    assert restored == blueprint
    assert restored.specification_hash == blueprint.specification_hash

    first = BlueprintCompiler().compile(blueprint)
    second = BlueprintCompiler().compile(restored)
    assert first == second
    assert len(first.experiment.replications) == 320
    assert CompiledCausalStudy.from_dict(round_trip(first.to_dict())) == first


def test_information_policy_overrides_scm_visibility_without_leakage():
    blueprint = build_mug_blueprint()
    compiled = BlueprintCompiler().compile(blueprint)
    replication = compiled.experiment.replications[0]
    by_role = {item.role: item for item in replication.participants}
    assert set(by_role["buyer"].private_context) == {"buyer_budget"}
    assert set(by_role["seller"].private_context) == {"seller_attachment"}
    assert replication.public_context == {}
    assert set(replication.system_context) == {"buyer_budget", "seller_attachment"}
    assert compiled.execution_channels["buyer"].kind == "llm"


def test_shared_information_can_cross_causal_scope_explicitly():
    blueprint = build_mug_blueprint()
    shared = (
        InformationPolicy("buyer_budget", "shared", ["buyer", "seller"]),
        blueprint.information[1],
    )
    changed = CausalStudyBlueprint(
        blueprint.name,
        blueprint.research_question,
        blueprint.analysis_plan,
        blueprint.roles,
        shared,
        blueprint.design,
        blueprint.interaction,
    )
    replication = BlueprintCompiler().compile(changed).experiment.replications[0]
    by_role = {item.role: item for item in replication.participants}
    assert "buyer_budget" in by_role["buyer"].private_context
    assert "buyer_budget" in by_role["seller"].private_context


def test_validation_reports_multiple_cross_component_errors():
    blueprint = build_mug_blueprint()
    invalid = CausalStudyBlueprint(
        blueprint.name,
        blueprint.research_question,
        blueprint.analysis_plan,
        blueprint.roles,
        [
            InformationPolicy("buyer_budget", "private", ["unknown-role"]),
            InformationPolicy("unknown-variable", "system"),
        ],
        DesignPolicy(replications=1, seed="small", max_cells=1),
        blueprint.interaction,
    )
    validation = invalid.validate()
    codes = {item.code for item in validation.findings}
    assert {"invalid-information-audience", "unknown-information-variable", "missing-information-policy", "insufficient-observations"}.issubset(codes)
    assert not validation.is_valid
    with pytest.raises(ValueError, match="invalid causal study blueprint"):
        BlueprintCompiler().compile(invalid)


def test_unsupported_design_and_procedure_are_not_silently_ignored():
    blueprint = build_mug_blueprint()
    invalid = CausalStudyBlueprint(
        blueprint.name,
        blueprint.research_question,
        blueprint.analysis_plan,
        blueprint.roles,
        blueprint.information,
        DesignPolicy(method="power", replications=1),
        blueprint.interaction,
        [ProcedureRequirement("roles_spoken")],
    )
    codes = {item.code for item in invalid.validate().findings}
    assert "unsupported-design-method" in codes
    assert "unsupported-procedure-requirement" in codes
