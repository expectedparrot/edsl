"""Ownership checks precede journal recovery and survive async thread dispatch."""

import asyncio

import pytest

from edsl.runner.task_guard import task_transition_guard
from test_completion_accounting import storage, coordinated_service, submit


@pytest.mark.parametrize("callback", ["complete", "fail", "skip", "resume"])
def test_rejected_worker_cannot_repair_journal_or_mutate(
    storage, coordinated_service, callback
):
    jid, rounds = submit(storage)
    iid, tid = rounds[0][0]
    service = coordinated_service()
    repaired = []
    service._resume_pending_completion = lambda *args: repaired.append(args)

    def reject(job_id, task_id):
        assert (job_id, task_id) == (jid, tid)
        raise RuntimeError("stale worker")

    def invoke():
        if callback == "complete":
            service.on_task_completed(jid, iid, tid, "stale")
        elif callback == "fail":
            service.on_task_failed(
                jid, iid, tid, "error", "stale", force_permanent=True
            )
        elif callback == "skip":
            service.on_task_skipped(jid, iid, tid)
        else:
            service.resume_worker_task(jid, iid, tid)

    async def run():
        with task_transition_guard(reject):
            with pytest.raises(RuntimeError, match="stale worker"):
                await asyncio.to_thread(invoke)
        # Resetting the request context restores the independent caller's access.
        await asyncio.to_thread(service.on_task_completed, jid, iid, tid, "authorized")

    asyncio.run(run())
    assert len(repaired) == 1
    assert service.answers.get(jid, iid, "answer").answer == "authorized"
    assert service.jobs.get_status(jid).completed_interviews == 1
    assert service.jobs.get_status(jid).failed_interviews == 0
