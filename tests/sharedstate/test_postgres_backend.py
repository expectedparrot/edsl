"""Run with EDSL_TEST_POSTGRES_URL pointing at a disposable/local test database."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import os
from uuid import uuid4

import pytest

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
    resolve_read,
    resolve_write,
)
from edsl.sharedstate.steps import StepContext
from edsl.sharedstate.exceptions import SharedStateRuntimeError


@pytest.fixture
def database():
    url = os.environ.get("EDSL_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("EDSL_TEST_POSTGRES_URL is not configured")
    from sqlalchemy import create_engine, delete
    from edsl.sharedstate.postgres import (
        PostgresStateBackend,
        definitions,
        events,
        checkpoints,
    )

    engine = create_engine(url, pool_pre_ping=True)
    PostgresStateBackend.create_schema(engine)
    namespace = "test-" + str(uuid4())
    yield engine, namespace
    with engine.begin() as conn:
        for table in (checkpoints, events, definitions):
            conn.execute(
                delete(table).where(
                    table.c.namespace.in_([namespace, namespace + "-other"])
                )
            )
    engine.dispose()


def counter():
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
    return SharedStateMap(SharedState(counter=machine), state_id="same-client-id")


def test_concurrent_writes_deduplicate_and_namespaces_isolate(database):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    step = state.by("room").counter.increment()
    operations = [
        resolve_write(step, StepContext({}, f"worker-{i}")) for i in range(20)
    ]

    def write(operation):
        return PostgresStateBackend(state, engine, namespace=namespace).apply(operation)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, operations + operations))
    reopened = PostgresStateBackend(state, engine, namespace=namespace)
    assert reopened.snapshot("room").state["counter"]["count"] == 20
    assert reopened.snapshot("room").version == 20
    assert len(reopened.history()) == 20
    isolated = PostgresStateBackend(state, engine, namespace=namespace + "-other")
    assert isolated.snapshot("room").version == 0
    assert reopened.snapshot("another-room").version == 0
    with pytest.raises(SharedStateRuntimeError, match="idempotency"):
        reopened.apply(replace(operations[0], runtime_context={"different": True}))


def test_postgres_matches_sqlite_snapshots_reads_and_close(database, tmp_path):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    target = state.by("room").counter
    backends = [
        SQLiteStateBackend(state, tmp_path / "state.sqlite"),
        PostgresStateBackend(state, engine, namespace=namespace),
    ]
    outputs = []
    for backend in backends:
        backend.apply(resolve_write(target.increment(), StepContext({}, "first")))
        checkpoint = backend.checkpoint()
        backend.apply(resolve_write(target.increment(), StepContext({}, "second")))
        observation = backend.read(
            resolve_read(target.read(), StepContext({}, "reader")),
            at_sequence=checkpoint,
        )
        assert observation.value == {"count": 1}
        assert observation.version == 1
        first_close = backend.finalize(
            target.is_complete(), "room", execution_id="closer"
        )
        duplicate = backend.finalize(
            target.is_complete(), "room", execution_id="closer"
        )
        assert first_close.observed_version == duplicate.observed_version == 3
        outputs.append(
            (
                backend.snapshot("room"),
                [(e["kind"], e["version"]) for e in backend.history()],
            )
        )
    assert outputs[0] == outputs[1]


def test_definition_changes_and_failed_commands_do_not_commit(database):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    backend = PostgresStateBackend(state, engine, namespace=namespace)
    operation = resolve_write(
        state.by("room").counter.increment(), StepContext({}, "writer")
    )
    with pytest.raises(Exception):
        backend.apply(replace(operation, command="does_not_exist"))
    assert backend.checkpoint() == 0
    backend.apply(operation)
    changed = SharedStateMap(
        SharedState(
            counter=replace(
                state.definition.machines["counter"], view={"other": field("count")}
            )
        ),
        state_id=state.state_id,
    )
    with pytest.raises(SharedStateRuntimeError, match="definition changed"):
        PostgresStateBackend(changed, engine, namespace=namespace)
    assert backend.snapshot("room").version == 1


def test_read_retries_pin_one_observation_and_reject_changed_requests(database):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    target = state.by("room").counter
    operation = resolve_read(target.read(), StepContext({}, "reader"))

    def retry(_):
        return PostgresStateBackend(state, engine, namespace=namespace).read(operation)

    with ThreadPoolExecutor(max_workers=8) as pool:
        observations = list(pool.map(retry, range(20)))
    assert all(observation == observations[0] for observation in observations)
    backend = PostgresStateBackend(state, engine, namespace=namespace)
    backend.apply(resolve_write(target.increment(), StepContext({}, "writer")))
    assert retry(None) == observations[0]
    assert observations[0].value == {"count": 0}
    assert len(backend.history()) == 2
    assert backend.read(replace(operation, read_id="new-read")).value == {"count": 1}
    for changed in (
        {"runtime_context": {"round": 2}},
        {"execution_id": "another-interview"},
        {"step_id": "another-step"},
    ):
        with pytest.raises(SharedStateRuntimeError, match="read ID was reused"):
            backend.read(replace(operation, **changed))
    with pytest.raises(SharedStateRuntimeError, match="read ID was reused"):
        backend.read(operation, at_sequence=0)
    assert len(backend.history()) == 3


def test_render_recovery_after_read_commit_and_delayed_phase_retry(database):
    from edsl import Agent, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    target = state.by("room").counter

    class InterruptedStorage(InMemoryStorage):
        interrupt = True

        def write_persistent(self, key, value):
            if self.interrupt and ":state_observation:" in key:
                self.interrupt = False
                raise RuntimeError("renderer crashed after committing state read")
            super().write_persistent(key, value)

    storage = InterruptedStorage()

    def service():
        return JobService(
            storage,
            distributed=True,
            state_backend_factory=lambda job_id, state_map: PostgresStateBackend(
                state_map, engine, namespace=namespace
            ),
        )

    def question(name):
        return QuestionFreeText(question_name=name, question_text="State?")

    job = (
        Survey(
            [
                target.read(),
                question("first"),
                question("inherited"),
                target.read(),
                question("second"),
                question("after"),
            ]
        )
        .by(Agent())
        .by(Model("test"))
    )
    submitted = service()
    job_id, _, _ = submitted.submit_job(job)
    interview_id = submitted.jobs.get_definition(job_id).interview_ids[0]
    task_ids = submitted.interviews.get_definition(job_id, interview_id).task_ids

    def render(index):
        return service().state_for_direct_answer(job_id, interview_id, task_ids[index])

    with pytest.raises(RuntimeError, match="renderer crashed"):
        render(0)
    backend = PostgresStateBackend(state, engine, namespace=namespace)
    backend.apply(resolve_write(target.increment(), StepContext({}, "writer")))
    first = render(0)
    assert first[0] == {"counter": {"count": 0}}
    assert render(1) == first
    second = render(2)
    assert second[0] == {"counter": {"count": 1}}
    assert render(0) == first  # A late retry cannot rewind a later phase.
    assert render(1) == first  # Nor can it inherit the later phase's observation.
    assert render(3) == second
    assert len([event for event in backend.history() if event["kind"] == "read"]) == 2


def test_round_checkpoints_are_atomic_and_survive_reconstruction(database):
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()

    def backend():
        return PostgresStateBackend(state, engine, namespace=namespace)

    def pin(_):
        return backend().pin_checkpoint(["round", "group-a", 0])

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(pin, range(20))) == [0] * 20
    backend().apply(
        resolve_write(state.by("room").counter.increment(), StepContext({}, "writer"))
    )
    assert pin(None) == 0  # Zero is a valid, durable checkpoint.
    assert backend().pin_checkpoint(["round", "group-a", 1]) == 1
    assert backend().pin_checkpoint(["round", "group-b", 0]) == 1
    isolated = PostgresStateBackend(state, engine, namespace=namespace + "-other")
    assert isolated.pin_checkpoint(["round", "group-a", 1]) == 0


def test_snapshot_rounds_pin_before_first_write_and_recover_barriers(database):
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    state = counter()
    target = state.by("room").counter
    storage = InMemoryStorage()

    def service():
        return JobService(
            storage,
            distributed=True,
            state_backend_factory=lambda _, state_map: PostgresStateBackend(
                state_map, engine, namespace=namespace
            ),
        )

    job = (
        Survey(
            [
                QuestionFreeText(question_name="write", question_text="Write first"),
                target.increment(),
                target.read(),
                QuestionFreeText(
                    question_name="observe", question_text="Observe later"
                ),
            ]
        )
        .by(Agent(name="a"), Agent(name="b"))
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(count=2)
    job_id, _, _ = service().submit_job(job)
    tasks = {}
    for iid in service().jobs.get_definition(job_id).interview_ids:
        for tid in service().interviews.get_definition(job_id, iid).task_ids:
            tasks[tid] = service().tasks.get_definition(job_id, iid, tid)
    completed = set()
    while len(completed) < len(tasks):
        tid = service().tasks.pop_ready_task(job_id)
        assert tid is not None, "the persisted barrier must release the next round"
        task = tasks[tid]
        assert all(parent in completed for parent in task.depends_on)
        if task.iteration == 1:
            assert all(
                t.task_id in completed for t in tasks.values() if t.iteration == 0
            )
        observation = service().state_for_direct_answer(job_id, task.interview_id, tid)
        if task.question_name == "observe":
            assert observation[0] == {"counter": {"count": 2 * task.iteration}}
        service().on_task_completed(
            job_id, task.interview_id, tid, "ok", validated=True
        )
        completed.add(tid)
    assert (
        PostgresStateBackend(state, engine, namespace=namespace)
        .snapshot("room")
        .state["counter"]["count"]
        == 4
    )
    for task in tasks.values():
        if task.question_name == "observe":
            assert service().state_for_direct_answer(
                job_id, task.interview_id, task.task_id
            )[0] == {"counter": {"count": 2 * task.iteration}}
