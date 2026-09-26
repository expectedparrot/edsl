"""Portable execution, durable observation pauses, and fresh-process replay."""

import json
import os
from pathlib import Path
import subprocess
import sys
from dataclasses import replace

import pytest

from edsl import Agent, QuestionDict, QuestionFreeText, Survey
from edsl.sharedstate import (
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    call_market,
    current,
    field,
)
from edsl.workflows import (
    ExecutionPlan,
    HumanWorkflow,
    Workflow,
    WorkflowExperiment,
    role,
    scripted,
)


def test_pause_drains_released_work_before_releasing_successors(tmp_path):
    from edsl.workflows import HumanStep, SQLiteWorkflowStore, WorkflowCoordinator

    experiment = small_experiment()
    other = HumanStep(
        "other",
        Survey([QuestionFreeText(question_name="done", question_text="Done?")]),
        assignee=role("exchange"),
    )
    workflow = replace(experiment.workflow, steps=(*experiment.workflow.steps, other))
    backend = SQLiteStateBackend(experiment.states[0], tmp_path / "state.sqlite")
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        workflow, store, state_backends={"market": backend}
    )
    instance = coordinator.launch(experiment.agents)

    def submit(step, answers):
        item = store.items(instance, step_name=step)[0]["id"]
        coordinator.open(item)
        coordinator.submit(item, answers, idempotency_key=step)

    submit(
        "order-1",
        experiment.execution_plan.resolve({"role": "trader"}).options["answers"],
    )
    submit("settle-1", {"clear": "clear"})
    assert store.instance_status(instance) == "running"
    assert store.items(instance, step_name="order-2")[0]["status"] == "blocked"
    submit("other", {"done": "yes"})
    assert store.instance_status(instance) == "paused"
    assert store.pending_outbox() == []
    item = store.items(instance, step_name="order-2")[0]["id"]
    with pytest.raises(ValueError, match="paused"):
        coordinator.open(item)
    restored = WorkflowCoordinator.restore(
        instance, store, state_backends={"market": backend}
    )
    restored.recover(instance)
    assert store.instance_status(instance) == "paused"
    restored.resume(instance)
    assert store.items(instance, step_name="order-2")[0]["status"] == "ready"


def test_live_executor_uses_edsl_and_archives_the_test_model_response(tmp_path):
    from edsl.workflows import llm

    experiment = small_experiment()
    answer = experiment.execution_plan.resolve({"role": "trader"}).options["answers"][
        "decision"
    ]
    experiment.execution_plan = ExecutionPlan().bind(
        role("trader"),
        llm(model="test", parameters={"canned_response": json.dumps(answer)}),
    )
    experiment.execution_plan = experiment.execution_plan.bind(
        role("exchange"), scripted(answers={"clear": "clear"})
    )
    result = experiment.run(tmp_path / "live-test")
    assert result["status"] == "paused"
    calls = (tmp_path / "live-test/model-calls.jsonl").read_text().splitlines()
    assert len(calls) == 1
    assert json.loads(calls[0])["result"]["answer"]["decision"] == answer


def test_portable_load_rejects_code_questions_before_instantiation():
    data = small_experiment().to_dict()
    data["workflow"]["steps"][0]["survey"]["questions"][0][
        "question_type"
    ] = "functional"
    with pytest.raises(ValueError, match="functional Python"):
        WorkflowExperiment.from_dict(data)


def small_experiment(*, resume_when=True):
    machine = call_market(["A"], periods=3, initial_shares=1)
    states = SharedStateMap(SharedState(market=machine), state_id="market")
    market = states.by("session").market
    builder = Workflow("pause test")
    agents = [
        Agent(name="A", traits={"role": "trader"}),
        Agent(name="exchange", traits={"role": "exchange"}),
    ]
    q = QuestionDict(
        question_name="decision",
        question_text="Choose.",
        answer_keys=[
            "forecast_0",
            "forecast_2",
            "forecast_5",
            "forecast_10",
            "side",
            "price",
            "quantity",
            "rationale",
        ],
        value_types=["float"] * 4 + ["str", "float", "int", "str"],
    )
    previous = None
    for t in range(1, 4):
        orders = builder.step(
            f"order-{t}",
            Survey([q]),
            after=previous,
            assigned_to=role("trader"),
            reads=(market.read(),),
            writes=(
                market.submit(trader=current.agent.name, period=t, decision=q.answer),
            ),
        )
        previous = builder.step(
            f"settle-{t}",
            Survey([QuestionFreeText(question_name="clear", question_text="Clear.")]),
            assigned_to=role("exchange"),
            after=orders,
            writes=(market.settle(period=t),),
        )
        if t == 1:
            builder.pause_after(
                previous,
                name="checkpoint",
                read=market.read(),
                condition=field("period") == 2,
                resume_when=resume_when,
            )
    answer = {
        "forecast_0": 14,
        "forecast_2": 14,
        "forecast_5": 14,
        "forecast_10": 14,
        "side": "hold",
        "price": 0,
        "quantity": 0,
        "rationale": "test",
    }
    plan = ExecutionPlan().bind(role("trader"), scripted(answers={"decision": answer}))
    plan = plan.bind(role("exchange"), scripted(answers={"clear": "clear"}))
    return WorkflowExperiment(builder.compile(), [states], agents, plan)


def test_json_roundtrip_pause_restore_resume_preserves_live_inventory(tmp_path):
    experiment = small_experiment()
    data = json.loads(json.dumps(experiment.to_dict()))
    assert data["workflow"]["version"] == 3
    loaded = WorkflowExperiment.from_dict(data)
    assert loaded.to_dict() == data
    first = loaded.run(tmp_path / "run", responses=[])
    assert first["status"] == "paused" and first["completed_items"] == 2
    state = (
        SQLiteStateBackend(loaded.states[0], tmp_path / "run/state-0.sqlite")
        .snapshot("session")
        .state["market"]
    )
    assert state["accounts"]["A"]["shares"] == 1 and not state["finished"]
    second = WorkflowExperiment.from_dict(data).run(
        tmp_path / "run", responses=[], resume=True
    )
    assert second["status"] == "completed" and second["completed_items"] == 6
    assert len(second["pauses"]) == 1
    state = (
        SQLiteStateBackend(loaded.states[0], tmp_path / "run/state-0.sqlite")
        .snapshot("session")
        .state["market"]
    )
    assert state["finished"] and state["accounts"]["A"]["shares"] == 0


def test_resume_guard_and_pinned_configuration_are_enforced(tmp_path):
    experiment = small_experiment(resume_when=False)
    experiment.run(tmp_path / "run", responses=[])
    with pytest.raises(ValueError, match="resume condition"):
        experiment.run(tmp_path / "run", responses=[], resume=True)
    experiment.metadata["changed"] = True
    with pytest.raises(ValueError, match="specification changed"):
        experiment.run(tmp_path / "run", responses=[], resume=True)


def test_invalid_pause_boundaries_and_missing_capabilities_fail_early():
    experiment = small_experiment()
    data = experiment.to_dict()
    data["workflow"]["pause_rules"][0]["after"] = "missing"
    with pytest.raises(ValueError, match="unknown boundary"):
        WorkflowExperiment.from_dict(data)
    runtime = experiment.runtime
    del runtime.algorithms[("call_market_settle", 1)]
    with pytest.raises(ValueError, match="unregistered"):
        WorkflowExperiment.from_dict(experiment.to_dict(), runtime=runtime)


def test_existing_workflow_serialization_stays_at_version_two():
    experiment = small_experiment()
    workflow = HumanWorkflow(experiment.workflow.name, experiment.workflow.steps)
    assert workflow.to_dict()["version"] == 2
    assert "pause_rules" not in workflow.to_dict()
    assert HumanWorkflow.from_dict(workflow.to_dict()).to_dict() == workflow.to_dict()


def test_saved_market_replays_in_process_that_forbids_example_imports(tmp_path):
    root = Path(__file__).resolve().parents[2]
    fixture = root / "examples/asset_market/portable"
    script = """
import importlib.abc, json, sys
from pathlib import Path
network_attempts = []
def forbid_network(event, args):
    if event in {"socket.connect", "socket.getaddrinfo"}:
        network_attempts.append(event)
        raise AssertionError("replay attempted network access: " + event)
sys.addaudithook(forbid_network)
class BlockExamples(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "examples" or fullname.startswith("examples."):
            raise AssertionError("experiment-specific Python import: " + fullname)
sys.meta_path.insert(0, BlockExamples())
from edsl.workflows import WorkflowExperiment
from edsl.sharedstate import SQLiteStateBackend
fixture, output = map(Path, sys.argv[1:])
experiment = WorkflowExperiment.load(fixture / "experiment.json")
answers = json.loads((fixture / "responses.json").read_text())
first = experiment.run(output, responses=answers)
assert first["status"] == "paused" and first["completed_items"] == 156
assert first["pauses"][-1]["rule"] == "observation-cap-12"
experiment = WorkflowExperiment.load(fixture / "experiment.json")
second = experiment.run(output, responses=answers, resume=True)
assert second["status"] == "paused" and second["completed_items"] == 221
assert second["pauses"][-1]["rule"] == "overpricing-17"
backend = SQLiteStateBackend(experiment.states[0], output / "state-0.sqlite")
state = backend.snapshot("session").state["market"]
expected = json.loads((fixture / "expected.json").read_text())
assert state["tape"] == expected["tape"]
assert state["accounts"] == expected["accounts"]
assert state["order_log"] == expected["orders"]
assert not state["finished"] and state["period"] == 18
assert not (output / "model-calls.jsonl").exists()
assert not network_attempts, network_attempts
print(json.dumps({"matched": True, "rounds": len(state["tape"]), "decisions": len(state["order_log"])}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(fixture), str(tmp_path / "run")],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(root)},
        text=True,
        capture_output=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["matched"]


def batch_experiment():
    from edsl.workflows import llm

    agents = [
        Agent(name=name, traits={"role": "trader", "private_token": name + "-secret"})
        for name in ["A", "B"]
    ]
    agents.append(Agent(name="exchange", traits={"role": "exchange"}))
    states = SharedStateMap(
        SharedState(market=call_market(["A", "B"])), state_id="batch-market"
    )
    workflow = Workflow("batch interviews")
    orders = workflow.step(
        "orders",
        Survey(
            [
                QuestionFreeText(
                    question_name="response",
                    question_text="Your private token is {{ participant.private_token }}; cash {{ shared_state.market.your_account.cash_cents }}.",
                )
            ]
        ),
        assigned_to=role("trader"),
        reads=(states.by("session").market.read(),),
    )
    workflow.step(
        "settle",
        Survey([QuestionFreeText(question_name="clear", question_text="Clear")]),
        assigned_to=role("exchange"),
        after=orders,
    )
    plan = (
        ExecutionPlan()
        .bind(role("trader"), llm(model="test", parameters={"canned_response": "ok"}))
        .bind(role("exchange"), scripted(answers={"clear": "done"}))
    )
    return WorkflowExperiment(workflow.compile(), [states], agents, plan)


def test_batch_is_one_job_with_private_surveys_and_unordered_results(
    tmp_path, monkeypatch
):
    from edsl.jobs import Jobs
    from edsl.workflows import SQLiteWorkflowStore

    actual_run, calls = Jobs.run, []

    def observed_run(job, **kwargs):
        # The explicit pairings must survive persistence as an ordinary Jobs.
        job = Jobs.from_dict(job.to_dict())
        interviews = list(job.generate_interviews())
        calls.append(len(interviews))
        assert len(interviews) == 2
        for interview in interviews:
            text = (
                interview.survey.questions[0]
                .render({**interview.scenario, "agent": interview.agent})
                .question_text
            )
            assert interview.agent.name + "-secret" in text
            other = "B" if interview.agent.name == "A" else "A"
            assert other + "-secret" not in text
            assert other + "-secret" not in json.dumps(interview.scenario.to_dict())
        result = actual_run(job, **kwargs)
        # Check the actual rendered provider prompts, not just template inputs.
        for row in result:
            prompt = row.to_dict()["prompt"]["response_user_prompt"]["text"]
            assert row.agent.name + "-secret" in prompt
            other = "B" if row.agent.name == "A" else "A"
            assert other + "-secret" not in prompt
            row.answer["response"] = row.agent.name
        result.data.reverse()
        return result

    monkeypatch.setattr(Jobs, "run", observed_run)
    output = tmp_path / "batch"
    result = batch_experiment().run(output)
    assert result["status"] == "completed" and result["completed_items"] == 3
    assert calls == [2]
    store = SQLiteWorkflowStore(output / "workflow.sqlite")
    with store.connect() as db:
        answers = db.execute(
            "select i.participant_id,s.answers from workflow_submissions s join workflow_items i on i.id=s.work_item_id where i.step_name='orders'"
        ).fetchall()
    assert {name: json.loads(answer)["response"] for name, answer in answers} == {
        "A": "A",
        "B": "B",
    }
    assert len((output / "model-calls.jsonl").read_text().splitlines()) == 2


def test_partial_batch_keeps_success_and_retries_only_missing_participant(
    tmp_path, monkeypatch
):
    from edsl.jobs import Jobs
    from edsl.workflows import SQLiteWorkflowStore

    actual_run, counts = Jobs.run, []

    def incomplete_once(job, **kwargs):
        counts.append(len(list(job.generate_interviews())))
        result = actual_run(job, **kwargs)
        if len(counts) == 1:
            result.data.pop()
        return result

    monkeypatch.setattr(Jobs, "run", incomplete_once)
    experiment = batch_experiment()
    output = tmp_path / "partial"
    with pytest.raises(ValueError, match="incomplete batch"):
        experiment.run(output)
    store = SQLiteWorkflowStore(output / "workflow.sqlite")
    assert store.items("experiment", step_name="settle")[0]["status"] == "blocked"
    result = experiment.run(output, resume=True)
    assert result["status"] == "completed" and result["completed_items"] == 3
    assert counts == [2, 1]
    assert len((output / "model-calls.jsonl").read_text().splitlines()) == 2


def test_null_result_never_creates_immutable_submission_intent(tmp_path, monkeypatch):
    from edsl.jobs import Jobs
    from edsl.workflows import SQLiteWorkflowStore

    actual_run, counts = Jobs.run, []

    def null_once(job, **kwargs):
        counts.append(len(list(job.generate_interviews())))
        result = actual_run(job, **kwargs)
        if len(counts) == 1:
            result.data[0].answer["response"] = None
        return result

    monkeypatch.setattr(Jobs, "run", null_once)
    experiment = batch_experiment()
    output = tmp_path / "null-result"
    with pytest.raises(ValueError, match="incomplete model result"):
        experiment.run(output)
    store = SQLiteWorkflowStore(output / "workflow.sqlite")
    unfinished = [
        i
        for i in store.items("experiment", step_name="orders")
        if i["status"] != "completed"
    ]
    assert len(unfinished) == 1
    assert store.submission_intent(unfinished[0]["id"]) is None
    assert experiment.run(output, resume=True)["status"] == "completed"
    assert counts == [2, 1]


def test_unsupported_builtin_fails_before_portable_execution_creates_artifacts(
    tmp_path,
):
    from edsl.sharedstate import UnsupportedCapabilityError
    from edsl.sharedstate.dsl_runtime import Runtime

    experiment = small_experiment()
    supported = set(Runtime().capability_manifest()["supported"]) - {"expression:ref@1"}
    destination = Runtime(capabilities=supported)
    for (name, version), implementation in experiment.runtime.algorithms.items():
        destination.register(
            name,
            version,
            implementation,
            validate_constants=experiment.runtime.validators.get((name, version)),
        )
    with pytest.raises(UnsupportedCapabilityError, match="expression:ref@1"):
        WorkflowExperiment.from_dict(
            json.loads(json.dumps(experiment.to_dict())), runtime=destination
        )
    # An advertisement/validation earlier in the session cannot replace the
    # check at the actual launch boundary after the runtime has changed.
    experiment.runtime = destination
    output = tmp_path / "unsupported"
    with pytest.raises(UnsupportedCapabilityError, match="expression:ref@1"):
        experiment.run(output, responses=[])
    assert not output.exists()
