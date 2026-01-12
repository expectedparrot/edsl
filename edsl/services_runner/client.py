"""
TaskQueueClient - HTTP client for remote task queue servers.

This client implements the same interface as LocalTaskQueueClient but
communicates with a remote server over HTTP.

Used when EXPECTED_PARROT_SERVICE_RUNNER_URL is set to point to a remote server.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class TaskQueueClient:
    """
    HTTP client for remote task queue server.
    
    Implements the same interface as LocalTaskQueueClient so they're
    interchangeable.
    
    Example:
        >>> client = TaskQueueClient("https://api.example.com")
        >>> task_id = client.create_unified_task("wikipedia", {"url": "..."})
        >>> task = client.get_unified_task(task_id)
    """
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize the client.
        
        Args:
            base_url: Base URL of the task queue server
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = None
    
    def _get_session(self):
        """Get or create requests session."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            if self.api_key:
                self._session.headers["Authorization"] = f"Bearer {self.api_key}"
            self._session.headers["Content-Type"] = "application/json"
        return self._session
    
    def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Make an HTTP request."""
        session = self._get_session()
        url = f"{self.base_url}{path}"
        
        response = session.request(method, url, json=json, params=params, timeout=timeout)
        response.raise_for_status()
        
        if response.content:
            return response.json()
        return None
    
    def health_check(self, timeout: float = 5.0) -> bool:
        """
        Check if the remote server is reachable and healthy.
        
        Args:
            timeout: Request timeout in seconds
            
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            result = self._request("GET", "/health", timeout=timeout)
            return result is not None and result.get("status") == "ok"
        except Exception:
            return False
    
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
        """Create a new task on the remote server."""
        payload = {
            "task_type": task_type,
            "params": params,
            "job_id": job_id,
            "group_id": group_id,
            "dependencies": dependencies or [],
            "bucket_id": bucket_id,
            "priority": priority,
            "meta": meta or {},
        }
        
        result = self._request("POST", "/api/tasks", json=payload)
        return result["task_id"]
    
    def claim_unified_task(
        self,
        task_types: List[str],
        worker_id: str,
        bucket_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Claim the next available task."""
        payload = {
            "task_types": task_types,
            "worker_id": worker_id,
            "bucket_id": bucket_id,
        }
        
        result = self._request("POST", "/api/tasks/claim", json=payload)
        return result  # May be None if no task available
    
    def complete_unified_task(
        self,
        task_id: str,
        result: Optional[Dict[str, Any]] = None,
        result_ref: Optional[str] = None,
    ) -> bool:
        """Mark a task as completed."""
        payload = {
            "result": result,
            "result_ref": result_ref,
        }
        
        self._request("POST", f"/api/tasks/{task_id}/complete", json=payload)
        return True
    
    def fail_unified_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        payload = {"error": error}
        self._request("POST", f"/api/tasks/{task_id}/fail", json=payload)
        return True
    
    def get_unified_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status and result."""
        try:
            return self._request("GET", f"/api/tasks/{task_id}")
        except Exception:
            return None
    
    def update_unified_task_progress(
        self,
        task_id: str,
        message: Optional[str] = None,
        progress: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update task progress."""
        payload = {
            "message": message,
            "progress": progress,
            "data": data,
        }
        
        try:
            self._request("POST", f"/api/tasks/{task_id}/progress", json=payload)
            return True
        except Exception:
            return False
    
    def get_unified_task_progress(
        self,
        task_id: str,
        since_index: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get progress events since a given index."""
        try:
            params = {"since_index": since_index}
            result = self._request("GET", f"/api/tasks/{task_id}/progress", params=params)
            return result or []
        except Exception:
            return []
    
    def create_task_group(
        self,
        group_id: str,
        job_id: Optional[str] = None,
    ) -> None:
        """Create a task group."""
        payload = {"group_id": group_id, "job_id": job_id}
        self._request("POST", "/api/groups", json=payload)
    
    def is_group_complete(self, group_id: str) -> bool:
        """Check if all tasks in a group are complete."""
        try:
            result = self._request("GET", f"/api/groups/{group_id}/status")
            return result.get("complete", False)
        except Exception:
            return False

