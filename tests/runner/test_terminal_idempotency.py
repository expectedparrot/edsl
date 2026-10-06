"""Regression tests for idempotent terminal accounting (TaskStore.claim_terminal).

Task delivery to the worker is at-least-once (silent dispatcher re-POST, stream
reclaim, client retry, in-flight races), so on_task_completed / on_task_failed can
fire more than once for the same task_id. Before the guard, each duplicate bumped
the interview's completed/failed counter again, so "questions answered" could
exceed the number of tasks (observed in prod: 1452 / 1000). These tests pin the
counters to exactly one terminal per task while leaving legitimate retries intact.
"""

from edsl import Agent, Model, QuestionFreeText, Survey
from edsl.inference_services.services.test_service import TestService
from edsl.runner.models import TaskStatus
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage
from edsl.runner.stores import TaskStore


def _one_task_job():
    survey = Survey([QuestionFreeText(question_name="q", question_text="Q?")])
    model = TestService.create_model("test")(skip_api_key_check=True)
    job = survey.to_jobs().by(Agent()).by(model)
    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="job")
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    interview = service.interviews.get_definition(job_id, interview_id)
    task_id = interview.task_ids[0]
    return service, job_id, interview_id, task_id


def test_claim_terminal_returns_true_only_once():
    tasks = TaskStore(InMemoryStorage())
    assert tasks.claim_terminal("t1") is True
    assert tasks.claim_terminal("t1") is False
    assert tasks.claim_terminal("t1") is False
    assert tasks.claim_terminal("t2") is True  # different task unaffected


def test_duplicate_completion_counts_once():
    service, job_id, interview_id, task_id = _one_task_job()

    for _ in range(3):  # redelivered / raced duplicates
        service.on_task_completed(job_id, interview_id, task_id, answer_value="hi")

    status = service.interviews.get_status(interview_id)
    assert status.completed == 1  # not 3
    assert status.failed == 0
    assert service.tasks.get_status(task_id) == TaskStatus.COMPLETED


def test_duplicate_permanent_failure_counts_once():
    service, job_id, interview_id, task_id = _one_task_job()

    for _ in range(3):
        service.on_task_failed(
            job_id, interview_id, task_id, "boom", "boom", force_permanent=True
        )

    status = service.interviews.get_status(interview_id)
    assert status.failed == 1  # not 3
    assert status.completed == 0
    assert service.tasks.get_status(task_id) == TaskStatus.FAILED


def test_retryable_failure_then_success_records_once():
    """A legitimate retry after a real (retryable) failure still runs and records:
    the retryable failure resets the task to READY without counting, so the later
    success is the first terminal outcome and is counted exactly once."""
    service, job_id, interview_id, task_id = _one_task_job()

    # Retryable failure (not force_permanent) -> reset to READY, nothing counted.
    service.on_task_failed(job_id, interview_id, task_id, "transient", "429")
    status = service.interviews.get_status(interview_id)
    assert status.failed == 0
    assert status.completed == 0
    assert service.tasks.get_status(task_id) == TaskStatus.READY

    # The retry succeeds -> counted once as completed.
    service.on_task_completed(job_id, interview_id, task_id, answer_value="hi")
    status = service.interviews.get_status(interview_id)
    assert status.completed == 1
    assert status.failed == 0


def test_monitor_reports_completed_equal_total_under_duplicates():
    """The runner monitor reads get_progress_lightweight; its completed_tasks must
    equal total_tasks even when each task's completion is delivered more than once.
    This is the exact number that over-counted in prod (1452 completed for a
    1000-task job); the idempotency guard keeps it correct."""
    survey = Survey(
        [QuestionFreeText(question_name=f"q{i}", question_text=f"Q{i}?") for i in range(3)]
    )
    model = TestService.create_model("test")(skip_api_key_check=True)
    job = survey.to_jobs().by(Agent()).by(model)
    service = JobService(InMemoryStorage())
    job_id, _, _ = service.submit_job(job, job_id="job")
    interview_id = service.jobs.get_definition(job_id).interview_ids[0]
    interview = service.interviews.get_definition(job_id, interview_id)

    # Deliver every task's completion TWICE (silent re-POST / reclaim / race).
    for task_id in interview.task_ids:
        for _ in range(2):
            service.on_task_completed(job_id, interview_id, task_id, answer_value="hi")

    prog = service.get_progress_lightweight(job_id)
    assert prog["total_tasks"] == 3
    assert prog["completed_tasks"] == 3   # not 6 — the monitor now reports correctly
    assert prog["running_tasks"] == 0     # fully accounted, no phantom over-count
