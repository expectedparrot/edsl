"""
Unified Worker - A single worker that processes all task types.

This replaces the separate service worker and job worker, providing:
- Polymorphic task handling based on task_type
- Consistent progress reporting
- Rate limiting via bucket_id
- Dependency-aware execution
"""

import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Type, Callable
from datetime import datetime, timezone

from edsl.services.keys import KEYS
from edsl.services.registry import ServiceRegistry


class UnifiedWorker:
    """
    A worker that processes tasks from the unified task queue.
    
    Handles all task types:
    - External services (embeddings, firecrawl, vibes, etc.)
    - LLM inference (question answering)
    - Any registered task type
    
    Example:
        # Start a worker for service tasks
        worker = UnifiedWorker(
            server=get_remote_server(),
            task_types=["embeddings", "vibes", "firecrawl"],
        )
        worker.start(background=True)
        
        # Or process a specific bucket (for rate limiting)
        worker = UnifiedWorker(
            server=server,
            task_types=["llm_inference"],
            bucket_id="gpt-4",
        )
    """
    
    def __init__(
        self,
        server,  # RemoteServer protocol
        task_types: List[str],
        *,
        worker_id: Optional[str] = None,
        bucket_id: Optional[str] = None,
        poll_interval: float = 0.1,
        handlers: Optional[Dict[str, Callable]] = None,
    ):
        """
        Initialize a unified worker.
        
        Args:
            server: RemoteServer instance
            task_types: List of task types this worker handles
            worker_id: Unique worker ID (auto-generated if not provided)
            bucket_id: If set, only claim tasks with matching bucket_id
            poll_interval: Seconds between polling for tasks
            handlers: Optional custom handlers for task types
        """
        self.server = server
        self.task_types = task_types
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.bucket_id = bucket_id
        self.poll_interval = poll_interval
        
        # Custom handlers override default service handlers
        self._handlers = handlers or {}
        
        # Control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def register_handler(
        self,
        task_type: str,
        handler: Callable[[Dict[str, Any], Dict[str, str]], Dict[str, Any]],
    ) -> None:
        """
        Register a custom handler for a task type.
        
        Args:
            task_type: The task type to handle
            handler: Function(params, keys) -> result_dict
        """
        self._handlers[task_type] = handler
    
    def start(self, background: bool = True) -> None:
        """
        Start the worker.
        
        Args:
            background: If True, run in a daemon thread. If False, block.
        """
        self._stop_event.clear()
        self._running = True
        
        if background:
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"UnifiedWorker-{self.worker_id}",
                daemon=True,
            )
            self._thread.start()
            # Small delay to ensure thread is polling
            time.sleep(0.05)
        else:
            self._run_loop()
    
    def stop(self, timeout: float = 5.0) -> None:
        """Stop the worker."""
        self._running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
    
    def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running and not self._stop_event.is_set():
            try:
                task = self.server.claim_unified_task(
                    task_types=self.task_types,
                    worker_id=self.worker_id,
                    bucket_id=self.bucket_id,
                )
                
                if task:
                    self._process_task(task)
                else:
                    # No task available, wait before polling again
                    self._stop_event.wait(timeout=self.poll_interval)
                    
            except Exception as e:
                # Log error but keep running
                import sys
                print(f"Worker {self.worker_id} error: {e}", file=sys.stderr)
                self._stop_event.wait(timeout=1.0)  # Back off on error
    
    def _process_task(self, task: Dict[str, Any]) -> None:
        """Process a single task."""
        task_id = task["task_id"]
        task_type = task["task_type"]
        params = task["params"]
        
        try:
            # Report start
            self.server.update_unified_task_progress(
                task_id,
                message=f"Starting {task_type}...",
            )
            
            # Get handler
            handler = self._get_handler(task_type)
            if handler is None:
                raise ValueError(f"No handler for task type: {task_type}")
            
            # Get keys
            keys = KEYS.to_dict()
            
            # Execute
            self.server.update_unified_task_progress(
                task_id,
                message=f"Executing...",
            )
            
            result = handler(params, keys)
            
            # Complete
            self.server.complete_unified_task(
                task_id,
                result=result,
            )
            
            self.server.update_unified_task_progress(
                task_id,
                message="Completed",
            )
            
        except Exception as e:
            self.server.fail_unified_task(task_id, str(e))
            self.server.update_unified_task_progress(
                task_id,
                message=f"Failed: {str(e)}",
            )
    
    def _get_handler(
        self, task_type: str
    ) -> Optional[Callable[[Dict[str, Any], Dict[str, str]], Dict[str, Any]]]:
        """Get the handler for a task type."""
        # Check custom handlers first
        if task_type in self._handlers:
            return self._handlers[task_type]
        
        # Check registered services
        service_class = ServiceRegistry.get(task_type)
        if service_class:
            return service_class.execute
        
        return None


# Global registry of running workers
_workers: Dict[str, UnifiedWorker] = {}
_workers_lock = threading.Lock()


def start_unified_worker(
    server,
    task_types: List[str],
    *,
    worker_id: Optional[str] = None,
    bucket_id: Optional[str] = None,
    background: bool = True,
) -> UnifiedWorker:
    """
    Start a unified worker.
    
    Args:
        server: RemoteServer instance
        task_types: List of task types to handle
        worker_id: Optional custom worker ID
        bucket_id: Optional bucket for rate limiting
        background: Run in background thread (default True)
        
    Returns:
        The started worker
    """
    worker = UnifiedWorker(
        server=server,
        task_types=task_types,
        worker_id=worker_id,
        bucket_id=bucket_id,
    )
    worker.start(background=background)
    
    with _workers_lock:
        _workers[worker.worker_id] = worker
    
    return worker


def stop_all_workers(timeout: float = 5.0) -> None:
    """Stop all running workers."""
    with _workers_lock:
        for worker in _workers.values():
            worker.stop(timeout=timeout)
        _workers.clear()


def get_worker(worker_id: str) -> Optional[UnifiedWorker]:
    """Get a worker by ID."""
    with _workers_lock:
        return _workers.get(worker_id)


def list_workers() -> List[str]:
    """List all worker IDs."""
    with _workers_lock:
        return list(_workers.keys())


# ─────────────────────────────────────────────────────────────
# Convenience: Ensure a worker is running for given task types
# ─────────────────────────────────────────────────────────────

_ensured_types: Set[str] = set()
_ensured_lock = threading.Lock()


def ensure_worker_for_types(
    server,
    task_types: List[str],
) -> None:
    """
    Ensure a worker is running for the given task types.
    
    Idempotent - only starts a worker if needed.
    """
    with _ensured_lock:
        # Check if all types are already covered
        missing = set(task_types) - _ensured_types
        if not missing:
            return
        
        # Start worker for missing types
        start_unified_worker(
            server=server,
            task_types=list(missing),
            background=True,
        )
        
        _ensured_types.update(missing)


def reset_ensured_types() -> None:
    """Reset the ensured types tracking (for testing)."""
    with _ensured_lock:
        _ensured_types.clear()

