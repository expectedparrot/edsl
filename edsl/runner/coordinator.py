"""
ExecutionCoordinator - Central controller for task execution.

Manages:
- Queue selection and fairness
- Worker assignment via long-polling
- Token acquisition and reconciliation
- Dead worker detection and task recovery (distributed mode)
"""

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
import asyncio
import time
import threading
import logging

from .queues import QueueRegistry, Queue
from .render import RenderedPrompt

if TYPE_CHECKING:
    from .worker_registry import WorkerRegistry

# Configure logging for coordinator operations
logger = logging.getLogger(__name__)


@dataclass
class WorkAssignment:
    """Task assigned to a worker."""

    task: RenderedPrompt
    queue_id: str
    api_key: str
    assigned_at: float


@dataclass
class WorkCompletion:
    """Worker reports task completion."""

    task_id: str
    queue_id: str
    success: bool
    answer: Any = None
    actual_tokens: int | None = None
    error_type: str | None = None
    error_message: str | None = None


class ExecutionCoordinator:
    """
    Central coordinator for task execution.

    Workers long-poll for work. Coordinator handles:
    - Queue selection based on availability
    - Token bucket acquisition
    - Fairness across jobs
    - Reconciliation after completion
    - Dead worker detection and task recovery (distributed mode)
    """

    def __init__(
        self,
        registry: QueueRegistry,
        worker_registry: "WorkerRegistry | None" = None,
        dead_worker_check_interval: float = 30.0,
    ):
        self._registry = registry
        self._worker_registry = worker_registry
        self._dead_worker_check_interval = dead_worker_check_interval
        self._waiting_workers: dict[str, asyncio.Event] = {}
        self._lock = threading.Lock()

        # Track in-flight tasks for recovery
        # Maps task_id -> (queue_id, task_dict, assigned_at)
        self._in_flight: dict[str, tuple[str, dict, float]] = {}
        self._in_flight_lock = threading.Lock()

        # Background task for dead worker detection
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    def enqueue(self, rendered: RenderedPrompt) -> str | None:
        """
        Add a rendered task to the appropriate queue.

        Returns queue_id on success, None if no queue available for service/model.
        """
        task_dict = {
            "task_id": rendered.task_id,
            "job_id": rendered.job_id,
            "interview_id": rendered.interview_id,
            "system_prompt": rendered.system_prompt,
            "user_prompt": rendered.user_prompt,
            "estimated_tokens": rendered.estimated_tokens,
            "cache_key": rendered.cache_key,
            "question_name": rendered.question_name,
            "files_list": rendered.files_list,
            "model_id": rendered.model_id,
            "iteration": rendered.iteration,
        }

        service = rendered.service_name or "openai"
        model = rendered.model_name or "gpt-4o-mini"

        logger.info(
            f"[COORDINATOR ENQUEUE] task={rendered.task_id[:8]}... "
            f"service={service} model={model} question={rendered.question_name} "
            f"estimated_tokens={rendered.estimated_tokens}"
        )

        try:
            queue_id = self._registry.enqueue_task(task_dict, service, model)
            logger.info(
                f"[COORDINATOR ENQUEUE SUCCESS] task={rendered.task_id[:8]}... "
                f"-> queue={queue_id[:8]}..."
            )
        except ValueError as e:
            logger.debug(
                f"[COORDINATOR ENQUEUE FAILED] task={rendered.task_id[:8]}... "
                f"service={service} model={model} error={str(e)}"
            )
            return None

        # Wake any waiting workers
        self._wake_workers()

        return queue_id

    def request_work(self, timeout: float = 30.0) -> WorkAssignment | None:
        """
        Worker requests work. Blocks until work available or timeout.

        Returns WorkAssignment or None on timeout.
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            assignment = self._try_assign()
            if assignment:
                return assignment

            # Wait for new work
            remaining = deadline - time.time()
            if remaining <= 0:
                break

            time.sleep(min(0.1, remaining))

        return None

    async def async_request_work(self, timeout: float = 30.0) -> WorkAssignment | None:
        """Async version of request_work with event-based wake."""
        deadline = time.time() + timeout

        # Create an event for this worker to wait on
        worker_id = f"worker_{id(asyncio.current_task())}"
        event = asyncio.Event()

        with self._lock:
            self._waiting_workers[worker_id] = event

        try:
            while time.time() < deadline:
                assignment = self._try_assign()
                if assignment:
                    return assignment

                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                # Wait for wake signal or timeout (max 0.5s to stay responsive)
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=min(0.5, remaining))
                except asyncio.TimeoutError:
                    pass  # Timeout - loop and check again

            return None
        finally:
            # Unregister this worker
            with self._lock:
                self._waiting_workers.pop(worker_id, None)

    def _try_assign(self) -> WorkAssignment | None:
        """
        Try to assign work to a worker.

        Tries multiple queues if the first is rate-limited, rather than
        giving up immediately. This reduces contention when many workers
        compete for work across multiple queues.
        """
        heap = self._registry.dispatch_heap
        now = time.time()

        # Track queues we tried but couldn't use (to put back later)
        tried_queues: list[tuple[str, float]] = []

        # Try up to 10 queues to find available work
        max_attempts = 10

        for attempt in range(max_attempts):
            # Pop from heap (not peek) so we can try the next one
            result = heap.pop()
            if result is None:
                break

            queue_id, avail_time = result

            # Check if available now
            if avail_time > now:
                # Not available yet - heap is sorted, so all remaining are worse
                # Put this one back and stop
                heap.push(queue_id, avail_time)
                logger.debug(
                    f"[COORDINATOR ASSIGN] queue={queue_id[:8]}... not available yet "
                    f"(wait {avail_time - now:.2f}s), stopping search"
                )
                break

            queue = self._registry.get_queue(queue_id)
            task = queue.peek()
            if task is None:
                # Queue is empty - don't put back, try next
                logger.debug(
                    f"[COORDINATOR ASSIGN] queue={queue_id[:8]}... empty, trying next"
                )
                continue

            estimated_tokens = task.get("estimated_tokens", 500)

            # Try to acquire tokens
            if queue.try_acquire(estimated_tokens):
                # Success! Put back all queues we skipped
                for skipped_id, skipped_time in tried_queues:
                    heap.push(skipped_id, skipped_time)

                # Dequeue the task
                task = queue.dequeue()

                # Track as in-flight for recovery
                self._track_in_flight(task["task_id"], queue_id, task)

                logger.info(
                    f"[COORDINATOR ASSIGN SUCCESS] task={task['task_id'][:8]}... "
                    f"from queue={queue_id[:8]}... service={queue.service} model={queue.model} "
                    f"(attempt {attempt + 1})"
                )

                # Re-add queue to heap if more tasks
                if queue.depth > 0:
                    next_task = queue.peek()
                    next_estimated = (
                        next_task.get("estimated_tokens", 500) if next_task else 500
                    )
                    next_avail = now + queue.time_until_available(next_estimated)
                    heap.push(queue_id, next_avail)

                # Build RenderedPrompt from task dict
                rendered = RenderedPrompt(
                    task_id=task["task_id"],
                    job_id=task["job_id"],
                    interview_id=task["interview_id"],
                    system_prompt=task["system_prompt"],
                    user_prompt=task["user_prompt"],
                    estimated_tokens=task["estimated_tokens"],
                    cache_key=task["cache_key"],
                    question_name=task.get("question_name"),
                    files_list=task.get("files_list"),
                    model_id=task.get("model_id"),
                    iteration=task.get("iteration", 0),
                )

                return WorkAssignment(
                    task=rendered,
                    queue_id=queue_id,
                    api_key=queue.api_key,
                    assigned_at=now,
                )
            else:
                # Rate limited - save with updated availability, try next queue
                wait_time = queue.time_until_available(estimated_tokens)
                tried_queues.append((queue_id, now + wait_time))
                logger.debug(
                    f"[COORDINATOR ASSIGN] queue={queue_id[:8]}... rate limited "
                    f"(wait {wait_time:.2f}s), trying next queue"
                )

        # Put back all queues we tried but couldn't use
        for queue_id, avail_time in tried_queues:
            heap.push(queue_id, avail_time)

        return None

    def complete_work(self, completion: WorkCompletion) -> None:
        """Worker reports task completion."""
        # Untrack from in-flight
        self._untrack_in_flight(completion.task_id)

        queue = self._registry.get_queue(completion.queue_id)

        # Reconcile tokens
        if completion.actual_tokens is not None:
            # We don't have estimated_tokens here, so we skip reconciliation
            # In production, we'd track this
            pass

    def _wake_workers(self) -> None:
        """Signal waiting workers that work is available."""
        with self._lock:
            for event in self._waiting_workers.values():
                event.set()

    def get_stats(self) -> dict:
        """Return coordinator statistics."""
        queues = self._registry.list_queues()
        total_depth = sum(self._registry.get_queue(q.queue_id).depth for q in queues)

        with self._in_flight_lock:
            in_flight_count = len(self._in_flight)

        return {
            "num_queues": len(queues),
            "total_depth": total_depth,
            "heap_size": len(self._registry.dispatch_heap),
            "in_flight_tasks": in_flight_count,
        }

    # -------------------------------------------------------------------------
    # In-flight task tracking
    # -------------------------------------------------------------------------

    def _track_in_flight(self, task_id: str, queue_id: str, task_dict: dict) -> None:
        """Track a task as in-flight for recovery purposes."""
        with self._in_flight_lock:
            self._in_flight[task_id] = (queue_id, task_dict, time.time())

    def _untrack_in_flight(self, task_id: str) -> None:
        """Remove task from in-flight tracking."""
        with self._in_flight_lock:
            self._in_flight.pop(task_id, None)

    def get_in_flight_tasks(self) -> list[str]:
        """Get list of in-flight task IDs."""
        with self._in_flight_lock:
            return list(self._in_flight.keys())

    def get_in_flight_by_queue(self) -> dict[str, int]:
        """Get count of in-flight tasks per queue_id."""
        with self._in_flight_lock:
            counts: dict[str, int] = {}
            for task_id, (queue_id, task_dict, assigned_at) in self._in_flight.items():
                counts[queue_id] = counts.get(queue_id, 0) + 1
            return counts

    # -------------------------------------------------------------------------
    # Dead worker detection and task recovery
    # -------------------------------------------------------------------------

    async def start_cleanup_loop(self) -> None:
        """Start background loop for dead worker cleanup."""
        if self._worker_registry is None:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_loop(self) -> None:
        """Stop the background cleanup loop."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        """Background loop that checks for dead workers and requeues their tasks."""
        while self._running:
            try:
                await self._check_dead_workers()
            except Exception as e:
                logger.error(f"Error in dead worker cleanup: {e}")

            await asyncio.sleep(self._dead_worker_check_interval)

    async def _check_dead_workers(self) -> None:
        """Check for dead workers and requeue their in-flight tasks."""
        if self._worker_registry is None:
            return

        # Get tasks from dead workers
        dead_tasks = self._worker_registry.get_dead_worker_tasks()

        for worker_id, job_id, task_id in dead_tasks:
            logger.warning(
                f"Dead worker detected: {worker_id[:8]}... "
                f"Requeuing task {task_id[:8]}..."
            )

            # Requeue the task if we have it tracked
            self._requeue_task(task_id)

        # Clean up dead workers from registry
        dead_workers = self._worker_registry.cleanup_dead_workers()
        if dead_workers:
            logger.info(f"Cleaned up {len(dead_workers)} dead workers")

    def _requeue_task(self, task_id: str) -> bool:
        """
        Requeue a task that was being processed by a dead worker.

        Returns True if task was requeued, False if not found.
        """
        with self._in_flight_lock:
            if task_id not in self._in_flight:
                return False

            queue_id, task_dict, assigned_at = self._in_flight.pop(task_id)

        # Re-add to queue
        queue = self._registry.get_queue(queue_id)
        if queue:
            queue.enqueue(task_dict)

            # Update heap
            heap = self._registry.dispatch_heap
            estimated = task_dict.get("estimated_tokens", 500)
            avail_time = time.time() + queue.time_until_available(estimated)
            heap.push(queue_id, avail_time)

            logger.info(
                f"[COORDINATOR REQUEUE] task={task_id[:8]}... "
                f"back to queue={queue_id[:8]}..."
            )
            return True

        return False

    def requeue_stale_tasks(self, stale_timeout: float = 300.0) -> int:
        """
        Requeue tasks that have been in-flight too long.

        Args:
            stale_timeout: Seconds after which a task is considered stale

        Returns:
            Number of tasks requeued
        """
        now = time.time()
        stale_tasks = []

        with self._in_flight_lock:
            for task_id, (queue_id, task_dict, assigned_at) in list(
                self._in_flight.items()
            ):
                if now - assigned_at > stale_timeout:
                    stale_tasks.append(task_id)

        count = 0
        for task_id in stale_tasks:
            if self._requeue_task(task_id):
                count += 1

        if count > 0:
            logger.info(f"Requeued {count} stale tasks")

        return count
