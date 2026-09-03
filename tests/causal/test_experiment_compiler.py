import json

import pytest

from edsl.causal import AgentRole, CompiledExperiment, ExperimentCompiler
from examples.automated_social_science.mug_causal_spec import build_mug_study


def roles():
    return [
        AgentRole("buyer", "buy the mug at an acceptable price", "never pay above your budget"),
        AgentRole("seller", "sell the mug at the highest acceptable price", "do not accept an unwanted deal"),
    ]


def test_compiler_creates_stable_private_assignments_and_measurements():
    _, plan, design = build_mug_study()
    compiler = ExperimentCompiler()
    first = compiler.compile(plan=plan, design=design, roles=roles())
    second = compiler.compile(plan=plan, design=design, roles=roles())
    assert first == second
    assert len(first.replications) == 320
    replication = first.replications[0]
    buyer = next(item for item in replication.participants if item.role == "buyer")
    seller = next(item for item in replication.participants if item.role == "seller")
    assert set(buyer.private_context) == {"buyer_budget"}
    assert set(seller.private_context) == {"seller_attachment"}
    assert "seller_attachment" not in buyer.private_context
    assert "buyer_budget" not in seller.private_context
    assert set(replication.system_context) == {"buyer_budget", "seller_attachment"}
    assert first.measurements[0].respondent_role == "buyer"
    assert first.measurements[0].field == "deal_occurred"
    assert CompiledExperiment.from_dict(json.loads(json.dumps(first.to_dict()))) == first


def test_compiled_assignments_materialize_agents_without_cross_role_leakage():
    _, plan, design = build_mug_study()
    compiled = ExperimentCompiler().compile(plan=plan, design=design, roles=roles())
    replication = compiled.replications[0]
    agents = {assignment.role: assignment.to_agent() for assignment in replication.participants}
    assert "maximum budget" in agents["buyer"].instruction
    assert "sentimental attachment" not in agents["buyer"].instruction
    assert "sentimental attachment" in agents["seller"].instruction
    assert "maximum budget" not in agents["seller"].instruction


def test_compiler_rejects_missing_roles_and_mismatched_design():
    _, plan, design = build_mug_study()
    with pytest.raises(ValueError, match="missing roles"):
        ExperimentCompiler().compile(plan=plan, design=design, roles=roles()[:1])
    truncated = type(design)(design.factors[:1], design.cells, design.seed)
    with pytest.raises(ValueError, match="exactly match"):
        ExperimentCompiler().compile(plan=plan, design=truncated, roles=roles())
