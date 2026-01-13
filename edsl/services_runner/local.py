"""
Local server for running services in-process.

For simplicity, the local server runs in the same process using threads.
This avoids the complexity of subprocess management while still providing
isolation via the task queue abstraction.

The TaskQueueClient wrapper provides the same interface whether talking
to a local InMemoryTaskQueue or a remote HTTP server.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Set

from .task_queue import InMemoryTaskQueue, TaskStatus


class LocalTaskRunner:
    """
    Runs tasks locally using worker threads.

    This processes tasks from an InMemoryTaskQueue using the registered
    service implementations from ServiceRegistry.
    """

    def __init__(
        self,
        queue: InMemoryTaskQueue,
        num_workers: int = 2,
    ):
        self.queue = queue
        self.num_workers = num_workers
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._active_types: Set[str] = set()

    def start(self, task_types: Optional[List[str]] = None) -> None:
        """
        Start worker threads.

        Args:
            task_types: List of task types to handle. If None, handles all.
        """
        if task_types:
            self._active_types.update(task_types)

        self._stop_event.clear()

        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"LocalTaskRunner-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop all worker threads."""
        self._stop_event.set()

        for worker in self._workers:
            worker.join(timeout=timeout)

        self._workers.clear()

    def _worker_loop(self) -> None:
        """Main worker loop - claim and process tasks."""
        from edsl.services import ServiceRegistry, KEYS

        worker_id = f"local-{threading.current_thread().name}"
        first_poll = True

        while not self._stop_event.is_set():
            # Get list of task types to handle
            if self._active_types:
                task_types = list(self._active_types)
            else:
                # Handle all registered services
                task_types = ServiceRegistry.list()

            if first_poll:
                print(f"[Worker {worker_id}] Polling for {len(task_types)} task types")
                first_poll = False

            if not task_types:
                self._stop_event.wait(timeout=0.5)
                continue

            # Try to claim a task
            task = self.queue.claim_unified_task(
                task_types=task_types,
                worker_id=worker_id,
            )

            if task is None:
                # No task available, wait before polling again
                self._stop_event.wait(timeout=0.1)
                continue

            # Process the task
            self._process_task(task)

    def _process_task(self, task: Dict[str, Any]) -> None:
        """Process a single task."""
        from edsl.services import ServiceRegistry, KEYS

        task_id = task["task_id"]
        task_type = task["task_type"]
        params = task["params"]
        short_id = task_id[:8]

        print(f"[Worker] Claimed task {short_id} type={task_type}")

        try:
            # Update progress
            self.queue.update_unified_task_progress(
                task_id,
                message=f"Starting {task_type}...",
            )

            # Get the service class
            service_class = ServiceRegistry.get(task_type)
            if service_class is None:
                raise ValueError(f"No service registered for task type: {task_type}")

            # Get API keys
            keys = KEYS.to_dict()
            print(f"[Worker] Task {short_id}: executing {task_type}...")

            # Execute the service
            self.queue.update_unified_task_progress(
                task_id,
                message="Executing...",
            )

            result = service_class.execute(params, keys)

            # Complete the task
            self.queue.complete_unified_task(task_id, result=result)

            self.queue.update_unified_task_progress(
                task_id,
                message="Completed",
                progress=1.0,
            )
            print(f"[Worker] Task {short_id}: completed successfully")

        except Exception as e:
            # Mark task as failed
            self.queue.fail_unified_task(task_id, str(e))

            self.queue.update_unified_task_progress(
                task_id,
                message=f"Failed: {str(e)}",
            )
            print(f"[Worker] Task {short_id}: FAILED - {e}")


class LocalServer:
    """
    Combined task queue and runner for local execution.

    Provides a simple interface that matches what the remote server would provide.
    """

    def __init__(self, num_workers: int = 2):
        self.queue = InMemoryTaskQueue()
        self.runner = LocalTaskRunner(self.queue, num_workers=num_workers)
        self._started = False

    def start(self) -> None:
        """Start the server and workers."""
        if not self._started:
            self.runner.start()
            self._started = True

    def stop(self) -> None:
        """Stop the server and workers."""
        if self._started:
            self.runner.stop()
            self._started = False

    # Delegate queue methods
    def create_unified_task(self, *args, **kwargs) -> str:
        return self.queue.create_unified_task(*args, **kwargs)

    def claim_unified_task(self, *args, **kwargs):
        return self.queue.claim_unified_task(*args, **kwargs)

    def complete_unified_task(self, *args, **kwargs) -> bool:
        return self.queue.complete_unified_task(*args, **kwargs)

    def fail_unified_task(self, *args, **kwargs) -> bool:
        return self.queue.fail_unified_task(*args, **kwargs)

    def get_unified_task(self, *args, **kwargs):
        return self.queue.get_unified_task(*args, **kwargs)

    def update_unified_task_progress(self, *args, **kwargs) -> bool:
        return self.queue.update_unified_task_progress(*args, **kwargs)

    def get_unified_task_progress(self, *args, **kwargs):
        return self.queue.get_unified_task_progress(*args, **kwargs)

    def create_task_group(self, *args, **kwargs) -> None:
        return self.queue.create_task_group(*args, **kwargs)

    def is_group_complete(self, *args, **kwargs) -> bool:
        return self.queue.is_group_complete(*args, **kwargs)


class LocalTaskQueueClient:
    """
    Client wrapper for LocalServer.

    Provides the same interface as TaskQueueClient (HTTP) so they're
    interchangeable.
    """

    def __init__(self, server: LocalServer):
        self._server = server

    def create_unified_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        **kwargs,
    ) -> str:
        return self._server.create_unified_task(task_type, params, **kwargs)

    def claim_unified_task(
        self,
        task_types: List[str],
        worker_id: str,
        bucket_id: Optional[str] = None,
    ):
        return self._server.claim_unified_task(task_types, worker_id, bucket_id)

    def complete_unified_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        result_ref: Optional[str] = None,
    ) -> bool:
        return self._server.complete_unified_task(task_id, result, result_ref)

    def fail_unified_task(self, task_id: str, error: str) -> bool:
        return self._server.fail_unified_task(task_id, error)

    def get_unified_task(self, task_id: str):
        return self._server.get_unified_task(task_id)

    def update_unified_task_progress(
        self,
        task_id: str,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._server.update_unified_task_progress(
            task_id, message, progress, data
        )

    def get_unified_task_progress(
        self,
        task_id: str,
        since_index: int = 0,
    ):
        return self._server.get_unified_task_progress(task_id, since_index)

    def create_task_group(
        self,
        group_id: str,
        job_id: Optional[str] = None,
    ) -> None:
        return self._server.create_task_group(group_id, job_id)

    def is_group_complete(self, group_id: str) -> bool:
        return self._server.is_group_complete(group_id)


def start_local_server(num_workers: int = 2) -> tuple:
    """
    Start a local server and return (server, client) tuple.

    Args:
        num_workers: Number of worker threads

    Returns:
        (LocalServer, LocalTaskQueueClient) tuple
    """
    server = LocalServer(num_workers=num_workers)
    server.start()
    client = LocalTaskQueueClient(server)
    return server, client
