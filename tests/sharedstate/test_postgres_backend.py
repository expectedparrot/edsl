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


def test_answer_pin_survives_crash_after_postgres_effect(database):
    from edsl import Agent, Model, QuestionNumerical, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.sharedstate import input_
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    machine = Machine(
        name="Total",
        constants={},
        fields={"total": state_field(T.integer(), 0)},
        commands={
            "add": Command(
                inputs={"amount": T.integer()},
                effects=(set_("total", field("total") + input_("amount")),),
            )
        },
        view={"total": field("total")},
    )
    state = SharedStateMap(
        SharedState(counter=machine), state_id="accepted-answer-test"
    )
    question = QuestionNumerical(question_name="amount", question_text="How much?")
    job = (
        Survey([question, state.by("room").counter.add(amount=question.answer)])
        .by(Agent())
        .by(Model("test"))
    )
    storage = InMemoryStorage()

    class InterruptedService(JobService):
        def _execute_shared_state_steps(self, *args):
            super()._execute_shared_state_steps(*args)
            raise RuntimeError("worker died after state effect")

    def service(cls=JobService):
        return cls(
            storage,
            distributed=True,
            state_backend_factory=lambda _, state_map: PostgresStateBackend(
                state_map, engine, namespace=namespace
            ),
        )

    job_id, _, _ = service().submit_job(job)
    iid = service().jobs.get_definition(job_id).interview_ids[0]
    tid = service().interviews.get_definition(job_id, iid).task_ids[0]
    with pytest.raises(RuntimeError, match="worker died"):
        service(InterruptedService).on_task_completed(
            job_id, iid, tid, 3, user_prompt="first", validated=True
        )
    # A new worker returns a different answer. Recovery must replay amount=3,
    # not reject changed operation inputs or replace the persisted result.
    service().on_task_completed(
        job_id, iid, tid, 17, user_prompt="retry", validated=True
    )
    backend = PostgresStateBackend(state, engine, namespace=namespace)
    assert backend.snapshot("room").state["counter"]["total"] == 3
    assert len(backend.history()) == 1
    assert backend.history()[0]["inputs"] == {"amount": 3}
    answer = service().answers.get(job_id, iid, "amount")
    assert (answer.answer, answer.user_prompt) == (3, "first")
    assert service().jobs.get_state(job_id).value == "completed"


@pytest.mark.parametrize("policy", ["rounds", "grouped"])
@pytest.mark.parametrize("crash_at", ["write", "stop", "close", "skip"])
def test_stop_and_finalize_recover_per_group(database, policy, crash_at):
    from sqlalchemy import create_engine
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.runner.transition_lock import PostgresJobTransitionLock
    from edsl.sharedstate import current
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    lock_engine = create_engine(engine.url)
    lock = PostgresJobTransitionLock(lock_engine)
    # Closing deliberately clears the predicate. Recovery must retain the stop.
    machine = replace(
        counter().definition.machines["counter"], close_effects=(set_("count", 0),)
    )
    state = SharedStateMap(SharedState(counter=machine), state_id="stop-test")
    target = state.by(current.agent.group).counter
    condition = target.is_complete()
    storage = InMemoryStorage()
    fired = False

    def interrupt(point):
        nonlocal fired
        if point == crash_at and not fired:
            fired = True
            raise RuntimeError("simulated process death")

    class Backend(PostgresStateBackend):
        def apply(self, operation):
            result = super().apply(operation)
            if self.snapshot(operation.scope.value).state["counter"]["count"] == 2:
                interrupt("write")
            return result

        def finalize(self, *args, **kwargs):
            result = super().finalize(*args, **kwargs)
            if any(e.get("command") == "$close" for e in self.history()):
                interrupt("close")
            return result

    class Storage:
        def __getattr__(self, name):
            return getattr(storage, name)

        def get_or_set_volatile(self, key, value):
            result = storage.get_or_set_volatile(key, value)
            if ":shared_state_stop:" in key:
                interrupt("stop")
            return result

        def increment_volatile_once(self, key, *args):
            result = storage.increment_volatile_once(key, *args)
            if key.endswith(":skipped"):
                interrupt("skip")
            return result

    def service():
        return JobService(
            Storage(),
            distributed=True,
            transition_lock=lock,
            state_backend_factory=lambda _, state_map: Backend(
                state_map, engine, namespace=namespace
            ),
        )

    schedule_args = dict(
        group_by="group", order_by="seat", stop_when=condition, finalize_when=condition
    )
    schedule = (
        InterviewSchedule.rounds(count=2, within_round="serial", **schedule_args)
        if policy == "rounds"
        else InterviewSchedule.grouped_round_robin(**schedule_args)
    )
    job = (
        Survey(
            [
                QuestionFreeText(question_name="answer", question_text="Say ok"),
                target.increment(),
                QuestionFreeText(question_name="after", question_text="After"),
            ]
        )
        .by(
            [
                Agent(name=f"{group}-{seat}", traits={"group": group, "seat": seat})
                for group in ("a", "b")
                for seat in range(3)
            ]
        )
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = schedule
    try:
        jid, _, _ = service().submit_job(job)
        finished = []
        while (tid := service().tasks.pop_ready_task(jid)) is not None:
            _, iid = service().tasks.get_location(tid)
            try:
                skipped, _ = service().should_skip_task(jid, iid, tid)
                if skipped:
                    service().on_task_skipped(jid, iid, tid)
                else:
                    service().on_task_completed(
                        jid, iid, tid, "original", validated=True
                    )
            except RuntimeError as exc:
                assert "simulated process death" in str(exc)
                accepted = storage.read_volatile(
                    f"job:{jid}:task:{tid}:accepted_answer"
                )
                if accepted:
                    assert service().should_skip_task(jid, iid, tid) == (False, None)
                    # A stale skip callback must finish the accepted answer.
                    service().on_task_skipped(jid, iid, tid)
                else:
                    service().on_task_skipped(jid, iid, tid)
            finished.append((iid, tid))
        assert fired
        assert service().jobs.get_state(jid).value == "completed"
        history = Backend(state, engine, namespace=namespace).history()
        for scope in ("a", "b"):
            assert [e["command"] for e in history if e["scope"] == scope] == [
                "increment",
                "increment",
                "$close",
            ]
            assert (
                Backend(state, engine, namespace=namespace)
                .snapshot(scope)
                .state["counter"]["count"]
                == 0
            )
        # Late completions must not write after closure or change task counts.
        status = service().jobs.get_status(jid)
        for iid, tid in finished:
            service().on_task_completed(jid, iid, tid, "late", validated=True)
        assert service().jobs.get_status(jid) == status
        assert Backend(state, engine, namespace=namespace).history() == history
        answers = [
            a
            for iid in service().jobs.get_definition(jid).interview_ids
            for a in service().answers.get_all_for_interview(jid, iid)
        ]
        assert len(answers) == 6  # Two writes and one follow-up per group.
        assert {a.answer for a in answers} == {"original"}
    finally:
        lock_engine.dispose()


def test_initial_stop_finalizes_without_answer_writes(database):
    from sqlalchemy import create_engine
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.runner.transition_lock import PostgresJobTransitionLock
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    lock_engine = create_engine(engine.url)
    machine = replace(
        counter().definition.machines["counter"],
        complete_when=field("count") == 0,
        close_effects=(set_("count", 1),),
    )
    state = SharedStateMap(SharedState(counter=machine), state_id="initial-stop")
    condition = state.by("room").counter.is_complete()
    storage = InMemoryStorage()

    def service():
        return JobService(
            storage,
            distributed=True,
            transition_lock=PostgresJobTransitionLock(lock_engine),
            state_backend_factory=lambda _, state_map: PostgresStateBackend(
                state_map, engine, namespace=namespace
            ),
        )

    job = (
        QuestionFreeText(question_name="answer", question_text="Never asked")
        .to_survey()
        .by(Agent())
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=2, within_round="serial", stop_when=condition, finalize_when=condition
    )
    try:
        jid, _, _ = service().submit_job(job)
        skipped = 0
        while (tid := service().tasks.pop_ready_task(jid)) is not None:
            _, iid = service().tasks.get_location(tid)
            assert service().should_skip_task(jid, iid, tid)[0]
            # A completion arriving after the stop must also take the skip path.
            service().on_task_completed(jid, iid, tid, "late", validated=True)
            assert service().answers.get_all_for_interview(jid, iid) == []
            assert service().interviews.get_status(iid).skipped == 1
            skipped += 1
        assert skipped == 2
        assert service().jobs.get_state(jid).value == "completed"
        backend = PostgresStateBackend(state, engine, namespace=namespace)
        assert [e["command"] for e in backend.history()] == ["$close"]
        assert backend.snapshot("room").state["counter"]["count"] == 1
    finally:
        lock_engine.dispose()


@pytest.mark.parametrize("mode", ["stop", "finalize", "both"])
@pytest.mark.parametrize("visibility", ["snapshot", "live"])
def test_concurrent_termination_handles_late_success_and_failure(
    database, mode, visibility
):
    from sqlalchemy import create_engine
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.runner.models import TaskStatus
    from edsl.runner.transition_lock import PostgresJobTransitionLock
    from edsl.sharedstate import current
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    lock_engine = create_engine(engine.url)
    state = SharedStateMap(
        SharedState(
            counter=replace(
                counter().definition.machines["counter"],
                close_effects=(set_("count", 0),),
            )
        ),
        state_id="concurrent-stop",
    )
    target = state.by(current.agent.group).counter
    storage = InMemoryStorage()

    def service():
        return JobService(
            storage,
            distributed=True,
            transition_lock=PostgresJobTransitionLock(lock_engine),
            state_backend_factory=lambda _, state_map: PostgresStateBackend(
                state_map, engine, namespace=namespace
            ),
        )

    job = (
        Survey(
            [
                target.read(),
                QuestionFreeText(question_name="write", question_text="Write"),
                target.increment(),
                target.read(),
                QuestionFreeText(question_name="observe", question_text="Observe"),
            ]
        )
        .by(
            [
                Agent(name=f"{group}-{seat}", traits={"group": group, "seat": seat})
                for group in ("a", "b")
                for seat in range(3)
            ]
        )
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=2,
        group_by="group",
        within_round="concurrent",
        state_visibility=visibility,
        stop_when=target.is_complete() if mode != "finalize" else None,
        finalize_when=target.is_complete() if mode != "stop" else None,
    )
    try:
        jid, _, _ = service().submit_job(job)
        first, late = [], []
        while (tid := service().tasks.pop_ready_task(jid)) is not None:
            _, iid = service().tasks.get_location(tid)
            task = service().tasks.get_definition(jid, iid, tid)
            traits = service().jobs.get_agent(jid, task.agent_id)["traits"]
            assert (
                service().state_for_direct_answer(jid, iid, tid)[0]["counter"]["count"]
                == 0
            )
            service().tasks.set_status(tid, TaskStatus.RUNNING)
            (late if traits["seat"] == 2 else first).append((iid, tid))

        def complete(task):
            service().on_task_completed(jid, *task, "accepted", validated=True)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(complete, first))
        # Both callbacks had started before termination but arrive after it.
        service().on_task_failed(
            jid, *late[0], "timeout", "late failure", force_permanent=True
        )
        complete(late[1])
        assert all(
            service().tasks.get_status(tid) == TaskStatus.SKIPPED for _, tid in late
        )
        while (tid := service().tasks.pop_ready_task(jid)) is not None:
            _, iid = service().tasks.get_location(tid)
            if service().should_skip_task(jid, iid, tid)[0]:
                service().on_task_skipped(jid, iid, tid)
            else:
                assert (
                    service().tasks.get_definition(jid, iid, tid).question_name
                    == "observe"
                )
                service().state_for_direct_answer(jid, iid, tid)
                service().on_task_completed(jid, iid, tid, "observed", validated=True)
        assert service().jobs.get_state(jid).value == "completed"
        backend = PostgresStateBackend(state, engine, namespace=namespace)
        for group in ("a", "b"):
            writes = [
                e
                for e in backend.history()
                if e["scope"] == group and e["kind"] == "write"
            ]
            assert [e["command"] for e in writes] == ["increment", "increment"] + (
                [] if mode == "stop" else ["$close"]
            )
            assert backend.is_finalized(group, "counter") == (mode != "stop")
            assert backend.snapshot(group).state["counter"]["count"] == (
                2 if mode == "stop" else 0
            )
        before = backend.history()
        service().recover_scheduler(jid)
        for task in first + late:
            complete(task)
        assert backend.history() == before
        assert service().jobs.get_status(jid).completed_interviews == 12
    finally:
        lock_engine.dispose()


@pytest.mark.parametrize("crash_at", ["accepted", "write", "close", "decision"])
@pytest.mark.parametrize("callback", ["success", "skip", "failure", "render"])
def test_other_callback_resumes_incomplete_answer_before_termination(
    database, crash_at, callback
):
    from sqlalchemy import create_engine
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.runner.models import TaskStatus
    from edsl.runner.transition_lock import PostgresJobTransitionLock
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    lock_engine = create_engine(engine.url)
    machine = replace(
        counter().definition.machines["counter"],
        complete_when=field("count") >= 1,
        close_effects=(set_("count", 0),),
    )
    state = SharedStateMap(
        SharedState(counter=machine), state_id="interrupted-concurrent"
    )
    target = state.by("room").counter
    storage = InMemoryStorage()
    fired = False

    def interrupt(point):
        nonlocal fired
        if point == crash_at and not fired:
            fired = True
            raise RuntimeError("interrupted completion")

    class Storage:
        def __getattr__(self, name):
            return getattr(storage, name)

        def get_or_set_volatile(self, key, value):
            result = storage.get_or_set_volatile(key, value)
            if key.endswith(":accepted_answer"):
                interrupt("accepted")
            if key.endswith(":terminal"):
                interrupt("decision")
            return result

    class Backend(PostgresStateBackend):
        def apply(self, operation):
            result = super().apply(operation)
            interrupt("write")
            return result

        def finalize(self, *args, **kwargs):
            result = super().finalize(*args, **kwargs)
            interrupt("close")
            return result

    def service():
        return JobService(
            Storage(),
            distributed=True,
            transition_lock=PostgresJobTransitionLock(lock_engine),
            state_backend_factory=lambda _, state_map: Backend(
                state_map, engine, namespace=namespace
            ),
        )

    job = (
        Survey(
            [
                QuestionFreeText(question_name="write", question_text="Write"),
                target.increment(),
                target.increment(),
            ]
        )
        .by(Agent(name="first"), Agent(name="second"))
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=1, stop_when=target.is_complete(), finalize_when=target.is_complete()
    )
    try:
        jid, _, _ = service().submit_job(job)
        iids = service().jobs.get_definition(jid).interview_ids
        first, second = [
            (iid, service().interviews.get_definition(jid, iid).task_ids[0])
            for iid in iids
        ]
        with pytest.raises(RuntimeError, match="interrupted completion"):
            service().on_task_completed(jid, *first, "first answer", validated=True)
        assert fired
        # The original worker never comes back. A different callback must finish
        # all of its accepted answer's writes before closing or skipping anything.
        if callback == "success":
            service().on_task_completed(jid, *second, "late answer", validated=True)
        elif callback == "skip":
            service().on_task_skipped(jid, *second)
        elif callback == "render":
            # A query of the same task does not complete its bookkeeping, even
            # when a terminal decision exists. It must retain the journal.
            assert service().should_skip_task(jid, *first) == (False, None)
            assert storage.read_volatile(f"job:{jid}:pending_completion") is not None
            assert service().should_skip_task(jid, *second)[0]
            service().on_task_skipped(jid, *second)
        else:
            service().on_task_failed(
                jid, *second, "timeout", "late failure", force_permanent=True
            )
        assert service().tasks.get_status(first[1]) == TaskStatus.COMPLETED
        assert service().tasks.get_status(second[1]) == TaskStatus.SKIPPED
        assert service().answers.get(jid, first[0], "write").answer == "first answer"
        assert service().answers.get(jid, second[0], "write") is None
        history = Backend(state, engine, namespace=namespace).history()
        assert [e["command"] for e in history] == ["increment", "increment", "$close"]
        assert {e["execution_id"] for e in history} == {first[0]}
        assert service().jobs.get_status(jid).completed_interviews == 2
        assert storage.read_volatile(f"job:{jid}:pending_completion") is None
    finally:
        lock_engine.dispose()


def test_finalization_checks_answer_selected_scope_at_commit(database):
    from sqlalchemy import create_engine
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.runner.models import TaskStatus
    from edsl.runner.transition_lock import PostgresJobTransitionLock
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    lock_engine = create_engine(engine.url)
    state = counter()
    condition = state.by("closed").counter.is_complete()
    backend = PostgresStateBackend(state, engine, namespace=namespace)
    for i in range(2):
        backend.apply(
            resolve_write(
                state.by("closed").counter.increment(), StepContext({}, f"setup-{i}")
            )
        )
    backend.finalize(condition, "closed", execution_id="setup-close")
    question = QuestionFreeText(question_name="scope", question_text="Choose a scope")
    job = (
        Survey([question, state.by(question.answer).counter.increment()])
        .by(Agent(name="a"), Agent(name="b"))
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=1, finalize_when=condition
    )
    service = JobService(
        InMemoryStorage(),
        distributed=True,
        transition_lock=PostgresJobTransitionLock(lock_engine),
        state_backend_factory=lambda _, state_map: PostgresStateBackend(
            state_map, engine, namespace=namespace
        ),
    )
    try:
        jid, _, _ = service.submit_job(job)
        for iid, scope in zip(
            service.jobs.get_definition(jid).interview_ids, ("closed", "open")
        ):
            tid = service.interviews.get_definition(jid, iid).task_ids[0]
            assert not service.should_skip_task(jid, iid, tid)[
                0
            ]  # scope is not known yet
            service.on_task_completed(jid, iid, tid, scope, validated=True)
            assert service.tasks.get_status(tid) == (
                TaskStatus.SKIPPED if scope == "closed" else TaskStatus.COMPLETED
            )
        assert backend.snapshot("closed").state["counter"]["count"] == 2
        assert backend.snapshot("open").state["counter"]["count"] == 1
        assert len(backend.history()) == 4
    finally:
        lock_engine.dispose()


def test_render_stop_check_cannot_observe_partial_answer_effects(database):
    from threading import Event
    from sqlalchemy import create_engine
    from edsl import Agent, InterviewSchedule, Model, QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage
    from edsl.runner.transition_lock import PostgresJobTransitionLock
    from edsl.sharedstate.postgres import PostgresStateBackend

    engine, namespace = database
    lock_engine = create_engine(engine.url)
    original = counter().definition.machines["counter"]
    machine = replace(
        original,
        commands={
            **original.commands,
            "reset": Command(inputs={}, effects=(set_("count", 0),)),
        },
        complete_when=field("count") == 1,
    )
    state = SharedStateMap(SharedState(counter=machine), state_id="partial-effects")
    target = state.by("room").counter
    paused, release, checking = Event(), Event(), Event()
    storage = InMemoryStorage()

    class Backend(PostgresStateBackend):
        def apply(self, operation):
            result = super().apply(operation)
            if operation.command == "increment" and not paused.is_set():
                paused.set()
                assert release.wait(10)
            return result

    def service():
        return JobService(
            storage,
            distributed=True,
            transition_lock=PostgresJobTransitionLock(lock_engine),
            state_backend_factory=lambda _, state_map: Backend(
                state_map, engine, namespace=namespace
            ),
        )

    job = (
        Survey(
            [
                QuestionFreeText(question_name="q", question_text="Write"),
                target.increment(),
                target.reset(),
            ]
        )
        .by(Agent(name="a"), Agent(name="b"))
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=1, stop_when=target.is_complete(), finalize_when=target.is_complete()
    )
    try:
        jid, _, _ = service().submit_job(job)
        tasks = [
            (iid, service().interviews.get_definition(jid, iid).task_ids[0])
            for iid in service().jobs.get_definition(jid).interview_ids
        ]

        def check():
            checking.set()
            return service().should_skip_task(jid, *tasks[1])

        with ThreadPoolExecutor(max_workers=2) as pool:
            completion = pool.submit(
                service().on_task_completed, jid, *tasks[0], "first", validated=True
            )
            try:
                assert paused.wait(5)
                check_future = pool.submit(check)
                assert checking.wait(5)
                # The intermediate count=1 is complete, but this accepted answer
                # still has a reset to apply. Render must wait for that reset.
                with pytest.raises(TimeoutError):
                    check_future.result(timeout=0.1)
            finally:
                release.set()
            completion.result(timeout=5)
            assert check_future.result(timeout=5) == (False, None)
        service().on_task_completed(jid, *tasks[1], "second", validated=True)
        backend = Backend(state, engine, namespace=namespace)
        assert [e["command"] for e in backend.history()] == ["increment", "reset"] * 2
        assert not backend.is_finalized("room", "counter")
        assert not storage.scan_keys_volatile(f"job:{jid}:shared_state_stop:*")
        assert service().jobs.get_state(jid).value == "completed"
    finally:
        release.set()
        lock_engine.dispose()
