"""
Worker Registry - Tracks worker registration, heartbeats, and status.

Enables distributed execution by tracking:
- Which workers are active
- What each worker is currently doing
- Which workers have gone silent (dead)

Workers register on startup, send heartbeats periodically, and
unregister on shutdown. The registry tracks worker liveness and
can identify dead workers whose tasks need to be requeued.
"""

import socket
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .storage import StorageProtocol
from .models import generate_id


@dataclass
class WorkerInfo:
    """Information about a registered worker."""

    worker_id: str
    hostname: str
    started_at: datetime
    last_heartbeat: datetime
    capabilities: dict = field(default_factory=dict)  # e.g., {"models": ["gpt-4"]}
    current_task_id: str | None = None
    current_job_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "started_at": self.started_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "capabilities": self.capabilities,
            "current_task_id": self.current_task_id,
            "current_job_id": self.current_job_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkerInfo":
        return cls(
            worker_id=data["worker_id"],
            hostname=data["hostname"],
            started_at=datetime.fromisoformat(data["started_at"]),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]),
            capabilities=data.get("capabilities", {}),
            current_task_id=data.get("current_task_id"),
            current_job_id=data.get("current_job_id"),
            metadata=data.get("metadata", {}),
        )

    def is_alive(self, timeout_seconds: int = 60) -> bool:
        """Check if worker is still alive (received heartbeat recently)."""
        elapsed = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return elapsed < timeout_seconds


class WorkerRegistry:
    """
    Registry for tracking distributed workers.

    Storage Keys:
    - worker:{worker_id}:info - Worker info (persistent during worker lifetime)
    - workers:active - Set of active worker IDs

    Workers should:
    1. Call register() on startup
    2. Call heartbeat() every 10-15 seconds
    3. Call unregister() on shutdown (or let timeout handle it)
    """

    WORKERS_SET_KEY = "workers:active"
    WORKER_INFO_PREFIX = "worker:"
    WORKER_INFO_SUFFIX = ":info"

    def __init__(
        self,
        storage: StorageProtocol,
        heartbeat_timeout: int = 60,
        default_capabilities: dict | None = None,
    ):
        """
        Initialize worker registry.

        Args:
            storage: Storage backend
            heartbeat_timeout: Seconds since last heartbeat before worker is considered dead
            default_capabilities: Default capabilities for workers
        """
        self._storage = storage
        self._heartbeat_timeout = heartbeat_timeout
        self._default_capabilities = default_capabilities or {}

    def _worker_key(self, worker_id: str) -> str:
        """Get storage key for worker info."""
        return f"{self.WORKER_INFO_PREFIX}{worker_id}{self.WORKER_INFO_SUFFIX}"

    def register(
        self,
        worker_id: str | None = None,
        capabilities: dict | None = None,
        metadata: dict | None = None,
    ) -> WorkerInfo:
        """
        Register a new worker.

        Args:
            worker_id: Optional worker ID (generated if not provided)
            capabilities: Worker capabilities (e.g., supported models)
            metadata: Additional metadata

        Returns:
            WorkerInfo for the registered worker
        """
        if worker_id is None:
            worker_id = generate_id()

        now = datetime.utcnow()
        hostname = socket.gethostname()

        info = WorkerInfo(
            worker_id=worker_id,
            hostname=hostname,
            started_at=now,
            last_heartbeat=now,
            capabilities=capabilities or self._default_capabilities.copy(),
            metadata=metadata or {},
        )

        # Store worker info
        self._storage.write_persistent(self._worker_key(worker_id), info.to_dict())

        # Add to active workers set
        self._storage.add_to_set(self.WORKERS_SET_KEY, worker_id)

        return info

    def heartbeat(
        self,
        worker_id: str,
        current_task_id: str | None = None,
        current_job_id: str | None = None,
    ) -> bool:
        """
        Update worker heartbeat.

        Args:
            worker_id: Worker ID
            current_task_id: ID of task currently being executed (if any)
            current_job_id: ID of job being worked on (if any)

        Returns:
            True if heartbeat was recorded, False if worker not registered
        """
        key = self._worker_key(worker_id)
        data = self._storage.read_persistent(key)

        if data is None:
            return False

        # Update heartbeat and current task
        data["last_heartbeat"] = datetime.utcnow().isoformat()
        data["current_task_id"] = current_task_id
        data["current_job_id"] = current_job_id

        self._storage.write_persistent(key, data)
        return True

    def unregister(self, worker_id: str) -> bool:
        """
        Unregister a worker.

        Args:
            worker_id: Worker ID to unregister

        Returns:
            True if worker was unregistered, False if not found
        """
        key = self._worker_key(worker_id)
        data = self._storage.read_persistent(key)

        if data is None:
            return False

        # Remove from active set
        self._storage.remove_from_set(self.WORKERS_SET_KEY, worker_id)

        # Delete worker info
        self._storage.delete_persistent(key)

        return True

    def get_worker(self, worker_id: str) -> WorkerInfo | None:
        """Get info for a specific worker."""
        key = self._worker_key(worker_id)
        data = self._storage.read_persistent(key)

        if data is None:
            return None

        return WorkerInfo.from_dict(data)

    def get_active_workers(self) -> list[WorkerInfo]:
        """Get all active workers."""
        worker_ids = self._storage.get_set_members(self.WORKERS_SET_KEY)
        workers = []

        for worker_id in worker_ids:
            info = self.get_worker(worker_id)
            if info:
                workers.append(info)

        return workers

    def get_alive_workers(self) -> list[WorkerInfo]:
        """Get workers that have sent heartbeats recently."""
        workers = self.get_active_workers()
        return [w for w in workers if w.is_alive(self._heartbeat_timeout)]

    def get_dead_workers(self, timeout: int | None = None) -> list[WorkerInfo]:
        """
        Get workers that have missed heartbeats.

        Args:
            timeout: Optional override for heartbeat timeout

        Returns:
            List of workers considered dead
        """
        if timeout is None:
            timeout = self._heartbeat_timeout

        workers = self.get_active_workers()
        return [w for w in workers if not w.is_alive(timeout)]

    def get_workers_with_task(self, task_id: str) -> list[WorkerInfo]:
        """Find workers currently working on a specific task."""
        workers = self.get_active_workers()
        return [w for w in workers if w.current_task_id == task_id]

    def get_workers_for_job(self, job_id: str) -> list[WorkerInfo]:
        """Find workers currently working on tasks for a specific job."""
        workers = self.get_active_workers()
        return [w for w in workers if w.current_job_id == job_id]

    def cleanup_dead_workers(self) -> list[WorkerInfo]:
        """
        Remove dead workers from registry.

        Returns:
            List of workers that were cleaned up
        """
        dead = self.get_dead_workers()

        for worker in dead:
            self._storage.remove_from_set(self.WORKERS_SET_KEY, worker.worker_id)
            self._storage.delete_persistent(self._worker_key(worker.worker_id))

        return dead

    def get_in_flight_tasks(self) -> list[tuple[str, str, str]]:
        """
        Get all tasks currently being worked on.

        Returns:
            List of (worker_id, job_id, task_id) tuples
        """
        workers = self.get_active_workers()
        in_flight = []

        for worker in workers:
            if worker.current_task_id:
                in_flight.append(
                    (
                        worker.worker_id,
                        worker.current_job_id or "",
                        worker.current_task_id,
                    )
                )

        return in_flight

    def get_dead_worker_tasks(self) -> list[tuple[str, str, str]]:
        """
        Get tasks that were being worked on by dead workers.

        Returns:
            List of (worker_id, job_id, task_id) tuples for dead workers
        """
        dead = self.get_dead_workers()
        tasks = []

        for worker in dead:
            if worker.current_task_id:
                tasks.append(
                    (
                        worker.worker_id,
                        worker.current_job_id or "",
                        worker.current_task_id,
                    )
                )

        return tasks

    def stats(self) -> dict:
        """Get registry statistics."""
        workers = self.get_active_workers()
        alive = [w for w in workers if w.is_alive(self._heartbeat_timeout)]
        dead = [w for w in workers if not w.is_alive(self._heartbeat_timeout)]
        working = [w for w in alive if w.current_task_id]

        return {
            "total_registered": len(workers),
            "alive": len(alive),
            "dead": len(dead),
            "working": len(working),
            "idle": len(alive) - len(working),
        }


class HeartbeatManager:
    """
    Helper class for managing worker heartbeats in a background thread.

    Usage:
        registry = WorkerRegistry(storage)
        worker_info = registry.register()

        heartbeat = HeartbeatManager(registry, worker_info.worker_id)
        heartbeat.start()

        # ... do work ...
        heartbeat.update_task(task_id, job_id)

        # ... when done ...
        heartbeat.stop()
    """

    def __init__(
        self,
        registry: WorkerRegistry,
        worker_id: str,
        interval: float = 10.0,
    ):
        """
        Initialize heartbeat manager.

        Args:
            registry: Worker registry
            worker_id: ID of this worker
            interval: Seconds between heartbeats
        """
        self._registry = registry
        self._worker_id = worker_id
        self._interval = interval
        self._current_task_id: str | None = None
        self._current_job_id: str | None = None
        self._running = False
        self._thread: Any = None

    def update_task(self, task_id: str | None, job_id: str | None = None) -> None:
        """Update the current task being worked on."""
        self._current_task_id = task_id
        self._current_job_id = job_id

    def start(self) -> None:
        """Start sending heartbeats in background thread."""
        import threading

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop sending heartbeats."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval * 2)
            self._thread = None

    def _heartbeat_loop(self) -> None:
        """Background loop that sends heartbeats."""
        while self._running:
            try:
                self._registry.heartbeat(
                    self._worker_id,
                    self._current_task_id,
                    self._current_job_id,
                )
            except Exception:
                pass  # Heartbeat failures are non-fatal
            time.sleep(self._interval)


class AsyncHeartbeatManager:
    """
    Async version of HeartbeatManager for use with asyncio.

    Usage:
        registry = WorkerRegistry(storage)
        worker_info = registry.register()

        heartbeat = AsyncHeartbeatManager(registry, worker_info.worker_id)
        await heartbeat.start()

        # ... do async work ...
        heartbeat.update_task(task_id, job_id)

        # ... when done ...
        await heartbeat.stop()
    """

    def __init__(
        self,
        registry: WorkerRegistry,
        worker_id: str,
        interval: float = 10.0,
    ):
        self._registry = registry
        self._worker_id = worker_id
        self._interval = interval
        self._current_task_id: str | None = None
        self._current_job_id: str | None = None
        self._running = False
        self._task: Any = None

    def update_task(self, task_id: str | None, job_id: str | None = None) -> None:
        """Update the current task being worked on."""
        self._current_task_id = task_id
        self._current_job_id = job_id

    async def start(self) -> None:
        """Start sending heartbeats in background task."""
        import asyncio

        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop sending heartbeats."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    async def _heartbeat_loop(self) -> None:
        """Background loop that sends heartbeats."""
        import asyncio

        while self._running:
            try:
                self._registry.heartbeat(
                    self._worker_id,
                    self._current_task_id,
                    self._current_job_id,
                )
            except Exception:
                pass  # Heartbeat failures are non-fatal
            await asyncio.sleep(self._interval)
