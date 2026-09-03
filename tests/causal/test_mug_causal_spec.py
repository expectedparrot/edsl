import json

from edsl.causal import CompiledExperiment
from edsl.conversations import Conversation
from examples.automated_social_science.mug_causal_spec import (
    build_compiled_mug_experiment,
    build_compiled_original_mug_experiment,
    build_mug_study,
    build_original_mug_study,
)


def test_mug_causal_spec_is_complete_and_serializable():
    scm, plan, design = build_mug_study()
    assert len(scm.exogenous_variables) == 2
    assert len(scm.endogenous_variables) == 1
    assert len(plan.estimands) == 2
    assert len(design.cells) == 4 * 4 * 20
    json.dumps({"scm": scm.to_dict(), "plan": plan.to_dict(), "design": design.to_dict()})


def test_compiled_mug_experiment_and_conversation_round_trip():
    compiled, conversation = build_compiled_mug_experiment()
    payload = json.loads(json.dumps({"experiment": compiled.to_dict(), "conversation": conversation.to_dict()}))
    assert CompiledExperiment.from_dict(payload["experiment"]) == compiled
    assert Conversation.from_dict(payload["conversation"]) == conversation
    assert conversation.protocol.options["order"] == ["buyer", "seller"]


def test_original_mug_design_matches_published_405_cell_factorial():
    scm, plan, design = build_original_mug_study()
    assert len(design.cells) == 405
    assert [len(variable.treatments) for variable in scm.exogenous_variables] == [9, 9, 5]
    assert [effect.cause for effect in plan.estimands] == [
        "buyer_budget",
        "seller_minimum_price",
        "seller_attachment",
    ]

    compiled, conversation, compiled_plan = build_compiled_original_mug_experiment()
    assert len(compiled.replications) == 405
    assert conversation.roles == ("buyer", "seller")
    assert compiled.measurements[0].respondent_role == "coordinator"
    assert compiled_plan.to_dict() == plan.to_dict()
