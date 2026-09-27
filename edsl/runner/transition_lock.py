"""Coordination for terminal task transitions across runner processes."""

from contextlib import contextmanager
from functools import wraps
from hashlib import sha256


def serialized_transition(method=None, *, clear_completion=True):
    if method is None:
        return lambda wrapped: serialized_transition(
            wrapped, clear_completion=clear_completion
        )

    @wraps(method)
    def wrapped(self, job_id, *args, **kwargs):
        if self._transition_lock is None:
            return method(self, job_id, *args, **kwargs)
        with self._transition_lock(job_id):
            task_id = kwargs.get("task_id", args[1] if len(args) > 1 else None)
            self._resume_pending_completion(job_id, task_id)
            result = method(self, job_id, *args, **kwargs)
            if clear_completion:
                self._clear_finished_completion(job_id)
            return result

    return wrapped


class PostgresJobTransitionLock:
    """Serialize bookkeeping for one job; model calls remain outside the lock.

    Use a separate engine/pool from the shared-state backend: waiting transition
    locks must not consume the connections a lock holder needs for state writes.
    Transaction-scoped advisory locks release on rollback or connection loss.
    Redis writes remain individually replayable; this is not a cross-store
    transaction and does not itself schedule recovery after a process dies.
    """

    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def __call__(self, job_id):
        from sqlalchemy import text

        key = int.from_bytes(
            sha256(f"edsl:job-transition:{job_id}".encode()).digest()[:8],
            byteorder="big",
            signed=True,
        )
        with self.engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            yield
