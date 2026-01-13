"""
InMemoryTaskQueue - Simple in-process task queue for local execution.

This provides the core task queue functionality used by both the local
server and can be used directly for testing.

Task lifecycle:
    pending -> claimed -> running -> completed/failed
"""

from __future__ import annotations

import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum


class TaskStatus(str, Enum):
    """Task status values."""

    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A task in the queue."""

    task_id: str
    task_type: str
    params: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING

    # Optional grouping
    job_id: Optional[str] = None
    group_id: Optional[str] = None

    # Dependencies (task_ids that must complete first)
    dependencies: List[str] = field(default_factory=list)

    # Rate limiting bucket
    bucket_id: Optional[str] = None

    # Priority (higher = more urgent)
    priority: int = 0

    # Metadata
    meta: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Worker info
    worker_id: Optional[str] = None

    # Result/error
    result: Optional[Dict[str, Any]] = None
    result_ref: Optional[str] = None  # For large results stored separately
    error: Optional[str] = None

    # Progress tracking
    progress_events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "params": self.params,
            "status": self.status.value,
            "job_id": self.job_id,
            "group_id": self.group_id,
            "dependencies": self.dependencies,
            "bucket_id": self.bucket_id,
            "priority": self.priority,
            "meta": self.meta,
            "created_at": self.created_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "worker_id": self.worker_id,
            "result": self.result,
            "result_ref": self.result_ref,
            "error": self.error,
        }


class InMemoryTaskQueue:
    """
    Simple in-memory task queue.

    Thread-safe implementation suitable for local development.
    For production, this would be replaced with a persistent queue
    (Redis, PostgreSQL, etc.).

    Example:
        >>> queue = InMemoryTaskQueue()
        >>> task_id = queue.create_task("wikipedia", {"url": "..."})
        >>> task = queue.claim_task(["wikipedia"], "worker-1")
        >>> queue.complete_task(task_id, {"rows": [...]})
    """

    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.RLock()
        self._groups: Dict[str, List[str]] = {}  # group_id -> [task_ids]

    def create_unified_task(
        self,
        task_type: str,
        params: Dict[str, Any],
        *,
        job_id: Optional[str] = None,
        group_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        bucket_id: Optional[str] = None,
        priority: int = 0,
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new task in the queue.

        Args:
            task_type: Service/task type (e.g., "wikipedia", "firecrawl")
            params: Task parameters
            job_id: Optional parent job ID
            group_id: Optional group ID for batching
            dependencies: List of task_ids that must complete first
            bucket_id: Optional bucket for rate limiting
            priority: Higher = more urgent
            meta: Additional metadata

        Returns:
            task_id: Unique identifier for the task
        """
        task_id = str(uuid.uuid4())

        task = Task(
            task_id=task_id,
            task_type=task_type,
            params=params,
            job_id=job_id,
            group_id=group_id,
            dependencies=dependencies or [],
            bucket_id=bucket_id,
            priority=priority,
            meta=meta or {},
        )

        with self._lock:
            self._tasks[task_id] = task

            # Track group membership
            if group_id:
                if group_id not in self._groups:
                    self._groups[group_id] = []
                self._groups[group_id].append(task_id)

        return task_id

    def claim_unified_task(
        self,
        task_types: List[str],
        worker_id: str,
        bucket_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Claim the next available task for processing.

        Args:
            task_types: List of task types this worker handles
            worker_id: Unique worker identifier
            bucket_id: If set, only claim tasks with matching bucket

        Returns:
            Task dict if one was claimed, None otherwise
        """
        with self._lock:
            # Find eligible tasks
            candidates = []
            for task in self._tasks.values():
                if task.status != TaskStatus.PENDING:
                    continue
                if task.task_type not in task_types:
                    continue
                if bucket_id and task.bucket_id != bucket_id:
                    continue

                # Check dependencies are satisfied
                deps_satisfied = all(
                    self._tasks.get(
                        dep_id, Task(task_id="", task_type="", params={})
                    ).status
                    == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                )
                if not deps_satisfied:
                    continue

                candidates.append(task)

            if not candidates:
                return None

            # Sort by priority (descending), then by created_at (ascending)
            candidates.sort(key=lambda t: (-t.priority, t.created_at))

            # Claim the first one
            task = candidates[0]
            task.status = TaskStatus.CLAIMED
            task.claimed_at = datetime.now(timezone.utc)
            task.worker_id = worker_id

            return task.to_dict()

    def complete_unified_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        result_ref: Optional[str] = None,
    ) -> bool:
        """
        Mark a task as completed.

        Args:
            task_id: Task to complete
            result: Task result (for small results)
            result_ref: Reference to stored result (for large results)

        Returns:
            True if task was completed, False if not found
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            task.result = result
            task.result_ref = result_ref

            return True

    def fail_unified_task(
        self,
        task_id: str,
        error: str,
    ) -> bool:
        """
        Mark a task as failed.

        Args:
            task_id: Task that failed
            error: Error message/description

        Returns:
            True if task was marked failed, False if not found
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False

            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            task.error = error

            return True

    def get_unified_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get task status and result.

        Args:
            task_id: Task to retrieve

        Returns:
            Task dict if found, None otherwise
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.to_dict()

    def update_unified_task_progress(
        self,
        task_id: str,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update task progress for streaming.

        Args:
            task_id: Task to update
            message: Progress message
            progress: Progress value (0.0 - 1.0)
            data: Additional progress data

        Returns:
            True if updated, False if task not found
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return False

            # Update status to running if still claimed
            if task.status == TaskStatus.CLAIMED:
                task.status = TaskStatus.RUNNING

            # Add progress event
            event = {
                "index": len(task.progress_events),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message,
                "progress": progress,
                "data": data,
            }
            task.progress_events.append(event)

            return True

    def get_unified_task_progress(
        self,
        task_id: str,
        since_index: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get progress events since a given index.

        Args:
            task_id: Task to get progress for
            since_index: Only return events with index >= this value

        Returns:
            List of progress events
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return []

            return [
                event
                for event in task.progress_events
                if event.get("index", 0) >= since_index
            ]

    def create_task_group(
        self,
        group_id: str,
        job_id: Optional[str] = None,
    ) -> None:
        """Create an empty task group."""
        with self._lock:
            if group_id not in self._groups:
                self._groups[group_id] = []

    def is_group_complete(self, group_id: str) -> bool:
        """Check if all tasks in a group are complete."""
        with self._lock:
            task_ids = self._groups.get(group_id, [])
            if not task_ids:
                return True

            return all(
                self._tasks.get(tid, Task(task_id="", task_type="", params={})).status
                in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                for tid in task_ids
            )

    def list_tasks(
        self,
        task_type: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List tasks with optional filtering.

        Args:
            task_type: Filter by task type
            status: Filter by status
            limit: Maximum number to return

        Returns:
            List of task dicts
        """
        with self._lock:
            tasks = list(self._tasks.values())

            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            if status:
                tasks = [t for t in tasks if t.status == status]

            # Sort by created_at descending
            tasks.sort(key=lambda t: t.created_at, reverse=True)

            return [t.to_dict() for t in tasks[:limit]]

    def clear(self) -> None:
        """Clear all tasks (for testing)."""
        with self._lock:
            self._tasks.clear()
            self._groups.clear()
