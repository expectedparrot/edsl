"""Threaded orchestration for independent remote EDSL jobs."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait as wait_futures
import math
from queue import Empty, Queue
from threading import Lock
from typing import Iterator, NamedTuple, Optional
from uuid import uuid4


class RemoteJobCompletion(NamedTuple):
    """One finished queue job; ``error`` is set when execution or fetch failed."""

    job_id: str
    results: object = None
    error: Optional[BaseException] = None


class RemoteJobQueue:
    """Submit remote jobs with bounded concurrency and consume finished results.

    Each worker submits one job with ``background=True`` and then blocks while
    polling that job's ``Results``. Thus ``max_workers`` bounds the number of
    remote jobs in flight. Jobs are yielded in the order their worker tasks
    finish, and one job's exception does not stop other jobs.

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

        ``job`` must implement ``run(background=True)`` and return a Results
        object whose ``fetch(polling_interval=...)`` waits for completion.
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
            results = job.run(background=True)
            results.fetch(polling_interval=self.polling_interval)
            return RemoteJobCompletion(job_id=job_id, results=results)
        except Exception as exc:
            return RemoteJobCompletion(job_id=job_id, error=exc)

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
