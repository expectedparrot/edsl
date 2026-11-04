import json

import pytest

from edsl.sharedstate import SQLiteStateBackend, SharedStateMap
from edsl.sharedstate.model import resolve_read, resolve_write
from edsl.sharedstate.steps import StepContext
from edsl.workflows import HumanWorkflow
from examples.talk_isnt_cheap.debate_experiment import (
    EXAMPLE_ITEM,
    MODEL_COMPOSITIONS,
    DebateItem,
    analyze_responses,
    build_debate_workflow,
    build_debaters,
    experiment_manifest,
    majority_answer,
)
from examples.talk_isnt_cheap.run_openai_pilot import run


def test_debate_item_round_trip_and_validation():
    assert DebateItem.from_dict(EXAMPLE_ITEM.to_dict()) == EXAMPLE_ITEM
    gsm8k = DebateItem("gsm-example", "gsm8k", "What is 2 + 2?", (), "4")
    workflow, _ = build_debate_workflow(gsm8k)
    assert workflow.steps[0].survey.questions[0].question_type == "dict"


def test_workflow_and_shared_state_are_serializable():
    workflow, state = build_debate_workflow(EXAMPLE_ITEM)
    restored_workflow = HumanWorkflow.from_dict(workflow.to_dict())
    restored_state = SharedStateMap.from_dict(state.to_dict())

    assert [step.name for step in restored_workflow.steps] == [
        "round-0",
        "round-1",
        "round-2",
    ]
    assert restored_workflow.steps[0].after == ()
    assert restored_workflow.steps[1].after == ("round-0",)
    assert restored_workflow.steps[2].after == ("round-1",)
    assert all(len(step.writes) == 1 for step in restored_workflow.steps)
    assert len(restored_workflow.steps[0].reads) == 0
    assert all(len(step.reads) == 1 for step in restored_workflow.steps[1:])
    assert restored_state.to_dict() == state.to_dict()
    json.dumps({"workflow": workflow.to_dict(), "state": state.to_dict()})


def test_complete_paper_design_manifest():
    manifest = experiment_manifest()
    assert len(MODEL_COMPOSITIONS) == 10
    assert set(manifest["datasets"]) == {"csqa", "mmlu", "gsm8k"}
    assert manifest["seeds"] == [0, 1, 2, 3, 4]
    assert manifest["rounds"] == [0, 1, 2]
    assert len(build_debaters(("gpt", "llama", "mistral"))) == 3


def test_debate_ledger_executes_transactionally(tmp_path):
    _, state = build_debate_workflow(EXAMPLE_ITEM)
    ledger = state.by(EXAMPLE_ITEM.item_id).debate
    backend = SQLiteStateBackend(state, tmp_path / "debate.sqlite3")
    context = StepContext({}, "round-0-agent-a")
    write = ledger.submit(
        participant="agent-a",
        round=0,
        response={"answer": "D", "reasoning": "r"},
    )

    first = backend.apply(resolve_write(write, context))
    retry = backend.apply(resolve_write(write, context))
    observed = backend.read(resolve_read(ledger.read(), context))

    assert first.accepted and retry.accepted
    assert observed.version == 1
    assert observed.value["responses"] == [
        {
            "participant": "agent-a",
            "round": 0,
            "response": {"answer": "D", "reasoning": "r"},
        }
    ]


def test_majority_and_transition_analysis():
    responses = [
        {
            "participant": "a",
            "round": 0,
            "response": {"answer": "correct", "reasoning": "r"},
        },
        {
            "participant": "b",
            "round": 0,
            "response": {"answer": "correct", "reasoning": "r"},
        },
        {
            "participant": "c",
            "round": 0,
            "response": {"answer": "wrong", "reasoning": "r"},
        },
        {
            "participant": "a",
            "round": 1,
            "response": {"answer": "wrong", "reasoning": "r"},
        },
        {
            "participant": "b",
            "round": 1,
            "response": {"answer": "correct", "reasoning": "r"},
        },
        {
            "participant": "c",
            "round": 1,
            "response": {"answer": "correct", "reasoning": "r"},
        },
        {
            "participant": "a",
            "round": 2,
            "response": {"answer": "wrong", "reasoning": "r"},
        },
        {
            "participant": "b",
            "round": 2,
            "response": {"answer": "wrong", "reasoning": "r"},
        },
        {
            "participant": "c",
            "round": 2,
            "response": {"answer": "correct", "reasoning": "r"},
        },
    ]

    analysis = analyze_responses(responses, "correct")

    assert majority_answer(["x", "x", "y"]) == "x"
    assert majority_answer(["x", "y"]) is None
    assert analysis["majority_answers"] == {
        "0": "correct",
        "1": "correct",
        "2": "wrong",
    }
    assert analysis["transitions"] == {
        "correct_to_correct": 2,
        "correct_to_incorrect": 2,
        "incorrect_to_correct": 1,
        "incorrect_to_incorrect": 1,
    }
    assert analysis["transitions_by_agreeing_peers"]["1"]["correct_to_incorrect"] == 2


def test_pilot_refuses_to_mix_existing_execution_state(tmp_path):
    output = tmp_path / "existing-run"
    output.mkdir()
    (output / "workflow.sqlite").touch()
    with pytest.raises(FileExistsError, match="fresh directory"):
        run(output)
