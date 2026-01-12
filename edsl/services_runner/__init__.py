"""
Services Runner - Task queue infrastructure for EDSL external services.

This module provides a task queue system that can run:
- Locally: Auto-starts an in-process server on first dispatch
- Remotely: Connects to EXPECTED_PARROT_SERVICE_RUNNER_URL if set

The same protocol is used for both modes, making local development
behave identically to production.

Usage:
    from edsl.services_runner import require_client
    
    # Get a client (auto-starts local server if needed)
    client = require_client()
    
    # Submit a task
    task_id = client.create_unified_task(
        task_type="wikipedia",
        params={"url": "https://en.wikipedia.org/..."}
    )
    
    # Poll for result
    task = client.get_unified_task(task_id)
    if task["status"] == "completed":
        result = task["result"]
        
Remote Usage:
    # Set environment variable to use remote server
    export EXPECTED_PARROT_SERVICE_RUNNER_URL="https://your-server.com"
    
    # Now all service calls go to the remote server
    # If server is not reachable, an exception is raised
"""

import os
import atexit
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .client import TaskQueueClient
    from .local import LocalTaskQueueClient

# Module-level state for local server
_local_server = None
_local_client = None


class ServiceRunnerConnectionError(Exception):
    """Raised when the remote service runner is not reachable."""
    pass


def require_client(purpose: str = "") -> "TaskQueueClient":
    """
    Get or create a task queue client.
    
    If EXPECTED_PARROT_SERVICE_RUNNER_URL is set, connects to that remote server.
    The server must be reachable (health check must pass) or an exception is raised.
    
    If the URL is not set, starts a local in-process server.
    
    Args:
        purpose: Optional description of why client is needed (for logging)
        
    Returns:
        TaskQueueClient connected to either remote or local server
        
    Raises:
        ServiceRunnerConnectionError: If remote URL is set but server is not reachable
        
    Example:
        >>> client = require_client(purpose="firecrawl scrape")
        >>> task_id = client.create_unified_task("firecrawl", {"url": "..."})
    """
    global _local_server, _local_client
    
    # Check for remote URL first (separate from EXPECTED_PARROT_URL)
    remote_url = os.getenv("EXPECTED_PARROT_SERVICE_RUNNER_URL")
    if remote_url:
        from .client import TaskQueueClient
        client = TaskQueueClient(remote_url)
        
        # Verify server is reachable - raise exception if not
        if not client.health_check():
            raise ServiceRunnerConnectionError(
                f"Service runner at {remote_url} is not reachable. "
                f"Check that the server is running, or unset EXPECTED_PARROT_SERVICE_RUNNER_URL "
                f"to use local execution."
            )
        return client
    
    # Use local server
    if _local_client is None:
        from .local import start_local_server
        _local_server, _local_client = start_local_server()
        
        # Register cleanup on exit
        atexit.register(_cleanup_local_server)
    
    return _local_client


def _cleanup_local_server():
    """Cleanup local server on Python exit."""
    global _local_server, _local_client
    if _local_server is not None:
        try:
            _local_server.stop()
        except Exception:
            pass
        _local_server = None
        _local_client = None


def get_local_server():
    """Get the local server instance (if running)."""
    return _local_server


__all__ = [
    "require_client",
    "get_local_server",
    "ServiceRunnerConnectionError",
]

