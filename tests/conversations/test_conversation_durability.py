from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3
from threading import Barrier

import pytest

from edsl.conversations import (
    Conversation,
    ConversationRuntime,
    CoordinatorAfter,
    MaxUtterances,
    OrderedTurns,
    SQLiteConversationStore,
)


def setup_conversation(tmp_path, *, after=False):
    definition = Conversation(
        "discussion",
        ["a", "b"],
        "Discuss.",
        CoordinatorAfter(coordinator="judge") if after else OrderedTurns(["a", "b"]),
        MaxUtterances(4),
    )
    store = SQLiteConversationStore(tmp_path / "conversation.sqlite")
    runtime = ConversationRuntime(definition, store)
    runtime.launch({"a": "a1", "b": "b1"}, instance_id="discussion")
    return runtime


def candidates():
    return [
        {
            "role": "a",
            "participant_id": "a1",
            "text": "A says",
            "metadata": {"source": "a"},
        },
        {"role": "b", "participant_id": "b1", "text": "B says"},
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"protocol": OrderedTurns(["b", "a"])},
        {"stop": MaxUtterances(1)},
        {"retire_on": {"a": ["pass"]}},
        {"turn_instructions": {"a": "Be brief."}},
    ],
)
@pytest.mark.parametrize(
    "operation",
    ["next_role", "next_recipient", "append", "should_stop", "realize_candidates"],
)
def test_restart_rejects_definition_drift_without_writes(tmp_path, change, operation):
    original = setup_conversation(tmp_path)
    runtime = ConversationRuntime(
        replace(original.definition, **change),
        SQLiteConversationStore(original.store.path),
    )
    kwargs = {}
    if operation == "append":
        kwargs = {"role": "a", "text": "Hello", "expected_version": 0}
    elif operation == "realize_candidates":
        kwargs = {
            "candidates": candidates(),
            "expected_version": 0,
            "coordinator": lambda *_: "a",
        }
    with pytest.raises(ValueError, match="persisted definition"):
        getattr(runtime, operation)("discussion", **kwargs)
    assert original.store.state("discussion")["status"] == "running"
    assert original.store.transcript("discussion") == []


def test_restart_accepts_json_round_trip(tmp_path):
    original = setup_conversation(tmp_path)
    runtime = ConversationRuntime(
        Conversation.from_dict(json.loads(json.dumps(original.definition.to_dict()))),
        SQLiteConversationStore(original.store.path),
    )
    runtime.append("discussion", role="a", text="Hello", expected_version=0)
    assert runtime.next_role("discussion") == "b"


def test_concurrent_realizations_commit_only_winning_candidates(tmp_path):
    runtime = setup_conversation(tmp_path, after=True)
    barrier = Barrier(2)

    def realize():
        restarted = ConversationRuntime(
            runtime.definition, SQLiteConversationStore(runtime.store.path)
        )

        def choose(*_):
            barrier.wait(timeout=5)
            return "a"

        try:
            return restarted.realize_candidates(
                "discussion", candidates(), expected_version=0, coordinator=choose
            )
        except ValueError as error:
            assert "stale" in str(error)
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: realize(), range(2)))
    assert sum(value is not None for value in results) == 1
    transcript = runtime.store.transcript("discussion")
    assert len(transcript) == 1
    with runtime.store.connect() as db:
        rows = db.execute("SELECT id, selected FROM conversation_candidates").fetchall()
    assert len(rows) == 2
    assert [row["id"] for row in rows if row["selected"]] == [
        transcript[0]["metadata"]["candidate_id"]
    ]
    assert transcript[0]["metadata"]["source"] == "a"
    assert runtime.store.state("discussion")["version"] == 1


def test_failed_candidate_write_rolls_back_transcript_and_audit(tmp_path):
    runtime = setup_conversation(tmp_path, after=True)
    with runtime.store.connect() as db:
        db.execute(
            """CREATE TRIGGER fail_second_candidate BEFORE INSERT ON conversation_candidates
                      WHEN NEW.role = 'b' BEGIN SELECT RAISE(ABORT, 'injected failure'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        runtime.realize_candidates(
            "discussion", candidates(), expected_version=0, coordinator=lambda *_: "a"
        )
    assert runtime.store.transcript("discussion") == []
    assert runtime.store.state("discussion")["version"] == 0
    with runtime.store.connect() as db:
        assert (
            db.execute("SELECT COUNT(*) FROM conversation_candidates").fetchone()[0]
            == 0
        )


@pytest.mark.parametrize(
    "failure",
    ["invalid_selection", "coordinator_error", "empty_text", "duplicate_role"],
)
def test_invalid_realization_leaves_no_candidates(tmp_path, failure):
    runtime = setup_conversation(tmp_path, after=True)
    inputs = candidates()
    if failure == "empty_text":
        inputs[0]["text"] = " "
    if failure == "duplicate_role":
        inputs.append(inputs[0])

    def choose(*_):
        if failure == "coordinator_error":
            raise ValueError("coordinator failed")
        return "missing" if failure == "invalid_selection" else "a"

    with pytest.raises(ValueError):
        runtime.realize_candidates(
            "discussion", inputs, expected_version=0, coordinator=choose
        )
    assert runtime.store.transcript("discussion") == []
    with runtime.store.connect() as db:
        assert (
            db.execute("SELECT COUNT(*) FROM conversation_candidates").fetchone()[0]
            == 0
        )
