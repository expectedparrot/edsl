"""
Runner and JobHandle - User-facing API for local job execution.

Usage:
    from edsl.runner import Runner

    runner = Runner()
    job_handle = runner.submit(Job.example())

    # Check status
    print(job_handle.status())
    print(job_handle.progress())

    # Wait and get results
    results = job_handle.results()
"""

from typing import Any, Optional, TYPE_CHECKING, Union
from dataclasses import dataclass, field
import time
import asyncio

from .storage import InMemoryStorage, StorageProtocol
from .service import JobService
from .models import JobState, TaskStatus, TaskExecutionError
from .queues import QueueRegistry, load_queues_from_env
from .coordinator import ExecutionCoordinator
from .render import RenderWorker
from .executor import ExecutionWorker, ExecutionWorkerPool
from .visualization import JobHandleVisualizer, JobVisualizer
from .direct_answer import DirectAnswerRegistry, DirectAnswerEntry

if TYPE_CHECKING:
    from .worker_registry import WorkerRegistry


@dataclass
class TimingStats:
    """Tracks timing for different phases of job execution."""

    job_creation: float = 0.0
    rendering: float = 0.0
    enqueueing: float = 0.0
    waiting_for_workers: float = 0.0  # Time spent in asyncio.sleep waiting for workers
    results_assembly: float = 0.0
    loop_overhead: float = 0.0
    total: float = 0.0

    # Counts
    render_calls: int = 0
    tasks_rendered: int = 0
    enqueue_calls: int = 0
    loop_iterations: int = 0

    def report(self) -> str:
        """Generate a timing report."""
        lines = [
            "=" * 50,
            "TIMING BREAKDOWN",
            "=" * 50,
            f"Job creation:        {self.job_creation*1000:8.1f} ms",
            f"Rendering:           {self.rendering*1000:8.1f} ms ({self.render_calls} calls, {self.tasks_rendered} tasks)",
            f"Enqueueing:          {self.enqueueing*1000:8.1f} ms ({self.enqueue_calls} enqueues)",
            f"Waiting for workers: {self.waiting_for_workers*1000:8.1f} ms ({self.loop_iterations} iterations)",
            f"Results assembly:    {self.results_assembly*1000:8.1f} ms",
            f"Loop overhead:       {self.loop_overhead*1000:8.1f} ms",
            "-" * 50,
            f"TOTAL:               {self.total*1000:8.1f} ms",
            "=" * 50,
        ]
        return "\n".join(lines)


class JobHandle:
    """
    Handle to a submitted job.

    Provides methods to track progress, wait for completion,
    retrieve results, and cancel execution.
    """

    def __init__(self, job_id: str, runner: "Runner"):
        self._job_id = job_id
        self._runner = runner
        self._service = runner.service
        self._storage = runner._storage
        self._registry = runner._registry
        self._coordinator = runner._coordinator
        self._viz = None  # Lazy initialization

    @property
    def job_id(self) -> str:
        """The unique identifier for this job."""
        return self._job_id

    def status(self) -> str:
        """
        Current state of the job.

        Returns one of:
        - 'pending': Job created but not started
        - 'running': Job is executing
        - 'completed': All interviews completed successfully
        - 'completed_with_failures': Some interviews failed
        - 'cancelled': Job was cancelled
        """
        state = self._service.jobs.get_state(self._job_id)
        return state.value

    def progress(self) -> dict:
        """
        Detailed progress counts.

        Returns dict with:
        - total_interviews, completed_interviews, failed_interviews, running_interviews
        - total_tasks, completed_tasks, skipped_tasks, failed_tasks, blocked_tasks
        - pending_tasks, ready_tasks, running_tasks
        """
        return self._service.get_progress(self._job_id)

    def wait(self, timeout: float | None = None, poll_interval: float = 0.5) -> bool:
        """
        Block until job completes.

        Args:
            timeout: Maximum seconds to wait. None means wait forever.
            poll_interval: Seconds between status checks.

        Returns:
            True if job completed, False if timeout.
        """
        start_time = time.time()

        while True:
            state = self._service.jobs.get_state(self._job_id)

            if state in (
                JobState.COMPLETED,
                JobState.COMPLETED_WITH_FAILURES,
                JobState.CANCELLED,
            ):
                return True

            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False

            time.sleep(poll_interval)

    def results(
        self,
        timeout: float | None = None,
        debug: bool = False,
        timing: bool = False,
        stop_on_exception: bool | None = None,
    ) -> Any:
        """
        Execute all tasks and return EDSL Results object.

        Args:
            timeout: Maximum seconds to wait.
            debug: Enable debug output for skip logic.
            timing: Print timing breakdown of execution phases.
            stop_on_exception: Override the job's stop_on_exception setting.
                              If None, uses the setting from submit().
                              If True, cancels job and raises TaskExecutionError on first failure.

        Returns:
            An edsl.results.Results object containing all completed interviews.

        Raises:
            TimeoutError: If timeout exceeded.
            RuntimeError: If job was cancelled.
            TaskExecutionError: If stop_on_exception is True and a task fails.
                               The job will be cancelled before the exception is raised.
        """
        # Execute all tasks for this job
        stats = self._runner.execute_job(
            self._job_id,
            debug=debug,
            timing=timing,
            stop_on_exception=stop_on_exception,
        )

        state = self._service.jobs.get_state(self._job_id)
        if state == JobState.CANCELLED:
            raise RuntimeError(f"Job {self._job_id} was cancelled")

        # Time results assembly
        t0 = time.time()
        results = self._service.build_edsl_results(self._job_id)
        if stats:
            stats.results_assembly = time.time() - t0
            stats.total = (
                stats.job_creation
                + stats.rendering
                + stats.enqueueing
                + stats.waiting_for_workers
                + stats.results_assembly
                + stats.loop_overhead
            )
            print(stats.report())

        return results

    def cancel(self) -> None:
        """Cancel the job. In-flight tasks will complete; pending tasks are dropped."""
        self._service.jobs.set_state(self._job_id, JobState.CANCELLED)

    def errors(self) -> list[dict]:
        """Retrieve detailed information about all failed tasks."""
        return self._service.get_error_details(self._job_id)

    def __repr__(self) -> str:
        state = self.status()
        progress = self.progress()
        completed = progress.get("completed_tasks", 0)
        total = progress.get("total_tasks", 0)
        return (
            f"Job {self._job_id[:8]}... | {state} | {completed}/{total} tasks complete"
        )

    # -------------------------------------------------------------------------
    # Visualization Methods
    # -------------------------------------------------------------------------

    @property
    def viz(self) -> JobHandleVisualizer:
        """Access to visualization methods."""
        if self._viz is None:
            self._viz = JobHandleVisualizer(
                self._job_id,
                self._storage,
                self._registry,
                self._coordinator,
            )
        return self._viz

    def show(self, details: bool = False, compact: bool = False) -> None:
        """Print visual representation of job progress."""
        self.viz.show(details=details, compact=compact)

    def show_queues(self) -> None:
        """Print visual representation of active task queues."""
        self.viz.show_queues()

    def watch(self, interval: float = 0.3) -> Any:
        """
        Execute job with live visualization updates.

        Shows progress in real-time as tasks complete.
        Returns the results when done.

        Args:
            interval: Update interval in seconds (default 0.3).
        """
        import threading
        import sys
        import shutil

        results_container = [None]
        exception_container = [None]

        def run_job():
            try:
                results_container[0] = self.results()
            except Exception as e:
                exception_container[0] = e

        thread = threading.Thread(target=run_job)
        thread.start()

        def get_max_per_line() -> int:
            try:
                term_width = shutil.get_terminal_size().columns
            except Exception:
                term_width = 80
            available = term_width - 4
            return max(4, available // 6)

        def build_display() -> str:
            max_per_line = get_max_per_line()
            job_output = self.viz._visualizer.render_job_compact(
                self._job_id, max_rows=6, max_per_line=max_per_line
            )
            progress = self._service.get_progress(self._job_id)
            total_tasks = progress.get("total_tasks", 0)
            queue_output = self.viz._visualizer.render_queues_compact(
                max_lines=10, total_tasks=total_tasks
            )
            return f"{job_output}\n\n{queue_output}"

        sys.stdout.write("\033[?25l")  # Hide cursor
        sys.stdout.write("\033[2J")  # Clear entire screen
        sys.stdout.write("\033[H")  # Move to home position
        sys.stdout.flush()

        try:
            while thread.is_alive():
                sys.stdout.write("\033[H")
                sys.stdout.write("\033[J")
                display = build_display()
                print(display)
                sys.stdout.flush()
                time.sleep(interval)
        finally:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()

        thread.join()

        if exception_container[0]:
            raise exception_container[0]

        sys.stdout.write("\033[H")
        sys.stdout.write("\033[J")
        print("Execution complete!\n")
        self.show()

        return results_container[0]


class Runner:
    """
    Local execution engine for EDSL jobs.

    Usage:
        runner = Runner()
        handle = runner.submit(Job.example())
        results = handle.results()
    """

    def __init__(
        self,
        storage: StorageProtocol | str | None = None,
        distributed: bool = False,
        heartbeat_interval: float = 10.0,
        dead_worker_timeout: int = 60,
    ):
        """
        Initialize a Runner for local execution.

        Args:
            storage: Storage implementation, URL string, or None.
                     - None: Uses in-memory storage
                     - StorageProtocol: Uses provided storage
                     - "sqlite:///...": Creates SQLAlchemyStorage
                     - "postgresql://...": Creates SQLAlchemyStorage
            distributed: If True, enable distributed execution features.
            heartbeat_interval: Seconds between worker heartbeats.
            dead_worker_timeout: Seconds after which a worker is considered dead.
        """
        self._distributed = distributed
        self._heartbeat_interval = heartbeat_interval
        self._dead_worker_timeout = dead_worker_timeout

        # Initialize storage
        self._storage = self._create_storage(storage)
        self._service = JobService(self._storage)

        # Track caches per job
        self._job_caches: dict[str, Any] = {}

        # Track stop_on_exception setting per job
        self._job_stop_on_exception: dict[str, bool] = {}

        # Worker registry for distributed execution
        self._worker_registry: "WorkerRegistry | None" = None
        if distributed:
            from .worker_registry import WorkerRegistry

            self._worker_registry = WorkerRegistry(
                self._storage,
                heartbeat_timeout=dead_worker_timeout,
            )

        # Set up execution infrastructure
        self._registry = QueueRegistry()
        load_queues_from_env(self._registry)
        self._coordinator = ExecutionCoordinator(
            self._registry,
            worker_registry=self._worker_registry,
            dead_worker_check_interval=dead_worker_timeout / 2,
        )
        self._render_worker = RenderWorker(self._storage, job_service=self._service)

        # Client-side registry for direct answer tasks
        self._direct_registry = DirectAnswerRegistry()

    def _create_storage(self, storage: StorageProtocol | str | None) -> StorageProtocol:
        """Create storage from URL string or return existing protocol."""
        if storage is None:
            return InMemoryStorage()

        if isinstance(storage, str):
            if storage.startswith("sqlite://") or storage.startswith("postgresql://"):
                from .storage_sqlalchemy import SQLAlchemyStorage

                return SQLAlchemyStorage(storage)
            else:
                raise ValueError(
                    f"Unknown storage URL format: {storage}. "
                    "Use sqlite:// or postgresql://"
                )

        # Assume it's already a StorageProtocol
        return storage

    @property
    def service(self) -> JobService:
        """Access to the underlying JobService."""
        return self._service

    def submit(
        self,
        job: Any,
        user_id: str = "anonymous",
        n: int = 1,
        cache: Any = None,
        stop_on_exception: bool = False,
    ) -> JobHandle:
        """
        Submit a job for execution.

        Args:
            job: An EDSL Job object.
            user_id: User identifier for tracking.
            n: Number of iterations to run each interview.
            cache: Optional EDSL Cache object for LLM response caching.
                   - None: a new cache is created for each execution.
                   - False: no caching.
                   - Cache: shared across all workers.
            stop_on_exception: If True, cancels the job and raises on first failure.

        Returns:
            JobHandle to track and retrieve results.
        """
        job_id, direct_task_info, _job_data = self._service.submit_job(
            job, user_id=user_id, n=n
        )

        # Register queues for models used in this job
        self._ensure_queues_for_job(job)

        # Build client-side registry for direct answer tasks
        for info in direct_task_info:
            entry = DirectAnswerEntry(
                task_id=info["task_id"],
                execution_type=info["execution_type"],
                agent=info["agent"],
                question=info["question"],
                scenario=info["scenario"],
            )
            self._direct_registry.register(info["task_id"], entry)

        # Store cache setting for this job
        if cache is not None:
            self._job_caches[job_id] = cache

        # Store stop_on_exception setting
        self._job_stop_on_exception[job_id] = stop_on_exception

        return JobHandle(job_id, self)

    def _ensure_queues_for_job(self, job: Any) -> None:
        """Register queues for all models used in this job."""
        models = job.models if hasattr(job, "models") else []
        for model in models:
            service = getattr(model, "_inference_service_", "openai")
            model_name = getattr(model, "model", "gpt-4o-mini")
            existing = self._registry.find_queues(service, model_name)
            if existing:
                continue
            api_key = getattr(model, "api_token", None) or "local"
            self._registry.register_queue(
                service=service,
                model=model_name,
                api_key=api_key,
            )

    def execute_job(
        self,
        job_id: str,
        debug: bool = False,
        timing: bool = False,
        stop_on_exception: bool | None = None,
    ) -> TimingStats | None:
        """
        Execute all tasks for a job.

        Args:
            job_id: The job to execute.
            debug: Enable debug output.
            timing: Print timing breakdown.
            stop_on_exception: Override the job's stop_on_exception setting.

        Returns:
            TimingStats if timing=True, else None.
        """
        cache = self._job_caches.get(job_id)
        stats = TimingStats() if timing else None
        effective_stop_on_exception = (
            stop_on_exception
            if stop_on_exception is not None
            else self._job_stop_on_exception.get(job_id, False)
        )
        asyncio.run(
            self._execute_job_async(
                job_id,
                debug=debug,
                cache=cache,
                stats=stats,
                stop_on_exception=effective_stop_on_exception,
            )
        )
        return stats

    async def _execute_job_async(
        self,
        job_id: str,
        debug: bool = False,
        max_workers: int = 400,
        cache: Any = None,
        stats: TimingStats | None = None,
        stop_on_exception: bool = False,
    ) -> None:
        """Async implementation of job execution with parallel workers."""
        pool = ExecutionWorkerPool(
            coordinator=self._coordinator,
            job_service=self._service,
            min_workers=max_workers,
            max_workers=max_workers,
            cache=cache,
            worker_registry=self._worker_registry,
            heartbeat_interval=self._heartbeat_interval,
        )
        await pool.start()

        if self._distributed:
            await self._coordinator.start_cleanup_loop()

        await asyncio.sleep(0.01)

        try:
            while True:
                loop_start = time.time()

                # 1. Execute any ready direct-answer tasks first (no LLM needed)
                self._execute_ready_direct_answers(
                    job_id, debug=debug, stop_on_exception=stop_on_exception
                )

                # 2. Render all ready LLM tasks
                t0 = time.time()
                rendered = self._render_worker.render_ready_tasks(
                    job_id, max_tasks=1000, debug=debug
                )
                if stats:
                    stats.rendering += time.time() - t0
                    stats.render_calls += 1
                    stats.tasks_rendered += len(rendered) if rendered else 0

                if rendered:
                    # Enqueue all rendered tasks for LLM execution
                    t0 = time.time()
                    for rp in rendered:
                        queue_id = self._coordinator.enqueue(rp)
                        if queue_id is None:
                            error_type = "no_queue"
                            error_message = f"No queue available for {rp.service_name}/{rp.model_name}"
                            self._service.on_task_failed(
                                job_id=rp.job_id,
                                interview_id=rp.interview_id,
                                task_id=rp.task_id,
                                error_type=error_type,
                                error_message=error_message,
                            )
                            if stop_on_exception:
                                self._service.jobs.set_state(
                                    rp.job_id, JobState.CANCELLED
                                )
                                raise TaskExecutionError(
                                    task_id=rp.task_id,
                                    job_id=rp.job_id,
                                    interview_id=rp.interview_id,
                                    error_type=error_type,
                                    error_message=error_message,
                                )
                    if stats:
                        stats.enqueueing += time.time() - t0
                        stats.enqueue_calls += len(rendered)

                # Check for LLM task failures from executor
                if stop_on_exception:
                    progress = self._service.get_progress(job_id)
                    if progress["failed_tasks"] > 0:
                        failed_info = self._service.get_first_failed_task(job_id)
                        if failed_info:
                            self._service.jobs.set_state(job_id, JobState.CANCELLED)
                            raise TaskExecutionError(
                                task_id=failed_info["task_id"],
                                job_id=job_id,
                                interview_id=failed_info["interview_id"],
                                error_type=failed_info["error_type"],
                                error_message=failed_info["error_message"],
                            )

                # Check if job is done
                progress = self._service.get_progress(job_id)
                if (
                    progress["ready_tasks"] == 0
                    and progress["pending_tasks"] == 0
                    and progress["running_tasks"] == 0
                ):
                    break

                # Smart wait
                t0 = time.time()
                if progress["running_tasks"] > 0 and progress["ready_tasks"] == 0:
                    await asyncio.sleep(0.05)
                else:
                    await asyncio.sleep(0.005)
                if stats:
                    stats.waiting_for_workers += time.time() - t0
                    stats.loop_overhead += time.time() - loop_start - (time.time() - t0)
                    stats.loop_iterations += 1

        finally:
            if self._distributed:
                await self._coordinator.stop_cleanup_loop()
            await pool.stop()

    def _execute_ready_direct_answers(
        self,
        job_id: str,
        debug: bool = False,
        stop_on_exception: bool = False,
    ) -> int:
        """Execute all ready direct-answer tasks for a job."""
        count = 0

        while True:
            task_id = self._service._tasks.pop_ready_task(job_id)
            if task_id is None:
                break

            if not self._direct_registry.has_entry(task_id):
                self._service._tasks.add_to_ready(job_id, task_id)
                break

            job_id_check, interview_id = self._service._tasks.get_location(task_id)

            try:
                result = self._direct_registry.execute(task_id)

                self._service.on_task_completed(
                    job_id=job_id,
                    interview_id=interview_id,
                    task_id=task_id,
                    answer_value=result["answer"],
                    comment=result.get("comment"),
                    input_tokens=result.get("input_tokens", 0),
                    output_tokens=result.get("output_tokens", 0),
                    cached=result.get("cached", False),
                )

                self._direct_registry.remove(task_id)
                count += 1

            except Exception as e:
                error_type = "direct_answer_error"
                error_message = str(e)
                self._service.on_task_failed(
                    job_id=job_id,
                    interview_id=interview_id,
                    task_id=task_id,
                    error_type=error_type,
                    error_message=error_message,
                )
                self._direct_registry.remove(task_id)

                if stop_on_exception:
                    self._service.jobs.set_state(job_id, JobState.CANCELLED)
                    raise TaskExecutionError(
                        task_id=task_id,
                        job_id=job_id,
                        interview_id=interview_id,
                        error_type=error_type,
                        error_message=error_message,
                    )

        return count

    def close(self) -> None:
        """Close the runner and release resources."""
        if self._storage and hasattr(self._storage, "close"):
            self._storage.close()

    def __repr__(self) -> str:
        storage_type = type(self._storage).__name__
        distributed = ", distributed" if self._distributed else ""
        return f"Runner(local, {storage_type}{distributed})"

    def __enter__(self) -> "Runner":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
