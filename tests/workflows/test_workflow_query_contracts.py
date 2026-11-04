"""Integrity and ordering guarantees for the workflow query optimizations."""

import json
import sqlite3

import pytest

from edsl import Agent, QuestionFreeText, Survey
from edsl._data_contracts import definition_fingerprint
from edsl.workflows import SQLiteWorkflowStore, Workflow, WorkflowCoordinator, role


def coordinator(tmp_path):
    workflow = Workflow("definitions")
    workflow.step(
        "reply",
        Survey([QuestionFreeText(question_name="reply", question_text="Reply")]),
    )
    result = WorkflowCoordinator(
        workflow.compile(), SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    )
    instance = result.launch([Agent(name="person")])
    result.store.assert_definition(instance, result.workflow.to_dict())
    return result, instance


def test_cached_definition_still_detects_nested_runtime_mutation(tmp_path):
    runtime, instance = coordinator(tmp_path)
    runtime.workflow.steps[0].survey.questions[0].question_text = "Changed"
    with pytest.raises(ValueError, match="definition changed"):
        runtime.open(runtime.store.items(instance)[0]["id"])


@pytest.mark.parametrize("change", ["definition", "hash", "both"])
def test_cached_definition_detects_external_database_edits(tmp_path, change):
    runtime, instance = coordinator(tmp_path)
    definition = runtime.workflow.to_dict()
    definition["steps"][0]["survey"]["questions"][0]["question_text"] = "Changed"
    with sqlite3.connect(runtime.store.path) as db:
        if change in {"definition", "both"}:
            db.execute(
                "UPDATE workflow_instances SET definition=? WHERE id=?",
                (json.dumps(definition), instance),
            )
        if change in {"hash", "both"}:
            db.execute(
                "UPDATE workflow_instance_contracts SET definition_hash=? WHERE instance_id=?",
                (definition_fingerprint(definition), instance),
            )
    with pytest.raises(ValueError, match="definition changed|fingerprint"):
        runtime.store.assert_definition(instance, runtime.workflow.to_dict())


def test_definition_return_value_cannot_poison_validation_cache(tmp_path):
    runtime, instance = coordinator(tmp_path)
    returned = runtime.store.definition(instance)
    returned["steps"][0]["survey"]["questions"][0]["question_text"] = "Changed"
    runtime.store.assert_definition(instance, runtime.workflow.to_dict())
    assert (
        runtime.store.definition(instance)["steps"][0]["survey"]["questions"][0][
            "question_text"
        ]
        == "Reply"
    )


def test_definition_cache_distinguishes_booleans_from_integers(tmp_path):
    runtime, instance = coordinator(tmp_path)
    definition = runtime.workflow.to_dict()
    definition["metadata"]["value"] = True
    with sqlite3.connect(runtime.store.path) as db:
        db.execute(
            "UPDATE workflow_instances SET definition=? WHERE id=?",
            (json.dumps(definition), instance),
        )
        db.execute(
            "UPDATE workflow_instance_contracts SET definition_hash=? WHERE instance_id=?",
            (definition_fingerprint(definition), instance),
        )
    runtime.store.assert_definition(instance, definition)
    definition["metadata"]["value"] = 1
    with pytest.raises(ValueError, match="definition changed"):
        runtime.store.assert_definition(instance, definition)


def test_render_history_preserves_orders_and_observes_new_completions(tmp_path):
    workflow = Workflow("history")
    review = workflow.step(
        "review",
        Survey([QuestionFreeText(question_name="reply", question_text="Reply")]),
        assigned_to=role("reviewer"),
    )
    workflow.step(
        "final",
        Survey([QuestionFreeText(question_name="final", question_text="Summarize")]),
        after=review,
        assigned_to=role("editor"),
    )
    store = SQLiteWorkflowStore(tmp_path / "history.sqlite")
    runtime = WorkflowCoordinator(workflow.compile(), store)
    instance = runtime.launch(
        [
            Agent(name="a", traits={"role": "reviewer"}),
            Agent(name="b", traits={"role": "reviewer"}),
            Agent(name="editor", traits={"role": "editor"}),
        ]
    )
    items = store.items(instance, step_name="review")
    for index, item in enumerate(reversed(items)):
        runtime.submit(
            item["id"], {"reply": item["participant_id"]}, idempotency_key=item["id"]
        )
        if index == 0:
            assert "review" not in store.render_history(instance)[0]
    answers, submissions = store.render_history(instance)
    assert answers["review"] == store.step_answers(instance, "review")
    assert [answer["reply"] for answer in answers["review"]] == [
        item["participant_id"] for item in reversed(items)
    ]
    assert [submission["participant_id"] for submission in submissions["review"]] == [
        item["participant_id"] for item in items
    ]
    assert "final" not in answers
