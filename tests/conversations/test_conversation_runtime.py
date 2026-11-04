import json

import pytest

from edsl.conversations import (
    AnyStop,
    AllStop,
    CentralOrdered,
    Conversation,
    ConversationRuntime,
    CoordinatorAfter,
    CoordinatorBefore,
    MaxUtterances,
    OrderedTurns,
    RandomTurns,
    RolesSpoken,
    SQLiteConversationStore,
    SemanticStop,
)


def ordered_conversation():
    return Conversation("mug", ["buyer", "seller"], "Negotiate over a mug.", OrderedTurns(["buyer", "seller"]), AnyStop(SemanticStop(judge="coordinator", question="Continue?"), MaxUtterances(4)))


def test_conversation_round_trip_and_ordered_optimistic_append(tmp_path):
    definition = ordered_conversation()
    assert Conversation.from_dict(json.loads(json.dumps(definition.to_dict()))) == definition
    store = SQLiteConversationStore(tmp_path / "conversation.sqlite")
    runtime = ConversationRuntime(definition, store)
    runtime.launch({"buyer": "buyer-1", "seller": "seller-1"}, instance_id="mug-1")
    assert runtime.next_role("mug-1") == "buyer"
    runtime.append("mug-1", role="buyer", text="I offer $10.", expected_version=0)
    assert runtime.next_role("mug-1") == "seller"
    with pytest.raises(ValueError, match="stale"):
        runtime.append("mug-1", role="seller", text="Late response", expected_version=0)
    runtime.append("mug-1", role="seller", text="I accept.", expected_version=1)
    assert [item["sequence"] for item in store.transcript("mug-1")] == [1, 2]
    assert runtime.should_stop("mug-1", lambda definition, transcript, question: "accept" in transcript[-1]["text"]) is True
    assert store.state("mug-1")["status"] == "completed"


def test_random_turns_are_stable_and_do_not_repeat(tmp_path):
    definition = Conversation("discussion", ["a", "b", "c"], "Discuss.", RandomTurns(seed="turns"), MaxUtterances(3))
    store = SQLiteConversationStore(tmp_path / "random.sqlite")
    runtime = ConversationRuntime(definition, store)
    runtime.launch({role: role for role in definition.roles}, instance_id="random-1")
    first = runtime.next_role("random-1")
    assert first == runtime.next_role("random-1")
    runtime.append("random-1", role=first, text="First", expected_version=0)
    assert runtime.next_role("random-1") != first


def test_roles_spoken_can_guard_semantic_stop_and_round_trip(tmp_path):
    definition = Conversation(
        "guarded",
        ["a", "b"],
        "Both must speak.",
        OrderedTurns(["a", "b"]),
        AnyStop(AllStop(RolesSpoken(["a", "b"]), SemanticStop(judge="judge", question="Done?")), MaxUtterances(4)),
    )
    assert Conversation.from_dict(json.loads(json.dumps(definition.to_dict()))) == definition
    runtime = ConversationRuntime(definition, SQLiteConversationStore(tmp_path / "guarded.sqlite"))
    runtime.launch({"a": "a1", "b": "b1"}, instance_id="guarded")
    runtime.append("guarded", role="a", text="done", expected_version=0)
    assert runtime.should_stop("guarded", lambda *_: True) is False
    runtime.append("guarded", role="b", text="done", expected_version=1)
    assert runtime.should_stop("guarded", lambda *_: True) is True


def test_central_ordered_alternates_center_and_others(tmp_path):
    definition = Conversation("hearing", ["judge", "defense", "prosecution"], "Set bail.", CentralOrdered(center="judge", others=["defense", "prosecution"]), MaxUtterances(5))
    store = SQLiteConversationStore(tmp_path / "central.sqlite")
    runtime = ConversationRuntime(definition, store)
    runtime.launch({role: role for role in definition.roles}, instance_id="hearing")
    observed = []
    for version in range(5):
        role = runtime.next_role("hearing")
        observed.append(role)
        runtime.append("hearing", role=role, text=f"turn {version}", expected_version=version)
    assert observed == ["judge", "defense", "judge", "prosecution", "judge"]
    assert runtime.should_stop("hearing") is True


def test_central_ordered_skips_roles_after_serializable_retirement(tmp_path):
    definition = Conversation(
        "auction",
        ["auctioneer", "a", "b", "c"],
        "Auction an item.",
        CentralOrdered(center="auctioneer", others=["a", "b", "c"]),
        MaxUtterances(20),
        turn_instructions={"*": "Be terse.", "a": "Bid or pass."},
        retire_on={"a": ["pass"], "b": ["pass"], "c": ["pass"]},
    )
    assert Conversation.from_dict(json.loads(json.dumps(definition.to_dict()))) == definition
    store = SQLiteConversationStore(tmp_path / "retirement.sqlite")
    runtime = ConversationRuntime(definition, store)
    runtime.launch({role: role for role in definition.roles}, instance_id="auction")
    turns = [("auctioneer", "Bid?"), ("a", "Pass."), ("auctioneer", "Next?"), ("b", "$50")]
    for version, (role, text) in enumerate(turns):
        assert runtime.next_role("auction") == role
        runtime.append("auction", role=role, text=text, expected_version=version)
    assert runtime.next_role("auction") == "auctioneer"
    runtime.append("auction", role="auctioneer", text="Next?", expected_version=4)
    assert runtime.next_role("auction") == "c"
    assert runtime.next_recipient("auction") == "c"


def test_coordinator_before_validates_selected_role(tmp_path):
    definition = Conversation("dynamic", ["a", "b"], "Discuss.", CoordinatorBefore(coordinator="hidden"), MaxUtterances(2))
    runtime = ConversationRuntime(definition, SQLiteConversationStore(tmp_path / "before.sqlite"))
    runtime.launch({"a": "a1", "b": "b1"}, instance_id="dynamic")
    assert runtime.next_role("dynamic", lambda definition, transcript, eligible: eligible[0]) == "a"
    with pytest.raises(ValueError, match="ineligible"):
        runtime.next_role("dynamic", lambda definition, transcript, eligible: "missing")


def test_coordinator_after_retains_unrealized_candidates_for_audit(tmp_path):
    definition = Conversation("after", ["a", "b"], "Discuss.", CoordinatorAfter(coordinator="hidden"), MaxUtterances(2))
    store = SQLiteConversationStore(tmp_path / "after.sqlite")
    runtime = ConversationRuntime(definition, store)
    runtime.launch({"a": "a1", "b": "b1"}, instance_id="after")
    candidates = [{"role": "a", "participant_id": "a1", "text": "A says"}, {"role": "b", "participant_id": "b1", "text": "B says"}]
    runtime.realize_candidates("after", candidates, expected_version=0, coordinator=lambda definition, transcript, eligible: "b")
    assert store.transcript("after")[0]["text"] == "B says"
    with store.connect() as db:
        rows = db.execute("SELECT role, selected FROM conversation_candidates ORDER BY role").fetchall()
    assert [(row["role"], row["selected"]) for row in rows] == [("a", 0), ("b", 1)]
