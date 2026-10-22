"""Request-scoped ownership checks for distributed worker transitions.

Context variables follow asyncio tasks and asyncio.to_thread calls without
mutating the JobService singleton shared by unrelated worker requests.
"""

from contextlib import contextmanager
from contextvars import ContextVar

_guard = ContextVar("runner_task_transition_guard", default=None)


@contextmanager
def task_transition_guard(guard):
    token = _guard.set(guard)
    try:
        yield
    finally:
        _guard.reset(token)


def check_task_transition(job_id, task_id):
    guard = _guard.get()
    if guard is not None:
        guard(job_id, task_id)
