"""
Task Polling - Client-side utilities for polling background task status.

This module provides utilities for polling task status with progressive
intervals, for use by service clients.
"""

import time
from typing import Callable, Optional, Any, Dict


class AdaptivePoller:
    """
    Polling with progressive intervals.

    The poller starts with shorter intervals and progressively increases
    them based on the estimated task duration and elapsed time.
    """

    def __init__(self, estimated_duration: float = 10.0):
        """
        Initialize the adaptive poller.

        Args:
            estimated_duration: Estimated task duration in seconds
        """
        self.estimated_duration = estimated_duration
        self.start_time: Optional[float] = None
        self.poll_count = 0

    def get_interval(self) -> float:
        """
        Get the next polling interval in seconds.

        Returns:
            Number of seconds to wait before the next poll
        """
        if self.start_time is None:
            self.start_time = time.time()

        self.poll_count += 1
        elapsed = time.time() - self.start_time
        remaining = max(0, self.estimated_duration - elapsed)

        # Longer intervals early, shorter near completion
        if remaining > 60:
            return min(30, remaining * 0.3)
        elif remaining > 30:
            return 10.0
        elif remaining > 10:
            return 5.0
        elif remaining > 0:
            return 2.0
        else:
            # Past estimate - use backoff
            overtime = elapsed - self.estimated_duration
            if overtime < 30:
                return 2.0
            elif overtime < 120:
                return 5.0
            return 10.0

    def reset(self) -> None:
        """Reset the poller for reuse."""
        self.start_time = None
        self.poll_count = 0


def poll_until_complete(
    get_status_fn: Callable[[str], Optional[Dict[str, Any]]],
    task_id: str,
    timeout: float = 3600.0,
    estimated_duration: float = 10.0,
    on_status_change: Optional[Callable[[Dict[str, Any]], None]] = None,
    show_progress: bool = True,
) -> Dict[str, Any]:
    """
    Poll until a task completes.

    Args:
        get_status_fn: Function that takes a task_id and returns status dict
        task_id: The task ID to poll
        timeout: Maximum time to wait in seconds (default: 1 hour)
        estimated_duration: Estimated task duration for adaptive polling
        on_status_change: Optional callback called when status changes
        show_progress: Whether to show progress output

    Returns:
        Final status dict when task completes

    Raises:
        TimeoutError: If task doesn't complete within timeout
        RuntimeError: If task fails
    """
    poller = AdaptivePoller(estimated_duration=estimated_duration)
    start = time.time()
    last_status: Optional[str] = None

    if show_progress:
        try:
            from rich.console import Console

            console = Console()
        except ImportError:
            console = None
    else:
        console = None

    while time.time() - start < timeout:
        status_dict = get_status_fn(task_id)

        if status_dict is None:
            raise RuntimeError(f"Task {task_id} not found")

        current_status = status_dict.get("status")

        # Callback on status change
        if current_status != last_status:
            if on_status_change:
                on_status_change(status_dict)
            if console and show_progress:
                console.print(f"[dim]Task {task_id[:8]}... {current_status}[/dim]")
        last_status = current_status

        # Check for terminal states
        if current_status == "completed":
            return status_dict
        elif current_status == "failed":
            error_msg = status_dict.get("error", "Unknown error")
            error_type = status_dict.get("error_type", "Exception")
            raise RuntimeError(f"Task failed: {error_type}: {error_msg}")
        elif current_status == "cancelled":
            raise RuntimeError("Task was cancelled")

        # Wait before next poll
        time.sleep(poller.get_interval())

    raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")
