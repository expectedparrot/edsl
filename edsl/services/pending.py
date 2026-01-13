"""
PendingResult: Async result wrapper for external service tasks.

Provides a user-friendly interface for waiting on and retrieving results
from tasks dispatched to external services.

Example:
    >>> from edsl.services import dispatch
    >>> 
    >>> # Dispatch returns a PendingResult
    >>> pending = dispatch("exa", {"query": "AI researchers"})
    >>> 
    >>> # Block and wait for result
    >>> result = pending.result()
    >>> 
    >>> # Or check status first
    >>> if pending.is_ready():
    ...     result = pending.result()
    >>> 
    >>> # Status property
    >>> print(pending.status)  # "pending", "running", "completed", "failed"
    >>> 
    >>> # Cancel if needed
    >>> pending.cancel()
"""

from __future__ import annotations

import sys
import time
import itertools
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
import uuid

if TYPE_CHECKING:
    from .base import ExternalService


@dataclass
class TaskStatus:
    """Status information for a pending task."""

    status: str  # "pending", "claimed", "running", "completed", "failed", "cancelled"
    task_id: str
    service: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result_ref: Optional[str] = None
    progress: Optional[float] = None  # 0.0 - 1.0
    message: Optional[str] = None


class PendingResult:
    """
    Async result wrapper for external service tasks.

    Provides methods for waiting on, checking status of, and retrieving
    results from tasks dispatched to external services. Supports both
    blocking and non-blocking patterns.

    Attributes:
        task_id: Unique identifier for the task
        service: Name of the service handling the task
        params: Parameters passed to the service
    """

    def __init__(
        self,
        task_id: str,
        service: str,
        params: Dict[str, Any],
        server: Optional[Any] = None,
        service_class: Optional[type] = None,
        result_pattern: Optional[str] = None,
        result_field: Optional[str] = None,
    ):
        """
        Initialize a PendingResult.

        Args:
            task_id: Unique task identifier
            service: Service name
            params: Task parameters
            server: RemoteServer instance for status checks
            service_class: ExternalService class for result parsing
            result_pattern: Pattern for generic parsing (when service_class is None)
            result_field: Field to extract from result (when using generic parsing)
        """
        self.task_id = task_id
        self.service = service
        self.params = params
        self._server = server
        self._service_class = service_class
        self._result_pattern = result_pattern
        self._result_field = result_field
        self._cached_result: Optional[Any] = None
        self._cached_status: Optional[TaskStatus] = None
        self._created_at = datetime.now()
        self._callbacks: list[Callable[[Any], None]] = []

    @property
    def status(self) -> str:
        """
        Get current task status.

        Returns:
            Status string: "pending", "claimed", "running",
                          "completed", "failed", "cancelled"
        """
        status = self._get_status()
        return status.status if status else "unknown"

    def _get_status(self) -> Optional[TaskStatus]:
        """
        Fetch current status from server.

        Returns:
            TaskStatus object, or None if not available
        """
        if self._server is None:
            # No server - assume local execution completed
            if self._cached_result is not None:
                return TaskStatus(
                    status="completed",
                    task_id=self.task_id,
                    service=self.service,
                    created_at=self._created_at,
                    completed_at=datetime.now(),
                )
            return TaskStatus(
                status="pending",
                task_id=self.task_id,
                service=self.service,
                created_at=self._created_at,
            )

        try:
            # Try unified task system first
            status_dict = None
            if hasattr(self._server, "get_unified_task"):
                status_dict = self._server.get_unified_task(self.task_id)

            # Fall back to legacy service task system
            if status_dict is None and hasattr(self._server, "get_task_status"):
                status_dict = self._server.get_task_status(self.task_id)

            if status_dict is None:
                return None

            self._cached_status = TaskStatus(
                status=status_dict.get("status", "unknown"),
                task_id=self.task_id,
                service=self.service,
                created_at=self._created_at,
                error=status_dict.get("error"),
                result_ref=status_dict.get("result_ref"),
                progress=status_dict.get("progress"),
                message=status_dict.get("message"),
            )
            return self._cached_status

        except Exception:
            return self._cached_status

    def is_ready(self) -> bool:
        """
        Check if the result is ready.

        Returns:
            True if task completed (successfully or with error)
        """
        status = self.status
        return status in ("completed", "failed")

    def is_complete(self) -> bool:
        """
        Check if task completed successfully.

        Returns:
            True if task completed without error
        """
        return self.status == "completed"

    def is_failed(self) -> bool:
        """
        Check if task failed.

        Returns:
            True if task failed with an error
        """
        return self.status == "failed"

    def wait(
        self,
        timeout: Optional[float] = None,
        poll_interval: float = 0.2,
        show_progress: bool = True,
        verbose: bool = True,
        raise_on_timeout: bool = True,
    ) -> bool:
        """
        Wait for task to complete.

        Args:
            timeout: Maximum seconds to wait (None = no timeout)
            poll_interval: Seconds between status checks
            show_progress: If True, print progress updates
            verbose: If True, print all streaming events from worker
            raise_on_timeout: If True, raise TimeoutError on timeout.
                             If False, return False on timeout.

        Returns:
            True if task completed, False if timeout (when raise_on_timeout=False)

        Raises:
            TimeoutError: If timeout exceeded and raise_on_timeout=True
        """
        start = time.time()
        last_status = None
        last_event_index = 0
        last_message = None
        spinner = itertools.cycle(["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"])

        if show_progress:
            print(f"[{self.service}] Task {self.task_id[:8]}... started")
            sys.stdout.flush()

        while True:
            if self.is_ready():
                if show_progress:
                    # Clear spinner line
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    sys.stdout.flush()
                    elapsed = time.time() - start
                    status = self.status
                    if status == "completed":
                        print(f"[{self.service}] Completed in {elapsed:.1f}s")
                    else:
                        print(f"✗ [{self.service}] Failed after {elapsed:.1f}s")
                return True

            if timeout is not None and timeout > 0:
                elapsed = time.time() - start
                if elapsed >= timeout:
                    if show_progress:
                        sys.stdout.write("\r" + " " * 80 + "\r")
                        sys.stdout.flush()
                        print(f"⏰ [{self.service}] Timeout after {timeout}s")
                    if raise_on_timeout:
                        raise TimeoutError(
                            f"Task {self.task_id} timed out after {timeout}s. "
                            f"Service: {self.service}, Status: {self.status}"
                        )
                    return False

            # Stream events from worker
            if verbose and self._server is not None:
                events = self._get_events(since_index=last_event_index)
                for event in events:
                    event_index = event.get("index")
                    if event_index is not None:
                        last_event_index = event_index + 1
                    # Clear spinner line before printing event
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    sys.stdout.flush()
                    self._print_event(event)
                    last_message = event.get("message")

            # Show spinner with elapsed time
            if show_progress:
                elapsed = time.time() - start
                spin_char = next(spinner)
                msg_part = f" {last_message}" if last_message else ""
                status_line = f"\r{spin_char} [{self.service}] Working... ({elapsed:.0f}s){msg_part}"
                # Truncate if too long
                if len(status_line) > 79:
                    status_line = status_line[:76] + "..."
                sys.stdout.write(status_line)
                sys.stdout.flush()

            time.sleep(poll_interval)

    def _get_events(self, since_index: int = 0) -> list:
        """Fetch events from server."""
        if self._server is None:
            return []
        try:
            # Try unified task system first
            if hasattr(self._server, "get_unified_task_progress"):
                return self._server.get_unified_task_progress(self.task_id, since_index)
            # Fall back to legacy
            return self._server.get_task_events(self.task_id, since_index)
        except Exception:
            return []

    def _print_event(self, event: dict) -> None:
        """Print a progress event."""
        message = event.get("message")
        progress = event.get("progress")
        data = event.get("data")

        # Build output line
        parts = []

        # Only show progress bar for meaningful progress (not fake 10%, 20% etc.)
        # Show for real milestones like intermediate steps or completion
        if progress is not None and progress > 0.5:
            pct = int(progress * 100)
            bar_width = 20
            filled = int(bar_width * progress)
            bar = "█" * filled + "░" * (bar_width - filled)
            parts.append(f"[{bar}] {pct}%")

        if message:
            parts.append(message)

        if data and isinstance(data, dict):
            # Show key info from data
            info_parts = []
            for key in ["step", "phase", "item", "url", "count"]:
                if key in data:
                    info_parts.append(f"{key}={data[key]}")
            if info_parts:
                parts.append(f"({', '.join(info_parts)})")

        if parts:
            print(f"  -> {' '.join(parts)}")

    def result(
        self,
        timeout: Optional[float] = None,
        poll_interval: float = 0.2,
        verbose: bool = True,
    ) -> Any:
        """
        Get the result, blocking until complete.

        Args:
            timeout: Maximum seconds to wait (None = forever)
            poll_interval: Seconds between status checks
            verbose: If True, stream progress events from worker

        Returns:
            The parsed result (typically a ScenarioList)

        Raises:
            TimeoutError: If timeout exceeded
            RuntimeError: If task failed
        """
        # Return cached result if available
        if self._cached_result is not None:
            return self._cached_result

        # Wait for completion
        if not self.wait(
            timeout=timeout,
            poll_interval=poll_interval,
            show_progress=True,
            verbose=verbose,
        ):
            raise TimeoutError(
                f"Task {self.task_id} did not complete within {timeout}s"
            )

        # Check for failure
        status = self._get_status()
        if status and status.status == "failed":
            error = status.error or "Unknown error"
            raise RuntimeError(f"Task {self.task_id} failed: {error}")

        # Fetch and parse result
        result = self._fetch_result()
        self._cached_result = result

        # Call any registered callbacks
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception:
                pass

        return result

    def stream_events(self, poll_interval: float = 0.5):
        """
        Generator that yields progress events as they arrive.

        Useful for custom progress display or logging.

        Args:
            poll_interval: Seconds between polls

        Yields:
            Event dicts with index, timestamp, progress, message, data

        Example:
            >>> for event in pending.stream_events():
            ...     if event.get("message"):
            ...         print(event["message"])
            ...     if pending.is_ready():
            ...         break
        """
        last_index = 0

        while not self.is_ready():
            events = self._get_events(since_index=last_index)
            for event in events:
                event_index = event.get("index")
                if event_index is not None:
                    last_index = event_index + 1
                yield event
            time.sleep(poll_interval)

        # Yield any final events
        events = self._get_events(since_index=last_index)
        for event in events:
            yield event

    def _fetch_result(self) -> Any:
        """
        Fetch and parse the result from the server.

        Returns:
            Parsed result
        """
        if self._server is None:
            # No server - result should have been set directly
            if self._cached_result is not None:
                return self._cached_result
            raise RuntimeError("No server configured and no cached result")

        # Get task data - try unified first
        task = None
        if hasattr(self._server, "get_unified_task"):
            task = self._server.get_unified_task(self.task_id)

        if task is None:
            # Fall back to legacy status
            status = self._get_status()
            if status is None or status.result_ref is None:
                raise RuntimeError("Result not available")

            # Fetch result from blob store
            result_bytes = self._server.pull_binary(status.result_ref)
            if result_bytes is None:
                raise RuntimeError(f"Result blob {status.result_ref} not found")

            import json

            result_dict = json.loads(result_bytes.decode("utf-8"))
        else:
            # Unified task - result may be inline or in blob store
            result_dict = task.get("result")
            result_ref = task.get("result_ref")

            if result_dict is None and result_ref:
                # Fetch from blob store
                result_bytes = self._server.pull_binary(result_ref)
                if result_bytes is None:
                    raise RuntimeError(f"Result blob {result_ref} not found")
                import json

                result_dict = json.loads(result_bytes.decode("utf-8"))

            if result_dict is None:
                raise RuntimeError("Result not available")

        # Use service class to parse if available
        if self._service_class is not None:
            return self._service_class.parse_result(result_dict)

        # Use generic parser if result_pattern is specified
        if self._result_pattern is not None:
            from .result_parsers import ResultParser

            return ResultParser.parse(
                result_dict,
                self._result_pattern,
                self._result_field,
            )

        # Return raw dict if no parser
        return result_dict

    def cancel(self) -> bool:
        """
        Cancel the pending task.

        Returns:
            True if cancelled, False if already complete or cancellation failed
        """
        if self.is_ready():
            return False

        if self._server is None:
            return False

        try:
            # Try unified task system first
            if hasattr(self._server, "fail_unified_task"):
                self._server.fail_unified_task(self.task_id, "Cancelled by user")
            else:
                self._server.fail_service_task(self.task_id, "Cancelled by user")
            return True
        except Exception:
            return False

    def on_complete(self, callback: Callable[[Any], None]) -> "PendingResult":
        """
        Register a callback to be called when result is ready.

        Args:
            callback: Function to call with the result

        Returns:
            self (for chaining)
        """
        self._callbacks.append(callback)
        return self

    def set_result(self, result: Any) -> None:
        """
        Directly set the result (for local execution).

        Args:
            result: The result to set
        """
        self._cached_result = result

    @classmethod
    def from_completed(
        cls,
        task_id: str,
        service: str,
        params: Dict[str, Any],
        result: Any,
        service_class: Optional[type] = None,
    ) -> "PendingResult":
        """
        Create a PendingResult with an already-completed result.

        Used for local execution where the result is immediately available.

        Args:
            task_id: Task identifier
            service: Service name
            params: Task parameters
            result: The completed result
            service_class: Service class for result parsing

        Returns:
            PendingResult with cached result
        """
        pending = cls(
            task_id=task_id,
            service=service,
            params=params,
            server=None,
            service_class=service_class,
        )

        # Parse the result if service class provided
        if service_class is not None and hasattr(service_class, "parse_result"):
            try:
                parsed = service_class.parse_result(result)
                pending._cached_result = parsed
            except Exception:
                pending._cached_result = result
        else:
            pending._cached_result = result

        return pending

    def __repr__(self) -> str:
        return f"PendingResult(task_id={self.task_id!r}, service={self.service!r}, status={self.status!r})"

    def _repr_html_(self) -> str:
        """
        Rich HTML representation for Jupyter notebooks.

        Returns:
            HTML string with status widget
        """
        status = self.status
        status_colors = {
            "pending": "#FFA500",  # Orange
            "claimed": "#1E90FF",  # Blue
            "running": "#1E90FF",  # Blue
            "completed": "#32CD32",  # Green
            "failed": "#DC143C",  # Red
            "cancelled": "#808080",  # Gray
            "unknown": "#808080",  # Gray
        }
        color = status_colors.get(status, "#808080")

        # Get progress if available
        task_status = self._get_status()
        progress_bar = ""
        if task_status and task_status.progress is not None:
            pct = int(task_status.progress * 100)
            progress_bar = f"""
            <div style="background: #e0e0e0; border-radius: 4px; height: 8px; margin-top: 8px;">
                <div style="background: {color}; width: {pct}%; height: 100%; border-radius: 4px;"></div>
            </div>
            """

        message = ""
        if task_status and task_status.message:
            message = f'<div style="color: #666; font-size: 12px; margin-top: 4px;">{task_status.message}</div>'

        return f"""
        <div style="font-family: sans-serif; padding: 12px; border: 1px solid #ddd; border-radius: 8px; max-width: 400px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">
                    {status.upper()}
                </span>
                <span style="color: #333; font-weight: bold;">{self.service}</span>
            </div>
            <div style="color: #666; font-size: 12px; margin-top: 8px;">
                Task ID: <code>{self.task_id[:8]}...</code>
            </div>
            {progress_bar}
            {message}
        </div>
        """
