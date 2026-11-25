"""Threaded orchestration for independent remote EDSL jobs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait as wait_futures
import math
from queue import Empty, Queue
from threading import Lock
import time
from typing import Iterator, NamedTuple, Optional
from uuid import uuid4


class RemoteJobCompletion(NamedTuple):
    """One finished queue job; ``error`` is set when execution or fetch failed."""

    job_id: str
    results: object = None
    error: Optional[BaseException] = None


class RemoteJobError(RuntimeError):
    """A remote job reached a terminal status other than ``completed``."""


class RemoteJobQueue:
    """Submit remote jobs with bounded concurrency and consume finished results.

    Each worker submits one job with ``background=True`` and then blocks while
    polling its remote status. Queue submissions explicitly request remote
    execution, so they never fall back to running provider calls locally.
    Thus ``max_workers`` bounds the number of remote jobs in flight. Jobs are
    yielded in the order their worker tasks finish, and one job's exception
    does not stop other jobs. Failed, partially failed, and cancelled remote
    jobs produce an error completion; partial Results are included when the
    service has saved a Results object for that job.

    ``shutdown(wait=True)`` waits for already submitted remote jobs to finish;
    it does not cancel work running on the remote service.
    """

    def __init__(self, max_workers: int = 4, polling_interval: float = 5.0):
        if (
            isinstance(max_workers, bool)
            or not isinstance(max_workers, int)
            or max_workers < 1
        ):
            raise ValueError("max_workers must be a positive integer.")
        if isinstance(polling_interval, bool) or not isinstance(
            polling_interval, (int, float)
        ):
            raise ValueError(
                "polling_interval must be a positive finite number of seconds."
            )
        if polling_interval <= 0 or not math.isfinite(polling_interval):
            raise ValueError(
                "polling_interval must be a positive finite number of seconds."
            )

        self.max_workers = max_workers
        self.polling_interval = float(polling_interval)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="edsl-remote-job"
        )
        self._completion_queue: Queue[RemoteJobCompletion] = Queue()
        self._lock = Lock()
        self._futures: dict[str, Future] = {}
        self._submitted_ids: set[str] = set()
        self._completed_count = 0
        self._shutdown = False

    def submit(self, job, job_id: Optional[str] = None) -> str:
        """Submit a Jobs-like object and return its queue identifier.

        ``job`` must implement ``run(background=True, offload_execution=True)``
        and return a Results object created from a remote job.
        """
        resolved_id = str(job_id) if job_id is not None else str(uuid4())
        if not resolved_id:
            raise ValueError("job_id must be a non-empty string when supplied.")
        with self._lock:
            if self._shutdown:
                raise RuntimeError("Cannot submit jobs after the queue is shut down.")
            if resolved_id in self._submitted_ids:
                raise ValueError(f"job_id has already been used: {resolved_id}")
            future = self._executor.submit(self._run_job, job, resolved_id)
            self._submitted_ids.add(resolved_id)
            self._futures[resolved_id] = future
        future.add_done_callback(
            lambda completed_future, identifier=resolved_id: self._on_done(
                identifier, completed_future
            )
        )
        return resolved_id

    def _run_job(self, job, job_id: str) -> RemoteJobCompletion:
        try:
            results = job.run(background=True, offload_execution=True)
            return self._wait_for_remote_job(job_id, results)
        except Exception as exc:
            return RemoteJobCompletion(job_id=job_id, error=exc)

    def _wait_for_remote_job(self, job_id: str, results) -> RemoteJobCompletion:
        """Poll remote status directly so every terminal state releases a worker."""
        from ..coop import Coop
        from .remote_inference import JobsRemoteInferenceHandler

        job_uuid = results.job_info.job_uuid
        terminal_statuses = {
            "completed",
            "failed",
            "partial_failed",
            "partially_failed",
            "cancelled",
        }
        while True:
            remote_job = JobsRemoteInferenceHandler.check_status(job_uuid)
            status = remote_job.get("status")
            if not status:
                raise RemoteJobError(
                    f"Remote job {job_uuid} status response did not include a status."
                )
            if status in terminal_statuses:
                break
            time.sleep(self.polling_interval)

        error = None
        if status != "completed":
            details = remote_job.get("error") or remote_job.get("message")
            message = f"Remote job {job_uuid} ended with status {status!r}."
            if details:
                message += f" {details}"
            error = RemoteJobError(message)

        results_uuid = remote_job.get("results_uuid")
        if not results_uuid:
            if error is None:
                error = RemoteJobError(
                    f"Remote job {job_uuid} completed without a results UUID."
                )
            return RemoteJobCompletion(job_id=job_id, error=error)

        remote_results = Coop().pull(
            results_uuid, expected_object_type="results"
        )
        results.data = remote_results.data
        results.survey = remote_results.survey
        results.created_columns = remote_results.created_columns
        results.cache = remote_results.cache
        results.task_history = remote_results.task_history
        results.completed = True
        results.job_uuid = job_uuid
        if hasattr(remote_results, "results_uuid"):
            results.results_uuid = remote_results.results_uuid

        return RemoteJobCompletion(job_id=job_id, results=results, error=error)

    def _on_done(self, job_id: str, future: Future) -> None:
        try:
            completion = future.result()
        except BaseException as exc:
            # Ensure every submitted item produces one completion, even if the
            # worker exits with a BaseException outside the ordinary error path.
            completion = RemoteJobCompletion(job_id=job_id, error=exc)
        with self._lock:
            self._completed_count += 1
        self._completion_queue.put(completion)

    def get_completed(
        self, block: bool = True, timeout: Optional[float] = None
    ) -> Optional[RemoteJobCompletion]:
        """Return the next completed job, or ``None`` if a nonblocking read is empty."""
        try:
            completion = self._completion_queue.get(block=block, timeout=timeout)
        except Empty:
            return None
        with self._lock:
            self._futures.pop(completion.job_id, None)
        return completion

    def results(self) -> Iterator[RemoteJobCompletion]:
        """Yield each submitted job's completion in finish order."""
        while self.has_pending():
            completion = self.get_completed()
            if completion is not None:
                yield completion

    def join(self) -> None:
        """Block until all currently submitted worker tasks have finished."""
        with self._lock:
            futures = list(self._futures.values())
        wait_futures(futures)

    def shutdown(self, wait: bool = True) -> None:
        """Stop accepting work and shut down worker threads.

        By default, waits for submitted remote jobs to finish. Set
        ``wait=False`` to stop waiting locally; already-submitted remote
        jobs continue running on the service.
        """
        with self._lock:
            self._shutdown = True
        self._executor.shutdown(wait=wait)

    @property
    def pending_count(self) -> int:
        """Number of submitted jobs waiting for a worker to start."""
        with self._lock:
            return sum(
                not future.done() and not future.running()
                for future in self._futures.values()
            )

    @property
    def running_count(self) -> int:
        """Number of jobs currently being submitted or polled by worker threads."""
        with self._lock:
            return sum(future.running() for future in self._futures.values())

    @property
    def completed_count(self) -> int:
        """Total number of submitted jobs that have finished, including failures."""
        with self._lock:
            return self._completed_count

    def has_pending(self) -> bool:
        """Whether submitted completions remain to be collected."""
        with self._lock:
            return bool(self._futures)

    def __enter__(self) -> "RemoteJobQueue":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.shutdown()
