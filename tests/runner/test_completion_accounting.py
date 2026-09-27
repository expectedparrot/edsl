"""Completion accounting must survive duplicate delivery and interrupted callbacks."""

from concurrent.futures import ThreadPoolExecutor
import os
from uuid import uuid4

import pytest

from edsl import Agent, InterviewSchedule, Model, QuestionFreeText
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage


@pytest.fixture(params=["memory", "redis"])
def storage(request):
    if request.param == "memory":
        yield InMemoryStorage()
        return
    url = os.environ.get("EDSL_TEST_REDIS_URL")
    if not url:
        pytest.skip("EDSL_TEST_REDIS_URL is not configured")
    from edsl.runner.storage_redis import RedisStorage
    from edsl.runner.storage_hybrid import HybridStorage

    prefix = "test-accounting-" + str(uuid4())
    redis = RedisStorage(url, prefix=prefix)
    try:
        yield HybridStorage(volatile=redis, all_redis=True)
    finally:
        keys = list(redis._client.scan_iter(match=prefix + ":*"))
        if keys:
            redis._client.delete(*keys)
        redis._client.close()
        redis._pool.disconnect()


def submit(storage):
    job = (
        QuestionFreeText(question_name="answer", question_text="Say ok")
        .to_survey()
        .by(Agent(name="a"), Agent(name="b"))
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = InterviewSchedule.rounds(count=2)
    service = JobService(storage, distributed=True)
    job_id, _, _ = service.submit_job(job)
    rounds = {0: [], 1: []}
    for iid in service.jobs.get_definition(job_id).interview_ids:
        interview = service.interviews.get_definition(job_id, iid)
        rounds[interview.iteration].append((iid, interview.task_ids[0]))
    return job_id, rounds


def complete(storage, job_id, task):
    JobService(storage, distributed=True).on_task_completed(
        job_id, *task, "ok", validated=True
    )


def assert_first_completion_only(storage, job_id, rounds):
    service = JobService(storage, distributed=True)
    iid, _ = rounds[0][0]
    assert service.interviews.get_status(iid).completed == 1
    assert service.jobs.get_status(job_id).completed_interviews == 1
    ready = storage.get_set_members(f"job:{job_id}:ready_tasks")
    for _, tid in rounds[1]:
        assert storage.read_volatile(f"task:{tid}:unmet_deps") == 1
        assert tid not in ready


def test_duplicate_callbacks_cannot_release_round_early(storage):
    job_id, rounds = submit(storage)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: complete(storage, job_id, rounds[0][0]), range(20)))
    assert_first_completion_only(storage, job_id, rounds)
    # Duplicate entries and a replayed cached batch use the same accounting.
    batch = [
        dict(interview_id=iid, task_id=tid, answer_value="ok", validated=True)
        for iid, tid in rounds[0]
    ] * 2
    for _ in range(2):
        JobService(storage, distributed=True).on_tasks_completed_batch(job_id, batch)
    ready = storage.get_set_members(f"job:{job_id}:ready_tasks")
    assert all(tid in ready for _, tid in rounds[1])
    for _, tid in rounds[1]:
        assert storage.read_volatile(f"task:{tid}:unmet_deps") == 0
        storage.remove_from_set(f"job:{job_id}:ready_tasks", tid)
    complete(storage, job_id, rounds[0][0])
    assert all(
        tid not in storage.get_set_members(f"job:{job_id}:ready_tasks")
        for _, tid in rounds[1]
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda task: complete(storage, job_id, task), rounds[1] * 10))
    service = JobService(storage, distributed=True)
    assert service.jobs.get_status(job_id).completed_interviews == 4
    assert service.jobs.get_state(job_id).value == "completed"
    for iid, _ in rounds[0] + rounds[1]:
        assert service.interviews.get_status(iid).completed == 1


@pytest.mark.parametrize("point", ["dependency", "task_counter", "job_counter"])
def test_retry_repairs_interrupted_completion_accounting(storage, point):
    job_id, rounds = submit(storage)

    class InterruptedStorage:
        fired = False

        def __getattr__(self, name):
            return getattr(storage, name)

        def interrupt(self, here):
            if here == point and not self.fired:
                self.fired = True
                raise RuntimeError("interrupted after atomic accounting")

        def satisfy_dependency_once(self, *args):
            result = storage.satisfy_dependency_once(*args)
            self.interrupt("dependency")
            return result

        def increment_volatile_once(self, key, *args):
            result = storage.increment_volatile_once(key, *args)
            self.interrupt(
                "task_counter" if key.startswith("interview:") else "job_counter"
            )
            return result

    with pytest.raises(RuntimeError, match="interrupted"):
        complete(InterruptedStorage(), job_id, rounds[0][0])
    complete(storage, job_id, rounds[0][0])
    assert_first_completion_only(storage, job_id, rounds)
    complete(storage, job_id, rounds[0][1])
    for task in rounds[1]:
        complete(storage, job_id, task)
    assert (
        JobService(storage, distributed=True).jobs.get_state(job_id).value
        == "completed"
    )


def test_duplicate_skip_cannot_release_round_early(storage):
    job_id, rounds = submit(storage)
    for _ in range(3):
        JobService(storage, distributed=True).on_task_skipped(job_id, *rounds[0][0])
    iid, _ = rounds[0][0]
    assert JobService(storage, distributed=True).interviews.get_status(iid).skipped == 1
    for _, tid in rounds[1]:
        assert storage.read_volatile(f"task:{tid}:unmet_deps") == 1


def test_scheduler_recovery_repairs_claims_without_redispatching_workers(
    storage, coordinated_service
):
    from edsl.runner.models import TaskStatus
    from edsl.runner.render import RenderWorker

    job_id, rounds = submit(storage)
    first_iid, first_tid = rounds[0][0]
    second_iid, second_tid = rounds[0][1]
    interrupted = coordinated_service()

    def crash(*args):
        raise RuntimeError("process died before recording terminal decision")

    interrupted._execute_shared_state_steps = crash
    with pytest.raises(RuntimeError, match="process died"):
        interrupted.on_task_completed(
            job_id, first_iid, first_tid, "accepted", validated=True
        )
    storage.remove_from_set(f"job:{job_id}:ready_tasks", second_tid)
    interrupted.tasks.set_status(second_tid, TaskStatus.RENDERING)
    service = coordinated_service()
    service.recover_scheduler(job_id)
    assert service.tasks.get_status(first_tid) == TaskStatus.COMPLETED
    assert service.answers.get(job_id, first_iid, "answer").answer == "accepted"
    assert storage.get_set_members(f"job:{job_id}:ready_tasks") == {second_tid}
    rendered = RenderWorker(storage, job_service=service).render_ready_tasks(
        job_id, defer_queue_status=True
    )
    assert [r.task_id for r in rendered] == [second_tid]
    assert service.tasks.get_status(second_tid) == TaskStatus.RENDERING
    service.recover_scheduler(job_id)
    assert storage.get_set_members(f"job:{job_id}:ready_tasks") == {second_tid}
    # Once queue publication has committed, recovery leaves the worker alone.
    storage.remove_from_set(f"job:{job_id}:ready_tasks", second_tid)
    for status in (TaskStatus.QUEUED, TaskStatus.RUNNING):
        service.tasks.set_status(second_tid, status)
        service.recover_scheduler(job_id)
        assert service.tasks.get_status(second_tid) == status
        assert storage.get_set_members(f"job:{job_id}:ready_tasks") == set()
    service.on_task_completed(job_id, second_iid, second_tid, "worker", validated=True)
    for iid, tid in rounds[1]:
        service.on_task_completed(job_id, iid, tid, "next round", validated=True)
    service.recover_scheduler(job_id)
    assert service.jobs.get_status(job_id).completed_interviews == 4
    assert service.jobs.get_state(job_id).value == "completed"


def test_conflicting_answers_preserve_one_complete_envelope(storage):
    job_id, rounds = submit(storage)
    iid, tid = rounds[0][0]

    def finish(value):
        JobService(storage, distributed=True).on_task_completed(
            job_id,
            iid,
            tid,
            {"value": value},
            user_prompt=f"prompt-{value}",
            input_tokens=value,
            raw_model_response={"response": value},
            question_presentation={"order": [value]},
            validated=True,
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(finish, range(20)))
    accepted = storage.read_volatile(f"job:{job_id}:task:{tid}:accepted_answer")
    stored = (
        JobService(storage, distributed=True)
        .answers.get(job_id, iid, "answer")
        .to_dict()
    )
    assert stored == accepted
    value = stored["answer"]["value"]
    assert stored["user_prompt"] == f"prompt-{value}"
    assert stored["input_tokens"] == value
    assert stored["raw_model_response"] == {"response": value}
    assert stored["question_presentation"] == {"order": [value]}
    finish(999)
    assert (
        JobService(storage, distributed=True)
        .answers.get(job_id, iid, "answer")
        .to_dict()
        == accepted
    )
    assert_first_completion_only(storage, job_id, rounds)


def test_lost_acceptance_acknowledgement_replays_first_answer(storage):
    job_id, rounds = submit(storage)
    iid, tid = rounds[0][0]

    class InterruptedStorage:
        def __getattr__(self, name):
            return getattr(storage, name)

        def get_or_set_volatile(self, *args):
            storage.get_or_set_volatile(*args)
            raise RuntimeError("lost acceptance acknowledgement")

    with pytest.raises(RuntimeError, match="lost acceptance"):
        JobService(InterruptedStorage(), distributed=True).on_task_completed(
            job_id, iid, tid, "first", user_prompt="original prompt", validated=True
        )
    assert (
        JobService(storage, distributed=True).answers.get(job_id, iid, "answer") is None
    )
    JobService(storage, distributed=True).on_task_completed(
        job_id, iid, tid, "replacement", user_prompt="changed prompt", validated=False
    )
    answer = JobService(storage, distributed=True).answers.get(job_id, iid, "answer")
    assert (answer.answer, answer.user_prompt, answer.validated) == (
        "first",
        "original prompt",
        True,
    )
    assert_first_completion_only(storage, job_id, rounds)


@pytest.fixture
def coordinated_service(storage):
    url = os.environ.get("EDSL_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("EDSL_TEST_POSTGRES_URL is required for transition coordination")
    from sqlalchemy import create_engine
    from edsl.runner.transition_lock import PostgresJobTransitionLock

    engine = create_engine(url, pool_pre_ping=True)

    def factory(actual_storage=storage):
        return JobService(
            actual_storage,
            distributed=True,
            transition_lock=PostgresJobTransitionLock(engine),
        )

    yield factory
    engine.dispose()


def test_late_failure_and_skip_preserve_success(storage, coordinated_service):
    from edsl.runner.models import TaskStatus

    job_id, rounds = submit(storage)
    iid, tid = rounds[0][0]
    coordinated_service().on_task_completed(
        job_id, iid, tid, "winner", user_prompt="original", validated=True
    )
    original = coordinated_service().answers.get(job_id, iid, "answer").to_dict()
    # Even a stale dispatcher status cannot erase the persisted decision.
    coordinated_service().tasks.set_status(tid, TaskStatus.RUNNING)
    coordinated_service().on_task_failed(
        job_id,
        iid,
        tid,
        "late",
        "obsolete response",
        force_permanent=True,
        raw_model_response={"error": "late"},
        validated=False,
    )
    coordinated_service().on_task_skipped(job_id, iid, tid)
    assert (
        coordinated_service().answers.get(job_id, iid, "answer").to_dict() == original
    )
    assert coordinated_service().tasks.get_status(tid) == TaskStatus.COMPLETED
    assert_first_completion_only(storage, job_id, rounds)


def test_success_and_failure_race_has_one_terminal_outcome(
    storage, coordinated_service
):
    from threading import Barrier
    from edsl.runner.models import TaskStatus

    job_id, rounds = submit(storage)
    iid, tid = rounds[0][0]
    gate = Barrier(2)

    def success():
        gate.wait(timeout=10)
        coordinated_service().on_task_completed(
            job_id, iid, tid, "winner", validated=True
        )

    def failure():
        gate.wait(timeout=10)
        coordinated_service().on_task_failed(
            job_id,
            iid,
            tid,
            "failure",
            "failed attempt",
            force_permanent=True,
            raw_model_response={"failed": True},
            validated=False,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(success), pool.submit(failure)]
        for future in futures:
            future.result(timeout=20)
    service = coordinated_service()
    status = service.tasks.get_status(tid)
    counts = service.interviews.get_status(iid)
    assert counts.finished_count == 1
    if status == TaskStatus.COMPLETED:
        assert counts.completed == 1 and counts.failed == 0
        assert service.answers.get(job_id, iid, "answer").answer == "winner"
        service.on_task_completed(job_id, *rounds[0][1], "ok")
        for task in rounds[1]:
            service.on_task_completed(job_id, *task, "ok")
        assert service.jobs.get_state(job_id).value == "completed"
    else:
        assert status == TaskStatus.FAILED
        assert counts.failed == 1 and counts.completed == 0
        assert service.answers.get(job_id, iid, "answer").answer is None
        for dependent_iid, dependent_tid in rounds[1]:
            assert service.tasks.get_status(dependent_tid) == TaskStatus.BLOCKED
            assert service.interviews.get_status(dependent_iid).blocked == 1
        service.on_task_completed(job_id, *rounds[0][1], "ok")
        assert service.jobs.get_state(job_id).value == "completed_with_failures"


@pytest.mark.parametrize("point", ["decision", "status", "counter"])
def test_failed_round_recovers_interrupted_cross_interview_propagation(
    storage, coordinated_service, point
):
    from edsl.runner.models import TaskStatus

    job_id, rounds = submit(storage)
    iid, tid = rounds[0][0]

    class InterruptedStorage:
        fired = False

        def __getattr__(self, name):
            return getattr(storage, name)

        def interrupt(self, here):
            if point == here and not self.fired:
                self.fired = True
                raise RuntimeError("failure propagation interrupted")

        def get_or_set_volatile(self, key, value):
            result = storage.get_or_set_volatile(key, value)
            if key.endswith(":terminal") and value == {"status": "blocked"}:
                self.interrupt("decision")
            return result

        def write_volatile(self, key, value):
            storage.write_volatile(key, value)
            if key.endswith(":status") and value == "blocked":
                self.interrupt("status")

        def increment_volatile_once(self, key, *args):
            result = storage.increment_volatile_once(key, *args)
            if key.endswith(":blocked"):
                self.interrupt("counter")
            return result

    with pytest.raises(RuntimeError, match="propagation interrupted"):
        coordinated_service(InterruptedStorage()).on_task_failed(
            job_id, iid, tid, "original", "failed", force_permanent=True
        )
    # Reconstruct everything; a late success must resume the failed decision.
    coordinated_service().on_task_completed(
        job_id, iid, tid, "too late", validated=True
    )
    service = coordinated_service()
    assert service.tasks.get_status(tid) == TaskStatus.FAILED
    assert service.interviews.get_status(iid).failed == 1
    for dependent_iid, dependent_tid in rounds[1]:
        assert service.tasks.get_status(dependent_tid) == TaskStatus.BLOCKED
        assert service.interviews.get_status(dependent_iid).blocked == 1
        assert dependent_tid not in storage.get_set_members(f"job:{job_id}:ready_tasks")
    service.on_task_completed(job_id, *rounds[0][1], "ok")
    assert service.jobs.get_state(job_id).value == "completed_with_failures"
    status = service.jobs.get_status(job_id)
    assert (status.completed_interviews, status.failed_interviews) == (1, 3)


def test_group_failure_does_not_block_independent_group(storage, coordinated_service):
    from edsl.runner.models import TaskStatus

    job = (
        QuestionFreeText(question_name="answer", question_text="Say ok")
        .to_survey()
        .by(
            [
                Agent(name=f"{group}-{seat}", traits={"group": group, "seat": seat})
                for group in ("bad", "good")
                for seat in (0, 1)
            ]
        )
        .by(Model("test"))
    )
    job.run_config.parameters.interview_schedule = (
        InterviewSchedule.grouped_round_robin("group", "seat")
    )
    service = coordinated_service()
    job_id, _, _ = service.submit_job(job)
    tasks = {}
    for iid in service.jobs.get_definition(job_id).interview_ids:
        definition = service.interviews.get_definition(job_id, iid)
        traits = service.jobs.get_agent(job_id, definition.agent_id)["traits"]
        tasks[(traits["group"], traits["seat"])] = (iid, definition.task_ids[0])
    service.on_task_failed(
        job_id, *tasks[("bad", 0)], "bad", "failed", force_permanent=True
    )
    assert service.tasks.get_status(tasks[("bad", 1)][1]) == TaskStatus.BLOCKED
    assert service.tasks.get_status(tasks[("good", 0)][1]) == TaskStatus.READY
    for seat in (0, 1):
        coordinated_service().on_task_completed(job_id, *tasks[("good", seat)], "ok")
    assert service.jobs.get_state(job_id).value == "completed_with_failures"
    status = service.jobs.get_status(job_id)
    assert (status.completed_interviews, status.failed_interviews) == (2, 2)
