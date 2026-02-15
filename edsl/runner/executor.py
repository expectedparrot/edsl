"""
ExecutionWorker - Executes LLM calls for tasks.

Uses EDSL's language model infrastructure for actual API calls.
Supports distributed execution with heartbeats and worker registration.
"""

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
import asyncio

from .coordinator import ExecutionCoordinator, WorkAssignment, WorkCompletion
from .service import JobService
from .models import TaskStatus, generate_id

# EDSL imports - relative since this module lives inside edsl package
from ..caching import Cache

if TYPE_CHECKING:
    from .worker_registry import WorkerRegistry, AsyncHeartbeatManager


@dataclass
class ExecutionResult:
    """Result of executing a task."""

    task_id: str
    job_id: str
    interview_id: str
    success: bool
    answer: Any = None
    comment: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_model_response: dict | None = None
    generated_tokens: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    cached: bool = False
    # Prompts used (for storing in Answer)
    system_prompt: str | None = None
    user_prompt: str | None = None
    # Pricing info (to match EDSL Result structure)
    input_price_per_million_tokens: float | None = None
    output_price_per_million_tokens: float | None = None
    # Cache and validation info
    cache_key: str | None = None
    validated: bool | None = None
    reasoning_summary: str | None = None


class ExecutionWorker:
    """
    Worker that executes LLM tasks.

    Lifecycle:
    1. Register with worker registry (if distributed)
    2. Start heartbeat loop (if distributed)
    3. Request work from coordinator
    4. Execute LLM call using the actual model object
    5. Report completion
    6. Update job service with result
    7. Unregister on shutdown

    For distributed execution, provide a WorkerRegistry to enable:
    - Worker registration and discovery
    - Heartbeat monitoring for failure detection
    - Task recovery when workers die
    """

    def __init__(
        self,
        coordinator: ExecutionCoordinator,
        job_service: JobService,
        idle_timeout: float = 30.0,
        cache: any = None,
        worker_registry: "WorkerRegistry | None" = None,
        worker_id: str | None = None,
        heartbeat_interval: float = 10.0,
    ):
        self._coordinator = coordinator
        self._job_service = job_service
        self._idle_timeout = idle_timeout
        self._cache = cache  # Optional EDSL Cache object
        self._running = False

        # Distributed execution support
        self._worker_registry = worker_registry
        self._worker_id = worker_id or generate_id()
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_manager: "AsyncHeartbeatManager | None" = None
        self._current_task_id: str | None = None
        self._current_job_id: str | None = None

    async def run(self) -> None:
        """Main worker loop."""
        from .models import TaskStatus

        self._running = True

        # Register with worker registry if distributed
        if self._worker_registry:
            await self._register()

        try:
            while self._running:
                # Request work
                assignment = await self._coordinator.async_request_work(
                    timeout=self._idle_timeout
                )

                if assignment is None:
                    continue

                # Track current task for heartbeat
                self._current_task_id = assignment.task.task_id
                self._current_job_id = assignment.task.job_id
                if self._heartbeat_manager:
                    self._heartbeat_manager.update_task(
                        self._current_task_id,
                        self._current_job_id,
                    )

                # Set task status to RUNNING
                self._job_service._tasks.set_status(
                    assignment.task.task_id, TaskStatus.RUNNING
                )

                # Execute
                result = await self._execute(assignment)

                # Clear current task
                self._current_task_id = None
                self._current_job_id = None
                if self._heartbeat_manager:
                    self._heartbeat_manager.update_task(None, None)

                # Report completion
                actual_tokens = (result.input_tokens or 0) + (result.output_tokens or 0)
                completion = WorkCompletion(
                    task_id=result.task_id,
                    queue_id=assignment.queue_id,
                    success=result.success,
                    answer=result.answer,
                    actual_tokens=actual_tokens,
                    error_type=result.error_type,
                    error_message=result.error_message,
                )
                self._coordinator.complete_work(completion)

                # Update job service
                if result.success:
                    self._job_service.on_task_completed(
                        job_id=result.job_id,
                        interview_id=result.interview_id,
                        task_id=result.task_id,
                        answer_value=result.answer,
                        comment=result.comment,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        raw_model_response=result.raw_model_response,
                        generated_tokens=result.generated_tokens,
                        cached=result.cached,
                        system_prompt=result.system_prompt,
                        user_prompt=result.user_prompt,
                        input_price_per_million_tokens=result.input_price_per_million_tokens,
                        output_price_per_million_tokens=result.output_price_per_million_tokens,
                        cache_key=result.cache_key,
                        validated=result.validated,
                        reasoning_summary=result.reasoning_summary,
                    )
                else:
                    self._job_service.on_task_failed(
                        job_id=result.job_id,
                        interview_id=result.interview_id,
                        task_id=result.task_id,
                        error_type=result.error_type or "unknown",
                        error_message=result.error_message or "Unknown error",
                    )
        finally:
            # Unregister on shutdown
            if self._worker_registry:
                await self._unregister()

    async def _register(self) -> None:
        """Register worker with registry and start heartbeat."""
        from .worker_registry import AsyncHeartbeatManager

        self._worker_registry.register(
            worker_id=self._worker_id,
            capabilities={},
            metadata={"type": "execution_worker"},
        )

        self._heartbeat_manager = AsyncHeartbeatManager(
            registry=self._worker_registry,
            worker_id=self._worker_id,
            interval=self._heartbeat_interval,
        )
        await self._heartbeat_manager.start()

    async def _unregister(self) -> None:
        """Stop heartbeat and unregister worker."""
        if self._heartbeat_manager:
            await self._heartbeat_manager.stop()
            self._heartbeat_manager = None

        if self._worker_registry:
            self._worker_registry.unregister(self._worker_id)

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False

    async def _execute(self, assignment: WorkAssignment) -> ExecutionResult:
        """Execute a single task using the actual model object."""
        task = assignment.task

        try:
            # Reconstruct the model object from stored data
            model = self._job_service.get_model_for_task(task.job_id, task.model_id)
            if model is None:
                raise ValueError(
                    f"Model {task.model_id} not found for job {task.job_id}"
                )

            # Disable remote proxy to make direct API calls
            model.remote_proxy = False

            # Handle cache: None or False=create new empty cache, otherwise use provided
            if self._cache is False or self._cache is None:
                cache = Cache()  # Create new cache
            else:
                cache = self._cache  # Use provided cache

            # Use model.async_get_response() like InvigilatorAI does
            # Pass iteration for cache key differentiation when n > 1
            response = await model.async_get_response(
                user_prompt=task.user_prompt,
                system_prompt=task.system_prompt,
                cache=cache,
                iteration=task.iteration,
                files_list=task.files_list,
            )

            # Extract answer and tokens from the response
            # Response is an AgentResponseDict with edsl_dict and model_outputs
            edsl_dict = response.edsl_dict
            model_outputs = response.model_outputs

            # From edsl_dict (EDSLOutput)
            answer = edsl_dict.answer if hasattr(edsl_dict, "answer") else None
            comment = edsl_dict.comment if hasattr(edsl_dict, "comment") else None
            generated_tokens = (
                edsl_dict.generated_tokens
                if hasattr(edsl_dict, "generated_tokens")
                else None
            )
            reasoning_summary = (
                edsl_dict.reasoning_summary
                if hasattr(edsl_dict, "reasoning_summary")
                else None
            )

            # From model_outputs (ModelResponse)
            input_tokens = (
                model_outputs.input_tokens
                if hasattr(model_outputs, "input_tokens")
                else None
            )
            output_tokens = (
                model_outputs.output_tokens
                if hasattr(model_outputs, "output_tokens")
                else None
            )
            raw_response = (
                model_outputs.response if hasattr(model_outputs, "response") else None
            )
            cached = (
                model_outputs.cache_used
                if hasattr(model_outputs, "cache_used")
                else False
            )
            cache_key = (
                model_outputs.cache_key if hasattr(model_outputs, "cache_key") else None
            )
            input_price = (
                model_outputs.input_price_per_million_tokens
                if hasattr(model_outputs, "input_price_per_million_tokens")
                else None
            )
            output_price = (
                model_outputs.output_price_per_million_tokens
                if hasattr(model_outputs, "output_price_per_million_tokens")
                else None
            )

            return ExecutionResult(
                task_id=task.task_id,
                job_id=task.job_id,
                interview_id=task.interview_id,
                success=True,
                answer=answer,
                comment=comment,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                raw_model_response=raw_response,
                generated_tokens=generated_tokens,
                cached=cached,
                system_prompt=task.system_prompt,
                user_prompt=task.user_prompt,
                input_price_per_million_tokens=input_price,
                output_price_per_million_tokens=output_price,
                cache_key=cache_key,
                validated=True,  # If we got here without exception, it's validated
                reasoning_summary=reasoning_summary,
            )

        except Exception as e:
            # Return failure result instead of printing/raising
            return ExecutionResult(
                task_id=task.task_id,
                job_id=task.job_id,
                interview_id=task.interview_id,
                success=False,
                error_type=self._classify_error(e),
                error_message=str(e),
            )

    def _classify_error(self, error: Exception) -> str:
        """Classify an error into a type."""
        error_str = str(error).lower()

        if "timeout" in error_str:
            return "network_timeout"
        elif "rate" in error_str or "429" in error_str:
            return "rate_limit"
        elif "500" in error_str or "502" in error_str or "503" in error_str:
            return "server_error"
        elif "invalid" in error_str or "400" in error_str:
            return "invalid_request"
        elif "content" in error_str and "policy" in error_str:
            return "content_policy"
        else:
            return "unknown"


class ExecutionWorkerPool:
    """
    Pool of execution workers with autoscaling.

    Supports distributed execution via worker registry for:
    - Worker registration and discovery
    - Heartbeat monitoring
    - Dead worker detection and task recovery
    """

    def __init__(
        self,
        coordinator: ExecutionCoordinator,
        job_service: JobService,
        min_workers: int = 1,
        max_workers: int = 10,
        cache: any = None,
        worker_registry: "WorkerRegistry | None" = None,
        heartbeat_interval: float = 10.0,
    ):
        self._coordinator = coordinator
        self._job_service = job_service
        self._min_workers = min_workers
        self._max_workers = max_workers
        self._cache = cache  # Optional EDSL Cache object shared by all workers
        self._worker_registry = worker_registry
        self._heartbeat_interval = heartbeat_interval
        self._workers: list[asyncio.Task] = []
        self._worker_instances: list[ExecutionWorker] = []
        self._running = False

    async def start(self) -> None:
        """Start the worker pool."""
        self._running = True

        # Start minimum workers
        for _ in range(self._min_workers):
            self._spawn_worker()

    async def stop(self) -> None:
        """Stop all workers."""
        self._running = False

        # Cancel all worker tasks
        for task in self._workers:
            task.cancel()

        # Wait for cancellation
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()

    def _spawn_worker(self) -> None:
        """Spawn a new worker."""
        if len(self._workers) >= self._max_workers:
            return

        worker = ExecutionWorker(
            coordinator=self._coordinator,
            job_service=self._job_service,
            cache=self._cache,
            worker_registry=self._worker_registry,
            heartbeat_interval=self._heartbeat_interval,
        )

        task = asyncio.create_task(worker.run())
        self._workers.append(task)
        self._worker_instances.append(worker)

    @property
    def worker_count(self) -> int:
        return len(self._workers)

    def get_worker_ids(self) -> list[str]:
        """Get IDs of all workers in this pool."""
        return [w._worker_id for w in self._worker_instances]
