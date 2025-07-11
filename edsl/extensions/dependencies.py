# dependencies.py
from fastapi import Request
import httpx


async def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency function to get the shared HTTP client from application state via the request object."""
    # Access the client from app.state, initialized by the lifespan manager
    # FastAPI makes the request object available, and request.app points to the FastAPI instance.
    # Increase timeout limits: creation of a survey can take several minutes while
    # the downstream service performs multiple remote-inference stages.  Use a
    # generous overall timeout (e.g. 10 minutes) but keep the connection timeout
    # short so we still fail fast on unreachable hosts.
    timeout = httpx.Timeout(600.0, connect=5.0)  # 10 min total, 5 s connect
    return httpx.AsyncClient(timeout=timeout)
