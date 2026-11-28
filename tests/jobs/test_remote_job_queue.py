from threading import Event
from types import SimpleNamespace

import pytest

from edsl.jobs import RemoteJobQueue
from edsl.jobs.remote_inference import JobsRemoteInferenceHandler
from edsl.jobs.remote_job_queue import RemoteJobError


class FakeResults:
    def __init__(self, value=None, job_uuid="remote-job"):
        self.value = value
        self.job_info = SimpleNamespace(job_uuid=job_uuid)
        self.data = []
        self.survey = None
        self.created_columns = []
        self.cache = None
        self.task_history = None
        self.completed = False
        self.fetch_called = False

    def fetch(self, polling_interval=1.0):
        self.fetch_called = True
        return self


class FakeRemoteResults:
    def __init__(self, value="complete"):
        self.data = [value]
        self.survey = "survey"
        self.created_columns = ["column"]
        self.cache = "cache"
        self.task_history = "history"
        self.results_uuid = "results-uuid"


class FakeCoop:
    def __init__(self, remote_results=None):
        self.remote_results = remote_results or FakeRemoteResults()

    def pull(self, results_uuid, expected_object_type):
        assert results_uuid == "results-uuid"
        assert expected_object_type == "results"
        return self.remote_results


class FakeJob:
    def __init__(self, results=None, error=None, block_run=None, started=None):
        self.results = results or FakeResults()
        self.error = error
        self.block_run = block_run
        self.started = started
        self.background = None
        self.offload_execution = None

    def run(self, background=False, offload_execution=False):
        self.background = background
        self.offload_execution = offload_execution
        if self.started is not None:
            self.started.set()
        if self.block_run is not None:
            self.block_run.wait(timeout=2)
        if self.error is not None:
            raise self.error
        return self.results


def patch_remote(monkeypatch, statuses=None, remote_results=None):
    statuses = statuses or {"remote-job": [{"status": "completed", "results_uuid": "results-uuid"}]}
    calls = {}

    def check_status(job_uuid):
        status_list = statuses[job_uuid]
        index = calls.get(job_uuid, 0)
        calls[job_uuid] = index + 1
        return status_list[min(index, len(status_list) - 1)]

    monkeypatch.setattr(JobsRemoteInferenceHandler, "check_status", staticmethod(check_status))
    monkeypatch.setattr("edsl.coop.Coop", lambda: FakeCoop(remote_results))
    return calls


def test_remote_queue_forces_offload_and_returns_fetched_results(monkeypatch):
    patch_remote(monkeypatch)
    results = FakeResults()
    job = FakeJob(results)
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    job_id = queue.submit(job, job_id="one")

    completion = queue.get_completed(timeout=2)

    assert job_id == "one"
    assert tuple(completion) == ("one", results, None)
    assert job.background is True
    assert job.offload_execution is True
    assert results.data == ["complete"]
    assert results.completed is True
    assert results.fetch_called is False
    assert queue.completed_count == 1
    assert not queue.has_pending()
    queue.shutdown()


@pytest.mark.parametrize(
    "job",
    [
        FakeJob(error=RuntimeError("submission failed")),
    ],
)
def test_remote_job_queue_reports_submission_errors(monkeypatch, job):
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(job, job_id="failed")

    completion = queue.get_completed(timeout=2)

    assert completion.job_id == "failed"
    assert completion.results is None
    assert isinstance(completion.error, RuntimeError)
    queue.shutdown()


@pytest.mark.parametrize("status", ["failed", "partial_failed", "partially_failed"])
def test_remote_terminal_failure_keeps_results_and_reports_error(monkeypatch, status):
    patch_remote(
        monkeypatch,
        statuses={
            "remote-job": [
                {"status": status, "results_uuid": "results-uuid", "message": "one interview failed"}
            ]
        },
    )
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(FakeJob(), job_id=status)

    completion = queue.get_completed(timeout=2)

    assert completion.job_id == status
    assert completion.results is not None
    assert completion.results.data == ["complete"]
    assert isinstance(completion.error, RemoteJobError)
    assert status in str(completion.error)
    queue.shutdown()


def test_cancelled_remote_job_releases_worker_without_waiting_for_results(monkeypatch):
    calls = patch_remote(
        monkeypatch,
        statuses={"remote-job": [{"status": "running"}, {"status": "cancelled"}]},
    )
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.001)
    queue.submit(FakeJob(), job_id="cancelled")

    completion = queue.get_completed(timeout=2)

    assert completion.job_id == "cancelled"
    assert completion.results is None
    assert isinstance(completion.error, RemoteJobError)
    assert "cancelled" in str(completion.error)
    assert calls["remote-job"] == 2
    queue.shutdown()


def test_remote_queue_yields_in_completion_order(monkeypatch):
    release_slow = Event()
    slow_started = Event()
    patch_remote(
        monkeypatch,
        statuses={
            "slow": [
                {"status": "running"},
                {"status": "completed", "results_uuid": "results-uuid"},
            ],
            "fast": [{"status": "completed", "results_uuid": "results-uuid"}],
        },
    )

    # Keep the slow status running until the test releases it.
    original_check_status = JobsRemoteInferenceHandler.check_status

    def controlled_status(job_uuid):
        if job_uuid == "slow":
            slow_started.set()
            if not release_slow.is_set():
                return {"status": "running"}
        return original_check_status(job_uuid)

    monkeypatch.setattr(JobsRemoteInferenceHandler, "check_status", staticmethod(controlled_status))
    queue = RemoteJobQueue(max_workers=2, polling_interval=0.005)
    queue.submit(FakeJob(FakeResults(job_uuid="slow")), job_id="slow")
    assert slow_started.wait(timeout=2)
    queue.submit(FakeJob(FakeResults(job_uuid="fast")), job_id="fast")

    first = queue.get_completed(timeout=2)
    assert first.job_id == "fast"
    release_slow.set()
    second = queue.get_completed(timeout=2)
    assert second.job_id == "slow"
    queue.shutdown()


def test_queue_bounds_running_jobs_and_join_keeps_completions(monkeypatch):
    patch_remote(
        monkeypatch,
        statuses={
            "first": [{"status": "completed", "results_uuid": "results-uuid"}],
            "second": [{"status": "completed", "results_uuid": "results-uuid"}],
        },
    )
    release_first = Event()
    first_started = Event()
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(
        FakeJob(FakeResults(job_uuid="first"), block_run=release_first, started=first_started),
        job_id="first",
    )
    assert first_started.wait(timeout=2)
    queue.submit(FakeJob(FakeResults(job_uuid="second")), job_id="second")
    assert queue.running_count == 1
    assert queue.pending_count == 1

    release_first.set()
    queue.join()
    assert queue.completed_count == 2
    assert queue.has_pending()
    assert [item.job_id for item in queue.results()] == ["first", "second"]
    assert not queue.has_pending()
    queue.shutdown()


def test_remote_job_queue_rejects_duplicate_ids_and_submissions_after_shutdown(monkeypatch):
    patch_remote(monkeypatch)
    queue = RemoteJobQueue(max_workers=1)
    queue.submit(FakeJob(), job_id="reused")
    with pytest.raises(ValueError, match="already been used"):
        queue.submit(FakeJob(), job_id="reused")
    queue.shutdown()
    with pytest.raises(RuntimeError, match="shut down"):
        queue.submit(FakeJob())


def test_remote_job_queue_can_wait_after_nonblocking_shutdown(monkeypatch):
    patch_remote(monkeypatch)
    release_job = Event()
    job_started = Event()
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(
        FakeJob(block_run=release_job, started=job_started), job_id="blocked"
    )
    assert job_started.wait(timeout=2)
    queue.shutdown(wait=False)
    release_job.set()
    queue.shutdown(wait=True)
    assert queue.completed_count == 1
