# main.py
from fastapi import FastAPI, Depends, Request
import httpx
import uvicorn
from contextlib import asynccontextmanager

# Import the router from gateway_router.py
from .gateway_router import router as gateway_router
# Import the dependency provider
from .dependencies import get_http_client
# Import the new test service router
from .test_service_router import router as test_router

# --- Lifespan Management ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the HTTP client lifecycle on application startup and shutdown."""
    # Initialize the client before the app starts
    app.state.http_client = httpx.AsyncClient()
    print("HTTP client started.")
    yield # Application runs here
    # Close the client after the app stops
    await app.state.http_client.aclose()
    print("HTTP client closed.")

# Create the main FastAPI application instance with the lifespan manager
app = FastAPI(
    title="Main Service Application",
    description="An application incorporating a gateway for external services.",
    version="1.0.0",
    lifespan=lifespan # Register the lifespan context manager
)

# --- Dependency Function (Removed) ---

# async def get_http_client() -> httpx.AsyncClient:
#     """Dependency function to get the shared HTTP client."""
#     # Access the client from app.state, initialized by the lifespan manager
#     return app.state.http_client

# --- Include Routers ---

# Include the gateway router
# We inject the get_http_client dependency here, which FastAPI will use
# for any Depends() call within the gateway_router routes.
app.include_router(
    gateway_router,
    tags=["Gateway Services"], 
    dependencies=[Depends(get_http_client)] 
)

# Include the test service router
app.include_router(
    test_router,
    tags=["Test Services"] 
    # No specific dependencies needed here unless the test service itself needs them
)

# --- Main Application Routes ---

@app.get("/")
async def root():
    """Root endpoint for the main application."""
    return {"message": "Welcome to the Main Application. Gateway services are at /services"}

# --- Run the Application (for local development) ---

if __name__ == "__main__":
    # Note: You might need to adjust the import string based on your project structure
    # if gateway_router is in a different directory.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 