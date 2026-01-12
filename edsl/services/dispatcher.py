"""
TaskDispatcher: Creates and dispatches tasks to external services.

Provides the main dispatch() function that routes requests to registered
services via the configured RemoteServer using the unified task system.

Example:
    >>> from edsl.services import dispatch, set_default_server
    >>> from edsl.store import InMemoryServer
    >>> 
    >>> # Configure the server (required)
    >>> set_default_server(InMemoryServer())
    >>> 
    >>> # Dispatch to a service
    >>> pending = dispatch("exa", {"query": "AI researchers at Stanford"})
    >>> result = pending.result()
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .registry import ServiceRegistry
from .pending import PendingResult

if TYPE_CHECKING:
    pass


class TaskDispatcher:
    """
    Dispatches tasks to the unified task queue via RemoteServer.
    
    All tasks are dispatched to a RemoteServer where workers process them.
    A server must be configured before dispatching tasks.
    
    Now uses the unified task system which supports:
    - All external services (embeddings, firecrawl, vibes, etc.)
    - LLM inference tasks (with dependencies)
    - Task groups and jobs
    """
    
    _default_server: Optional[Any] = None
    
    @classmethod
    def set_default_server(cls, server: Any) -> None:
        """
        Set the default RemoteServer for task dispatch.
        
        Args:
            server: RemoteServer instance to use by default
        """
        cls._default_server = server
    
    @classmethod
    def get_default_server(cls) -> Optional[Any]:
        """
        Get the default RemoteServer.
        
        Returns:
            The default server, or None if not set
        """
        return cls._default_server
    
    @classmethod
    def _get_or_create_local_server(cls) -> Any:
        """
        Get the configured EDSL server.
        
        Uses EXPECTED_PARROT_URL and EXPECTED_PARROT_API_KEY from environment.
        
        Returns:
            HTTPClient configured for the server
        """
        from edsl.services_runner import require_client
        return require_client(purpose="service dispatch")
    
    @classmethod
    def dispatch(
        cls,
        service: str,
        params: Dict[str, Any],
        *,
        server: Optional[Any] = None,
        meta: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        group_id: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
        bucket_id: Optional[str] = None,
        priority: int = 0,
    ) -> PendingResult:
        """
        Dispatch a task to an external service via the unified task queue.
        
        Args:
            service: Service/task type (e.g., "exa", "firecrawl", "llm_inference")
            params: Service-specific parameters (opaque to framework)
            server: RemoteServer to use (defaults to class default)
            meta: Additional metadata (user_id, priority, etc.)
            job_id: Optional top-level job grouping
            group_id: Optional sub-grouping (for aggregated completion)
            dependencies: List of task_ids this task depends on
            bucket_id: Optional bucket for rate-limit routing
            priority: Higher = more urgent (default 0)
            
        Returns:
            PendingResult that can be used to wait for/retrieve results
            
        Raises:
            ValueError: If service not found, validation fails, or no server configured
        """
        # Get the service class
        service_class = ServiceRegistry.get_or_raise(service)
        
        # Use the canonical service name (not alias) for task_type
        # This ensures workers can find the handler
        canonical_name = service_class.name
        
        # Validate parameters
        if not service_class.validate_params(params):
            raise ValueError(f"Invalid parameters for service '{service}'")
        
        # Get server - if none configured, auto-start local server
        use_server = server or cls._default_server
        if use_server is None:
            use_server = cls._get_or_create_local_server()
        
        # Build metadata
        task_meta = {
            "user_id": cls._get_user_id(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if meta:
            task_meta.update(meta)
        
        # Create task on server using unified task system
        task_id = use_server.create_unified_task(
            task_type=canonical_name,
            params=params,
            job_id=job_id,
            group_id=group_id,
            dependencies=dependencies,
            bucket_id=bucket_id,
            priority=priority,
            meta=task_meta,
        )
        
        # Return PendingResult connected to server
        return PendingResult(
            task_id=task_id,
            service=service,
            params=params,
            server=use_server,
            service_class=service_class,
        )
    
    @classmethod
    def dispatch_group(
        cls,
        tasks: List[Dict[str, Any]],
        *,
        server: Optional[Any] = None,
        job_id: Optional[str] = None,
    ) -> "PendingGroup":
        """
        Dispatch a group of related tasks.
        
        All tasks in the group are dispatched together. The group is complete
        when all tasks are complete.
        
        Args:
            tasks: List of task specifications, each with:
                - service: Task type
                - params: Task parameters
                - dependencies: Optional list of indices (0-based) of tasks this depends on
            server: RemoteServer to use
            job_id: Optional parent job ID
            
        Returns:
            PendingGroup for tracking aggregate completion
        """
        use_server = server or cls._default_server
        if use_server is None:
            raise ValueError(
                "No RemoteServer configured. Call set_default_server() first."
            )
        
        # Create group
        group_id = str(uuid.uuid4())
        use_server.create_task_group(group_id, job_id=job_id)
        
        # Create tasks, resolving dependency indices to task_ids
        task_ids = []
        pending_results = []
        
        for task_spec in tasks:
            # Resolve dependency indices to task_ids
            dep_indices = task_spec.get("dependencies", [])
            dependencies = [task_ids[i] for i in dep_indices if i < len(task_ids)]
            
            pending = cls.dispatch(
                service=task_spec["service"],
                params=task_spec["params"],
                server=use_server,
                meta=task_spec.get("meta"),
                group_id=group_id,
                job_id=job_id,
                dependencies=dependencies,
                bucket_id=task_spec.get("bucket_id"),
                priority=task_spec.get("priority", 0),
            )
            
            task_ids.append(pending.task_id)
            pending_results.append(pending)
        
        return PendingGroup(
            group_id=group_id,
            task_ids=task_ids,
            pending_results=pending_results,
            server=use_server,
        )
    
    @classmethod
    def _get_user_id(cls) -> str:
        """
        Get current user ID for task attribution.
        
        Returns:
            User ID string
        """
        import os
        return os.getenv("USER", os.getenv("USERNAME", "anonymous"))


class PendingGroup:
    """
    Represents a group of pending tasks.
    
    Provides methods to wait for all tasks or iterate over results.
    """
    
    def __init__(
        self,
        group_id: str,
        task_ids: List[str],
        pending_results: List[PendingResult],
        server: Any,
    ):
        self.group_id = group_id
        self.task_ids = task_ids
        self.pending_results = pending_results
        self.server = server
    
    def is_complete(self) -> bool:
        """Check if all tasks in the group are complete."""
        return self.server.is_group_complete(self.group_id)
    
    def wait(
        self,
        timeout: float = 300.0,
        poll_interval: float = 0.1,
        verbose: bool = False,
    ) -> List[Any]:
        """
        Wait for all tasks to complete and return their results.
        
        Args:
            timeout: Maximum seconds to wait
            poll_interval: Seconds between status checks
            verbose: Print progress updates
            
        Returns:
            List of results in task order
        """
        return [
            pending.result(timeout=timeout, poll_interval=poll_interval, verbose=verbose)
            for pending in self.pending_results
        ]
    
    def __iter__(self):
        """Iterate over pending results."""
        return iter(self.pending_results)
    
    def __len__(self):
        return len(self.pending_results)


def dispatch(
    service: str,
    params: Dict[str, Any],
    *,
    server: Optional[Any] = None,
    meta: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    group_id: Optional[str] = None,
    dependencies: Optional[List[str]] = None,
    bucket_id: Optional[str] = None,
    priority: int = 0,
) -> PendingResult:
    """
    Dispatch a task to an external service via the unified task queue.
    
    This is the main entry point for the External Services Framework.
    It routes requests to registered services and returns a PendingResult
    that can be used to wait for and retrieve results.
    
    A RemoteServer must be configured via set_default_server() or passed
    explicitly.
    
    Args:
        service: Service/task type (e.g., "exa", "firecrawl", "huggingface")
        params: Service-specific parameters (opaque to framework)
        server: RemoteServer to use (optional, uses default if not provided)
        meta: Additional metadata (user_id, priority, etc.)
        job_id: Optional top-level job grouping
        group_id: Optional sub-grouping (for aggregated completion)
        dependencies: List of task_ids this task depends on
        bucket_id: Optional bucket for rate-limit routing
        priority: Higher = more urgent (default 0)
        
    Returns:
        PendingResult for tracking and retrieving the result
        
    Example:
        >>> from edsl.services import dispatch, set_default_server
        >>> from edsl.store import InMemoryServer
        >>> 
        >>> set_default_server(InMemoryServer())
        >>> 
        >>> # Dispatch to Exa service
        >>> pending = dispatch("exa", {"query": "AI researchers at Stanford"})
        >>> 
        >>> # Wait for result
        >>> result = pending.result()
        
    Raises:
        ValueError: If service not found, parameters invalid, or no server configured
    """
    return TaskDispatcher.dispatch(
        service=service,
        params=params,
        server=server,
        meta=meta,
        job_id=job_id,
        group_id=group_id,
        dependencies=dependencies,
        bucket_id=bucket_id,
        priority=priority,
    )


def dispatch_group(
    tasks: List[Dict[str, Any]],
    *,
    server: Optional[Any] = None,
    job_id: Optional[str] = None,
) -> PendingGroup:
    """
    Dispatch a group of related tasks.
    
    All tasks in the group are dispatched together. The group is complete
    when all tasks are complete.
    
    Args:
        tasks: List of task specifications, each with:
            - service: Task type
            - params: Task parameters
            - dependencies: Optional list of indices (0-based) of tasks this depends on
        server: RemoteServer to use
        job_id: Optional parent job ID
        
    Returns:
        PendingGroup for tracking aggregate completion
    
    Example:
        >>> # Chain of dependent tasks
        >>> group = dispatch_group([
        ...     {"service": "firecrawl", "params": {"url": "..."}},
        ...     {"service": "embeddings", "params": {...}, "dependencies": [0]},
        ... ])
        >>> results = group.wait()
    """
    return TaskDispatcher.dispatch_group(
        tasks=tasks,
        server=server,
        job_id=job_id,
    )


def set_default_server(server: Any) -> None:
    """
    Set the default RemoteServer for task dispatch.
    
    This must be called before dispatching any tasks.
    
    Args:
        server: RemoteServer instance
        
    Example:
        >>> from edsl.services import set_default_server
        >>> from edsl.store import InMemoryServer
        >>> set_default_server(InMemoryServer())
    """
    TaskDispatcher.set_default_server(server)

