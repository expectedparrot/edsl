from threading import Event

import pytest

from edsl.jobs import RemoteJobQueue


class FakeResults:
    def __init__(self, value=None, error=None, wait_for=None):
        self.value = value
        self.error = error
        self.wait_for = wait_for
        self.fetch_interval = None

    def fetch(self, polling_interval=1.0):
        self.fetch_interval = polling_interval
        if self.wait_for is not None:
            self.wait_for.wait(timeout=2)
        if self.error is not None:
            raise self.error
        return self


class FakeJob:
    def __init__(self, results=None, error=None):
        self.results = results or FakeResults()
        self.error = error
        self.background = None

    def run(self, background=False):
        self.background = background
        if self.error is not None:
            raise self.error
        return self.results


def test_remote_job_queue_returns_fetched_results_and_counts_completion():
    results = FakeResults(value="complete")
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    job_id = queue.submit(FakeJob(results), job_id="one")

    completion = queue.get_completed(timeout=2)

    assert job_id == "one"
    assert tuple(completion) == ("one", results, None)
    assert results.fetch_interval == 0.01
    assert queue.completed_count == 1
    assert not queue.has_pending()
    queue.shutdown()


@pytest.mark.parametrize(
    "job",
    [
        FakeJob(error=RuntimeError("submission failed")),
        FakeJob(results=FakeResults(error=RuntimeError("fetch failed"))),
    ],
)
def test_remote_job_queue_reports_per_job_errors(job):
    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(job, job_id="failed")

    job_id, results, error = queue.get_completed(timeout=2)

    assert job_id == "failed"
    assert results is None
    assert isinstance(error, RuntimeError)
    queue.shutdown()


def test_remote_job_queue_yields_in_completion_order():
    release_slow = Event()
    slow_started = Event()

    class SlowResults(FakeResults):
        def fetch(self, polling_interval=1.0):
            slow_started.set()
            return super().fetch(polling_interval)

    queue = RemoteJobQueue(max_workers=2, polling_interval=0.01)
    queue.submit(FakeJob(SlowResults(wait_for=release_slow)), job_id="slow")
    assert slow_started.wait(timeout=2)
    queue.submit(FakeJob(FakeResults(value="fast")), job_id="fast")

    first = queue.get_completed(timeout=2)
    assert first.job_id == "fast"
    release_slow.set()
    second = queue.get_completed(timeout=2)
    assert second.job_id == "slow"
    queue.shutdown()


def test_remote_job_queue_bounds_running_jobs_and_join_keeps_completions():
    release_first = Event()
    first_started = Event()

    class BlockingResults(FakeResults):
        def fetch(self, polling_interval=1.0):
            first_started.set()
            return super().fetch(polling_interval)

    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(FakeJob(BlockingResults(wait_for=release_first)), job_id="first")
    assert first_started.wait(timeout=2)
    queue.submit(FakeJob(), job_id="second")
    assert queue.running_count == 1
    assert queue.pending_count == 1

    release_first.set()
    queue.join()
    assert queue.completed_count == 2
    assert queue.has_pending()  # completed values remain available until consumed
    assert [item.job_id for item in queue.results()] == ["first", "second"]
    assert not queue.has_pending()
    queue.shutdown()


def test_remote_job_queue_rejects_duplicate_ids_and_submissions_after_shutdown():
    queue = RemoteJobQueue(max_workers=1)
    queue.submit(FakeJob(), job_id="reused")
    with pytest.raises(ValueError, match="already been used"):
        queue.submit(FakeJob(), job_id="reused")
    queue.shutdown()
    with pytest.raises(RuntimeError, match="shut down"):
        queue.submit(FakeJob())


def test_remote_job_queue_can_wait_after_nonblocking_shutdown():
    release_job = Event()
    job_started = Event()

    class BlockingResults(FakeResults):
        def fetch(self, polling_interval=1.0):
            job_started.set()
            return super().fetch(polling_interval)

    queue = RemoteJobQueue(max_workers=1, polling_interval=0.01)
    queue.submit(FakeJob(BlockingResults(wait_for=release_job)))
    assert job_started.wait(timeout=2)
    queue.shutdown(wait=False)
    release_job.set()
    queue.shutdown(wait=True)
    assert queue.completed_count == 1
