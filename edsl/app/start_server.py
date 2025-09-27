#!/usr/bin/env python3
"""Startup script for EDSL App FastAPI server."""

import sys

def start_server():
    """Start the FastAPI server."""
    try:
        import uvicorn
    except ImportError:
        print("FastAPI and uvicorn are required for the app server.")
        print("Install with: pip install 'edsl[services]' or poetry install -E services")
        sys.exit(1)

    # Import the app
    try:
        from edsl.app.server import app
    except ImportError as e:
        print(f"Failed to import server: {e}")
        sys.exit(1)

    print("Starting EDSL App FastAPI Server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation: http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    print()

    # Start the server
    uvicorn.run(
        "edsl.app.server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    start_server()