import json

import pytest

from edsl.causal import CausalAnalysisPlan, CompiledExperiment
from edsl.conversations import Conversation
from examples.automated_social_science.paper_studies import STUDIES


@pytest.mark.parametrize(
    ("study", "cells", "protocol", "roles", "outcome"),
    [
        ("bail", 245, "central_ordered", ("judge", "prosecutor", "defense_attorney", "defendant"), "bail_amount"),
        ("interview", 80, "ordered", ("interviewer", "applicant"), "hired"),
        ("auction", 343, "central_ordered", ("auctioneer", "bidder_1", "bidder_2", "bidder_3"), "final_price"),
    ],
)
def test_published_study_designs_are_complete_and_serializable(study, cells, protocol, roles, outcome):
    compiled, conversation, plan = STUDIES[study]()
    assert len(compiled.replications) == cells
    assert conversation.protocol.kind == protocol
    assert conversation.roles == roles
    assert compiled.measurements[0].variable == outcome
    payload = json.loads(json.dumps({"compiled": compiled.to_dict(), "conversation": conversation.to_dict(), "plan": plan.to_dict()}))
    assert CompiledExperiment.from_dict(payload["compiled"]) == compiled
    assert Conversation.from_dict(payload["conversation"]) == conversation
    assert CausalAnalysisPlan.from_dict(payload["plan"]) == plan


def test_bail_information_boundary_matches_courtroom_knowledge():
    compiled, _, _ = STUDIES["bail"]()
    replication = compiled.replications[0]
    assert "criminal_history_instruction" in replication.public_context
    assert "defendant_remorse_instruction" in replication.public_context
    judge = next(item for item in replication.participants if item.role == "judge")
    defendant = next(item for item in replication.participants if item.role == "defendant")
    assert set(judge.private_context) == {"judge_case_count"}
    assert defendant.private_context == {}


def test_auction_budgets_remain_role_private():
    compiled, conversation, _ = STUDIES["auction"]()
    replication = compiled.replications[0]
    assert replication.public_context == {}
    for index in (1, 2, 3):
        bidder = next(item for item in replication.participants if item.role == f"bidder_{index}")
        assert set(bidder.private_context) == {f"bidder_{index}_budget"}
    assert conversation.turn_instructions["*"].startswith("Use one terse line")
    assert "'pass'" in conversation.turn_instructions["bidder_1"]
