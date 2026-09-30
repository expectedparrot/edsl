"""Service boundaries must not discard shared-state execution semantics."""

import json
from uuid import uuid4

import pytest

from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
from edsl.runner.serialization import deserialize_job, serialize_job
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    field,
    set_,
    state_field,
)


def counter_job():
    machine = Machine(
        name="Counter",
        constants={},
        fields={"count": state_field(T.integer(), 0)},
        commands={
            "increment": Command(
                inputs={}, effects=(set_("count", field("count") + 1),)
            )
        },
        view={"count": field("count")},
        complete_when=field("count") >= 2,
    )
    states = SharedStateMap(SharedState(counter=machine), state_id=str(uuid4()))
    counter = states.by("room").counter
    question = QuestionFreeText(
        question_name="answer", question_text="Count: {{ shared_state.counter.count }}"
    )
    job = (
        Survey([counter.read(), question, counter.increment()])
        .by(Agent(name="first"), Agent(name="second"))
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = "serial"
    return job


def test_runner_wire_preserves_schedule_and_steps():
    job = counter_job()
    for payload in (serialize_job(job), {**job.to_dict(), "_type": "Job"}):
        restored = deserialize_job(json.loads(json.dumps(payload)))
        assert restored.run_config.parameters.interview_schedule == "serial"
        assert (
            restored.survey.to_dict()["state_steps"]
            == job.survey.to_dict()["state_steps"]
        )


def test_separate_services_read_writes_and_reconstruct_provenance(tmp_path):
    storage = InMemoryStorage()

    def factory(job_id, state_map):
        return SQLiteStateBackend(
            state_map, tmp_path / job_id / f"{state_map.state_id}.sqlite"
        )

    def service():
        return JobService(storage, state_backend_factory=factory, distributed=True)

    job = counter_job()
    job_id, _, _ = service().submit_job(job)
    renderer = service()
    definition = renderer.jobs.get_definition(job_id)
    assert renderer._get_interview_schedule(job_id) == "serial"
    for index, interview_id in enumerate(definition.interview_ids):
        interview = renderer.interviews.get_definition(job_id, interview_id)
        task_id = interview.task_ids[0]
        view, _ = renderer.state_for_direct_answer(job_id, interview_id, task_id)
        assert view["counter"]["count"] == index
        # A separately constructed worker commits the answer and state effect.
        service().on_task_completed(job_id, interview_id, task_id, "ok", validated=True)

    published = storage.read_persistent(f"job:{job_id}:shared_state_results")
    bindings = service().shared_state_results(job_id)["bindings"]
    assert published["bindings"] == bindings
    assert len(bindings) == 1
    assert bindings[0]["entry_snapshots"][0]["state"]["counter"]["count"] == 0
    assert bindings[0]["exit_snapshots"][0]["state"]["counter"]["count"] == 2
    assert [e["version"] for e in bindings[0]["events"] if e["kind"] == "write"] == [
        1,
        2,
    ]


@pytest.mark.parametrize(
    "within_round,error",
    [
        ("concurrent", "requires a transition lock"),
        ("serial", "requires a transition lock"),
    ],
)
def test_uncoordinated_conditions_fail_before_creating_tasks(within_round, error):
    storage = InMemoryStorage()
    job = counter_job()
    step = job.survey._state_reads["answer"][0]
    condition = (
        SharedStateMap(step.definition, state_id=step.state_id)
        .by("room")
        .counter.is_complete()
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=2, within_round=within_round, stop_when=condition
    )
    with pytest.raises(ValueError, match=error):
        JobService(storage, distributed=True).submit_job(job)
    assert storage.stats()["persistent_keys"] == 0


def test_distributed_state_cannot_fall_back_to_local_disk():
    storage = InMemoryStorage()
    with pytest.raises(ValueError, match="configured distributed state backend"):
        JobService(storage, distributed=True).submit_job(counter_job())
    assert storage.stats()["persistent_keys"] == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"count": 0},
        {"count": True},
        {"count": 1.5},
        {"within_round": "unordered"},
        {"state_visibility": "eventual"},
        {"round_order": "random"},
        {"reveal": "live"},
    ],
)
def test_invalid_serialized_round_policy_creates_no_tasks(changes):
    from edsl.jobs.exceptions import JobsValueError

    payload = InterviewSchedule.rounds(count=2).to_dict() | changes
    job = counter_job()
    job.run_config.parameters.interview_schedule = InterviewSchedule.from_dict(payload)
    storage = InMemoryStorage()
    with pytest.raises(JobsValueError):
        JobService(storage, distributed=True).submit_job(job)
    assert storage.stats()["persistent_keys"] == 0


def test_snapshot_rounds_require_durable_checkpoint_capability(tmp_path):
    job = counter_job()
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(count=2)
    storage = InMemoryStorage()
    service = JobService(
        storage,
        distributed=True,
        state_backend_factory=lambda _, state_map: SQLiteStateBackend(
            state_map, tmp_path / "state.sqlite"
        ),
    )
    with pytest.raises(ValueError, match="durable checkpoints"):
        service.submit_job(job)
    assert storage.stats()["persistent_keys"] == 0


@pytest.mark.parametrize(
    "module,anchor,dependency",
    [
        ("uniform_price_auction", "bid_1", "bid_0"),
        ("balanced_assignment", "experience", "age_group"),
    ],
)
@pytest.mark.parametrize("roundtrip", [False, True])
def test_state_command_inputs_create_task_dependencies(
    module, anchor, dependency, roundtrip, tmp_path
):
    from importlib import import_module
    from edsl.runner.models import TaskStatus

    example = import_module(f"examples.{module}")
    survey = example.build_survey()[0]
    if roundtrip:
        survey = Survey.from_dict(survey.to_dict())
    service = JobService(
        InMemoryStorage(),
        distributed=True,
        state_backend_factory=lambda jid, state: SQLiteStateBackend(
            state, tmp_path / f"{jid}.sqlite"
        ),
    )
    jid, _, _ = service.submit_job(survey.by(Model("test")))
    iid = service.jobs.get_definition(jid).interview_ids[0]
    definitions = [
        service.tasks.get_definition(jid, iid, tid)
        for tid in service.interviews.get_definition(jid, iid).task_ids
    ]
    tasks = {task.question_name: task for task in definitions}
    assert tasks[dependency].task_id in tasks[anchor].depends_on
    assert service.tasks.get_status(tasks[anchor].task_id) == TaskStatus.PENDING
