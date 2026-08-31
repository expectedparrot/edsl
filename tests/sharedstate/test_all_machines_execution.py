"""Execute a meaningful transition path through every retained state machine."""

from __future__ import annotations

from importlib import import_module
import json

import pytest

from edsl.sharedstate import SharedState, SharedStateMap, SQLiteStateBackend
from edsl.sharedstate.model import resolve_read, resolve_write
from edsl.sharedstate.steps import StepContext


VECTORS = {
    "shared_agenda": [
        ("propose", {"proposer": "Amina", "title": "Go sailing"}),
        ("vote", {"voter": "Boris", "votes": {"0": 0}}),
    ],
    "shared_auction": [
        ("bid", {"amount": 10}),
        ("bid", {"amount": 20}),
        ("bid", {"amount": 30}),
        ("$close", {}),
    ],
    "shared_beauty_contest": [
        ("submit", {"player": "A", "choice": 30}),
        ("submit", {"player": "B", "choice": 40}),
        ("submit", {"player": "C", "choice": 50}),
        ("$close", {}),
    ],
    "shared_bilateral_trade": [
        ("offer", {"buyer": "Buyer", "buyer_value": 90, "price": 55}),
        ("respond", {"seller": "Seller", "seller_cost": 30, "decision": "accept"}),
    ],
    "shared_binary_market": [
        ("trade", {"trader": "Amina", "action": "buy_yes", "quantity": 2}),
        ("settle", {"outcome": True}),
    ],
    "shared_budget_pool": [
        ("fund", {"sponsor": "Amina", "project": "park", "amount": 100}),
    ],
    "shared_centipede_game": [
        ("move", {"player": "A", "node": 1, "action": "pass"}),
        ("move", {"player": "B", "node": 2, "action": "take"}),
    ],
    "shared_cheap_talk_game": [
        ("message", {"sender": "Sender", "state": "L", "preference": "aligned", "message": "L"}),
        ("act", {"receiver": "Receiver", "action": "L"}),
    ],
    "shared_coalition_pool": [
        ("request", {"member": "Amina", "coalition": "red", "round": 1}),
        ("request", {"member": "Boris", "coalition": "red", "round": 1}),
    ],
    "shared_common_pool_game": [
        ("extract", {"player": "A", "amount": 10}),
        ("extract", {"player": "B", "amount": 20}),
        ("extract", {"player": "C", "amount": 15}),
        ("$close", {}),
    ],
    "shared_counter_map": [
        ("tally", {"values": ["hike", "hike", "sailing"]}),
    ],
    "shared_deferred_acceptance": [
        ("collect", {"student": "A", "ranking": ["North", "South"]}),
        ("collect", {"student": "B", "ranking": ["North", "South"]}),
        ("$close", {}),
    ],
    "shared_delphi_panel": [
        ("submit", {"expert": "A", "round": 1, "estimate": 50, "confidence": 80, "rationale": "r1"}),
        ("submit", {"expert": "B", "round": 1, "estimate": 52, "confidence": 80, "rationale": "r1"}),
        ("submit", {"expert": "C", "round": 1, "estimate": 54, "confidence": 80, "rationale": "r1"}),
        ("submit", {"expert": "A", "round": 2, "estimate": 51, "confidence": 85, "rationale": "r2"}),
        ("submit", {"expert": "B", "round": 2, "estimate": 52, "confidence": 85, "rationale": "r2"}),
        ("submit", {"expert": "C", "round": 2, "estimate": 53, "confidence": 85, "rationale": "r2"}),
    ],
    "shared_dictator_game": [
        ("allocate", {"dictator": "A", "recipient": "B", "transfer": 30}),
    ],
    "shared_document": [
        ("revise", {"author": "Amina", "round": 1, "text": "We will hike.", "rationale": "Consensus"}),
    ],
    "shared_double_auction": [
        ("submit", {"trader": "Seller", "round": 1, "action": "sell", "price": 40}),
        ("submit", {"trader": "Buyer", "round": 1, "action": "buy", "price": 50}),
        ("$close", {}),
    ],
    "shared_forecast": [
        ("submit", {"forecaster": "Amina", "round": 1, "probability": 60, "confidence": 75}),
    ],
    "shared_log": [("append", {"entry": {"author": "Amina", "text": "Hello"}})],
    "shared_market_entry_game": [
        ("submit", {"player": "A", "action": "enter"}),
        ("submit", {"player": "B", "action": "stay_out"}),
        ("submit", {"player": "C", "action": "enter"}),
        ("$close", {}),
    ],
    "shared_match_pool": [
        ("collect", {"claimant": "A", "priority": 1, "ranking": ["hike", "sailing", "bike ride", "beach day"]}),
        ("collect", {"claimant": "B", "priority": 2, "ranking": ["hike", "bike ride", "beach day", "sailing"]}),
        ("collect", {"claimant": "C", "priority": 3, "ranking": ["sailing", "beach day", "hike", "bike ride"]}),
        ("$close", {}),
    ],
    "shared_matrix_game": [
        ("submit", {"player": "A", "seat": "0", "action": "cooperate"}),
        ("submit", {"player": "B", "seat": "1", "action": "defect"}),
        ("$close", {}),
    ],
    "shared_meeting_poll": [
        (
            "respond",
            {
                "participant": "Amina",
                "available_slots": ["Tuesday 10:00 AM", "Wednesday 2:00 PM"],
            },
        ),
    ],
    "shared_message_board": [
        ("add", {"author": "Amina", "message": "Let's hike", "reply_to": None}),
    ],
    "shared_money_request_game": [
        ("submit", {"player": "A", "request": 19}),
        ("submit", {"player": "B", "request": 20}),
        ("$close", {}),
    ],
    "shared_nash_demand_game": [
        ("demand", {"player": "A", "seat": "0", "amount": 40}),
        ("demand", {"player": "B", "seat": "1", "amount": 50}),
        ("$close", {}),
    ],
    "shared_negotiation": [
        ("record", {"speaker": "Buyer", "role": "buyer", "action": "offer", "amount": 60, "message": "I offer 60"}),
        ("record", {"speaker": "Seller", "role": "seller", "action": "accept", "amount": 60, "message": "Accepted"}),
    ],
    "shared_principal_agent_game": [
        ("contract", {"principal": "Firm", "bonus": 30}),
        ("effort", {"worker": "Worker", "effort": "high"}),
    ],
    "shared_register": [("set", {"key": "Amina", "value": "hike"})],
    "shared_repeated_matrix_game": [
        ("submit", {"player": "A", "seat": "0", "round": 1, "action": "cooperate"}),
        ("submit", {"player": "B", "seat": "1", "round": 1, "action": "defect"}),
        ("submit", {"player": "A", "seat": "0", "round": 2, "action": "defect"}),
        ("submit", {"player": "B", "seat": "1", "round": 2, "action": "defect"}),
        ("submit", {"player": "A", "seat": "0", "round": 3, "action": "cooperate"}),
        ("submit", {"player": "B", "seat": "1", "round": 3, "action": "cooperate"}),
    ],
    "shared_resource_board": [
        ("allocate", {"responder": "Amina", "round": 1, "incident": "fire", "resource": "E1"}),
    ],
    "shared_review_screening": [
        ("claim", {"reviewer": "Amina"}),
        (
            "review",
            {
                "reviewer": "Amina",
                "decision": "include",
                "reason": "Randomized study with attendance outcomes.",
            },
        ),
        (
            "adjudicate",
            {
                "paper": "P1",
                "adjudicator": "Morgan",
                "decision": "include",
                "reason": "Meets the review criteria.",
            },
        ),
    ],
    "shared_sealed_auction": [
        ("bid", {"bidder": "A", "seat": 0, "private_value": 80, "amount": 60}),
        ("bid", {"bidder": "B", "seat": 1, "private_value": 70, "amount": 50}),
        ("bid", {"bidder": "C", "seat": 2, "private_value": 40, "amount": 30}),
        ("$close", {}),
    ],
    "shared_signal_schedule": [
        ("reveal", {"participant": "Amina", "round": 1}),
    ],
    "shared_signaling_game": [
        ("signal", {"worker": "Worker", "productivity": 90, "signal_cost": 10, "education": 2}),
        ("decide", {"employer": "Firm", "decision": "hire"}),
    ],
    "shared_trust_game": [
        ("send", {"player": "Sender", "amount": 30}),
        ("return_funds", {"player": "Receiver", "amount": 40}),
    ],
    "shared_ultimatum_game": [
        ("offer", {"player": "Proposer", "amount": 35}),
        ("respond", {"player": "Responder", "decision": "accept"}),
    ],
    "shared_voting_game": [
        ("vote", {"voter": "A", "ranking": ["A", "B", "C"]}),
        ("vote", {"voter": "B", "ranking": ["B", "A", "C"]}),
        ("vote", {"voter": "C", "ranking": ["A", "C", "B"]}),
        ("$close", {}),
    ],
    "shared_work_pool": [
        ("claim_before", {"claimant": "Amina"}),
        ("complete", {"claimant": "Amina", "result": {"score": 5}}),
    ],
}


# A compact semantic oracle for every machine.  These checks intentionally
# target the economically or procedurally meaningful result, rather than
# copying each machine's entire public view into the test.
EXPECTED_PATHS = {
    "shared_agenda": {("scores", "Go sailing"): 1},
    "shared_auction": {
        ("highest_bid",): 30,
        ("winning_bid",): 30,
        ("winner",): "shared_auction-3",
    },
    "shared_beauty_contest": {("mean",): 40.0, ("winners",): ["A"]},
    "shared_bilateral_trade": {("accepted",): True, ("payoffs", "Buyer"): 35},
    "shared_binary_market": {
        ("prices", "yes"): 0.5099986668799655,
        ("portfolios", "Amina", "yes"): 2.0,
    },
    "shared_budget_pool": {("remaining",): 0, ("funded", "park"): 100},
    "shared_centipede_game": {("outcome",): "take_at_2", ("payoffs",): [1, 3]},
    "shared_cheap_talk_game": {("truthful",): True, ("correct_action",): True},
    "shared_coalition_pool": {("members", "red"): ["Amina", "Boris"]},
    "shared_common_pool_game": {("total_requested",): 45, ("overdrawn",): False},
    "shared_counter_map": {("counts", "hike"): 2},
    "shared_deferred_acceptance": {("matches",): {"A": "North", "B": "South"}},
    "shared_delphi_panel": {("summaries", 2, "range"): 2},
    "shared_dictator_game": {("payoffs",): {"A": 70, "B": 30}},
    "shared_document": {("text",): "We will hike.", ("revision_count",): 1},
    "shared_double_auction": {
        ("trades", 0, "price"): 40.0,
        ("trades", 0, "maker_order"): "O1",
    },
    "shared_forecast": {("mean_probability",): 60.0},
    "shared_log": {("count",): 1},
    "shared_market_entry_game": {("payoffs",): {"A": 4, "B": 2, "C": 4}},
    "shared_match_pool": {
        ("assignments",): {"A": "hike", "B": "bike ride", "C": "sailing"}
    },
    "shared_matrix_game": {("payoffs",): {"A": 0, "B": 5}},
    "shared_meeting_poll": {
        ("counts", "Tuesday 10:00 AM"): 1,
        ("response_count",): 1,
    },
    "shared_message_board": {("message_count",): 1},
    "shared_money_request_game": {("payoffs",): {"A": 39, "B": 20}},
    "shared_nash_demand_game": {("feasible",): True, ("payoffs", "B"): 50},
    "shared_negotiation": {("agreement",): 60},
    "shared_principal_agent_game": {("expected_payoffs", "Firm"): 56.0},
    "shared_register": {("values", "Amina"): "hike"},
    "shared_repeated_matrix_game": {("rounds", "1", "1"): "defect"},
    "shared_resource_board": {("assignments", "fire"): "E1"},
    "shared_review_screening": {
        ("remaining_assignment_count",): 5,
        ("reviews", 0, "paper"): "P1",
        ("final_decisions", "P1", "decision"): "include",
    },
    "shared_sealed_auction": {("winner",): "A", ("price",): 50},
    "shared_signal_schedule": {("release_count",): 1},
    "shared_signaling_game": {("hired",): True, ("payoffs", "Worker"): 40},
    "shared_trust_game": {("payoffs",): {"Receiver": 50, "Sender": 110}},
    "shared_ultimatum_game": {("decision",): "accept", ("payoffs", "proposer"): 65},
    "shared_voting_game": {("results", "condorcet_winner"): "A"},
    "shared_work_pool": {("completed", "Amina", "result", "score"): 5},
}


def _at(value, path):
    for part in path:
        value = value[part]
    return value


@pytest.mark.parametrize("module_name", sorted(VECTORS))
def test_machine_executes_through_transactional_backend(module_name, tmp_path):
    machine = import_module(
        f"examples.shared_state_dsl.{module_name}"
    ).SPEC
    machine.validate()
    spaces = SharedStateMap(
        SharedState(machine=machine), state_id=f"execution-{module_name}"
    )
    handle = spaces.by("scope").machine
    backend = SQLiteStateBackend(spaces, tmp_path / f"{module_name}.sqlite3")

    outcomes = []
    for index, (command, inputs) in enumerate(VECTORS[module_name], 1):
        step = handle.close() if command == "$close" else handle.command(command, **inputs)
        outcome = backend.apply(
            resolve_write(step, StepContext({}, f"{module_name}-{index}"))
        )
        outcomes.append(outcome)

    observed = backend.read(
        resolve_read(handle.read(), StepContext({}, f"{module_name}-reader"))
    )
    writes = [event for event in backend.history() if event["kind"] == "write"]

    assert all(outcome.accepted for outcome in outcomes)
    assert [event["version"] for event in writes] == list(
        range(1, len(writes) + 1)
    )
    assert len(writes) == len(VECTORS[module_name])
    assert observed.version == len(writes)
    json.dumps(observed.value)
    for path, expected in EXPECTED_PATHS[module_name].items():
        actual = _at(observed.value, path)
        if isinstance(expected, float):
            assert actual == pytest.approx(expected)
        else:
            assert actual == expected
    if machine.complete_when is not None:
        snapshot = backend.snapshot("scope")
        assert backend.runtime.complete(machine, snapshot.state["machine"])


def test_vector_inventory_exactly_matches_retained_machine_files():
    from pathlib import Path

    modules = {
        path.stem
        for path in Path("examples/shared_state_dsl").glob("shared_*.py")
    }
    assert set(VECTORS) == modules
    assert set(EXPECTED_PATHS) == modules


def test_delphi_does_not_converge_on_a_partial_round(tmp_path):
    machine = import_module(
        "examples.shared_state_dsl.shared_delphi_panel"
    ).SPEC
    spaces = SharedStateMap(SharedState(panel=machine), state_id="partial-delphi")
    panel = spaces.by("scope").panel
    backend = SQLiteStateBackend(spaces, tmp_path / "delphi.sqlite3")
    commands = VECTORS["shared_delphi_panel"]

    for index, (_, inputs) in enumerate(commands[:4], 1):
        backend.apply(
            resolve_write(
                panel.submit(**inputs), StepContext({}, f"partial-{index}")
            )
        )

    snapshot = backend.snapshot("scope")
    assert not backend.runtime.complete(machine, snapshot.state["panel"])
