# dependencies.py
from fastapi import Request
import httpx

async def get_http_client(request: Request) -> httpx.AsyncClient:
    """Dependency function to get the shared HTTP client from application state via the request object."""
    # Access the client from app.state, initialized by the lifespan manager
    # FastAPI makes the request object available, and request.app points to the FastAPI instance.
    timeout = httpx.Timeout(60.0, connect=5.0) # 60s total, 5s connect
    return httpx.AsyncClient(timeout=timeout) 