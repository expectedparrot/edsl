"""
FastAPI server for the EDSL Service Runner.

This server provides HTTP endpoints for the task queue, allowing remote
execution of EDSL services. It can be run standalone or deployed to a
cloud platform.

Usage:
    # Run directly
    python -m edsl.services_runner.server --port 8080
    
    # Or with uvicorn
    uvicorn edsl.services_runner.server:app --host 0.0.0.0 --port 8080

Endpoints:
    GET  /health              - Health check
    POST /api/tasks           - Create a new task
    POST /api/tasks/claim     - Claim a task for processing
    GET  /api/tasks/{id}      - Get task status and result
    POST /api/tasks/{id}/complete - Mark task as completed
    POST /api/tasks/{id}/fail     - Mark task as failed
    POST /api/tasks/{id}/progress - Update task progress
    GET  /api/tasks/{id}/progress - Get task progress events
    POST /api/groups          - Create a task group
    GET  /api/groups/{id}/status - Check if group is complete
    GET  /api/services        - List all services with metadata
    GET  /api/services/{name} - Get specific service metadata
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Load .env from this directory
_server_dir = Path(__file__).parent
_env_file = _server_dir / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
        print(f"[EDSL Service Runner] Loaded .env from {_env_file}")
    except ImportError:
        print("[EDSL Service Runner] Warning: python-dotenv not installed, .env not loaded")

from .local import LocalServer

# Create FastAPI app
app = FastAPI(
    title="EDSL Service Runner",
    description="Task queue server for EDSL external services",
    version="1.0.0",
)

# Global server instance (created on startup)
_server: Optional[LocalServer] = None


def get_server() -> LocalServer:
    """Get the server instance, creating it if needed."""
    global _server
    if _server is None:
        _server = LocalServer(num_workers=4)
        _server.start()
    return _server


# ============================================================================
# Pydantic models for request/response bodies
# ============================================================================


class CreateTaskRequest(BaseModel):
    task_type: str
    params: Dict[str, Any]
    job_id: Optional[str] = None
    group_id: Optional[str] = None
    dependencies: List[str] = []
    bucket_id: Optional[str] = None
    priority: int = 0
    meta: Dict[str, Any] = {}


class CreateTaskResponse(BaseModel):
    task_id: str


class ClaimTaskRequest(BaseModel):
    task_types: List[str]
    worker_id: str
    bucket_id: Optional[str] = None


class CompleteTaskRequest(BaseModel):
    result: Optional[Dict[str, Any]] = None
    result_ref: Optional[str] = None


class FailTaskRequest(BaseModel):
    error: str


class ProgressUpdateRequest(BaseModel):
    message: Optional[str] = None
    progress: Optional[float] = None
    data: Optional[Dict[str, Any]] = None


class CreateGroupRequest(BaseModel):
    group_id: str
    job_id: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class GroupStatusResponse(BaseModel):
    group_id: str
    complete: bool


# ============================================================================
# Health check endpoint
# ============================================================================


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns server status for monitoring and client connection verification.
    """
    return HealthResponse(
        status="ok",
        service="edsl-service-runner",
        version="1.0.0",
    )


# ============================================================================
# Task endpoints
# ============================================================================


@app.post("/api/tasks", response_model=CreateTaskResponse)
async def create_task(request: CreateTaskRequest):
    """
    Create a new task.

    The task will be queued for processing by a worker.
    """
    server = get_server()

    task_id = server.create_unified_task(
        task_type=request.task_type,
        params=request.params,
        job_id=request.job_id,
        group_id=request.group_id,
        dependencies=request.dependencies,
        bucket_id=request.bucket_id,
        priority=request.priority,
        meta=request.meta,
    )

    return CreateTaskResponse(task_id=task_id)


@app.post("/api/tasks/claim")
async def claim_task(request: ClaimTaskRequest):
    """
    Claim the next available task for processing.

    Workers call this to get tasks to process.
    Returns the claimed task or null if none available.
    """
    server = get_server()

    task = server.claim_unified_task(
        task_types=request.task_types,
        worker_id=request.worker_id,
        bucket_id=request.bucket_id,
    )

    return task  # May be None


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """
    Get task status and result.

    Returns the full task object including status, result (if complete),
    and error (if failed).
    """
    server = get_server()

    task = server.get_unified_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return task


@app.post("/api/tasks/{task_id}/complete")
async def complete_task(task_id: str, request: CompleteTaskRequest):
    """
    Mark a task as completed.

    Workers call this when they've finished processing a task.
    """
    server = get_server()

    success = server.complete_unified_task(
        task_id=task_id,
        result=request.result,
        result_ref=request.result_ref,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {"status": "completed"}


@app.post("/api/tasks/{task_id}/fail")
async def fail_task(task_id: str, request: FailTaskRequest):
    """
    Mark a task as failed.

    Workers call this when task processing fails.
    """
    server = get_server()

    success = server.fail_unified_task(task_id=task_id, error=request.error)

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {"status": "failed"}


@app.post("/api/tasks/{task_id}/progress")
async def update_progress(task_id: str, request: ProgressUpdateRequest):
    """
    Update task progress.

    Workers call this to report progress during long-running tasks.
    """
    server = get_server()

    success = server.update_unified_task_progress(
        task_id=task_id,
        message=request.message,
        progress=request.progress,
        data=request.data,
    )

    if not success:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {"status": "updated"}


@app.get("/api/tasks/{task_id}/progress")
async def get_progress(task_id: str, since_index: int = 0):
    """
    Get task progress events.

    Returns progress events since the given index for incremental updates.
    """
    server = get_server()

    events = server.get_unified_task_progress(task_id=task_id, since_index=since_index)

    return events


# ============================================================================
# Group endpoints
# ============================================================================


@app.post("/api/groups")
async def create_group(request: CreateGroupRequest):
    """
    Create a task group.

    Groups allow tracking multiple related tasks together.
    """
    server = get_server()

    server.create_task_group(group_id=request.group_id, job_id=request.job_id)

    return {"status": "created", "group_id": request.group_id}


@app.get("/api/groups/{group_id}/status", response_model=GroupStatusResponse)
async def get_group_status(group_id: str):
    """
    Check if all tasks in a group are complete.
    """
    server = get_server()

    complete = server.is_group_complete(group_id)

    return GroupStatusResponse(group_id=group_id, complete=complete)


# ============================================================================
# Service metadata endpoints
# ============================================================================


class ServiceMetadataResponse(BaseModel):
    """Metadata for a single service."""

    name: str
    description: str
    version: str
    aliases: List[str]
    result_pattern: str
    result_field: Optional[str] = None
    required_keys: List[str]
    operations: Dict[str, Dict[str, Any]]  # operation_name -> {input_param, defaults}
    extends: List[str]


class ServicesResponse(BaseModel):
    """Response containing all available services."""

    services: Dict[str, ServiceMetadataResponse]


@app.get("/api/services", response_model=ServicesResponse)
async def list_services():
    """
    List all available services with their metadata.

    This endpoint allows clients to discover services and their
    result parsing patterns without having edsl-services installed.
    """
    from edsl.services import ServiceRegistry
    from edsl.services import _ensure_builtin_services

    # Ensure services are loaded (triggers entry point discovery)
    _ensure_builtin_services()

    services = {}
    for name in ServiceRegistry.list():
        meta = ServiceRegistry.get_metadata(name)
        service_class = ServiceRegistry.get(name)

        if meta and service_class:
            services[name] = ServiceMetadataResponse(
                name=name,
                description=getattr(service_class, "description", ""),
                version=getattr(service_class, "version", "1.0.0"),
                aliases=meta.aliases,
                result_pattern=meta.result_pattern,
                result_field=meta.result_field,
                required_keys=service_class.get_required_keys(),
                operations={
                    op_name: {
                        "input_param": op_schema.input_param,
                        "defaults": op_schema.defaults,
                    }
                    for op_name, op_schema in meta.operations.items()
                },
                extends=meta.extends,
            )

    return ServicesResponse(services=services)


@app.get("/api/services/{service_name}", response_model=ServiceMetadataResponse)
async def get_service(service_name: str):
    """
    Get metadata for a specific service.

    Args:
        service_name: Service name or alias
    """
    from edsl.services import ServiceRegistry
    from edsl.services import _ensure_builtin_services

    _ensure_builtin_services()

    meta = ServiceRegistry.get_metadata(service_name)
    service_class = ServiceRegistry.get(service_name)

    if not meta or not service_class:
        raise HTTPException(status_code=404, detail=f"Service {service_name} not found")

    return ServiceMetadataResponse(
        name=meta.name,
        description=getattr(service_class, "description", ""),
        version=getattr(service_class, "version", "1.0.0"),
        aliases=meta.aliases,
        result_pattern=meta.result_pattern,
        result_field=meta.result_field,
        required_keys=service_class.get_required_keys(),
        operations={
            op_name: {
                "input_param": op_schema.input_param,
                "defaults": op_schema.defaults,
            }
            for op_name, op_schema in meta.operations.items()
        },
        extends=meta.extends,
    )


# ============================================================================
# Startup/shutdown events
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize the server on startup."""
    # Ensure services are loaded BEFORE starting workers
    # This triggers entry point discovery so workers can find task types
    from edsl.services import _ensure_builtin_services, ServiceRegistry, KEYS

    _ensure_builtin_services()
    service_count = len(ServiceRegistry.list())
    print(f"[EDSL Service Runner] Loaded {service_count} services")

    # Log available keys (for debugging)
    available_keys = KEYS.to_dict()
    key_names = list(available_keys.keys())
    print(f"[EDSL Service Runner] Available API keys: {key_names}")

    # Pre-create the server to ensure workers are running
    get_server()
    print("[EDSL Service Runner] Server started with workers")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _server
    if _server is not None:
        _server.stop()
        _server = None
        print("[EDSL Service Runner] Server stopped")


# ============================================================================
# CLI entry point
# ============================================================================


def main():
    """Run the server from command line."""
    parser = argparse.ArgumentParser(description="EDSL Service Runner Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--workers", type=int, default=4, help="Number of task workers")
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    import uvicorn

    print(f"[EDSL Service Runner] Starting server on {args.host}:{args.port}")
    print(f"[EDSL Service Runner] Workers: {args.workers}")
    print(f"[EDSL Service Runner] Health check: http://{args.host}:{args.port}/health")

    uvicorn.run(
        "edsl.services_runner.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
