"""FastAPI server for EDSL App backend."""

from datetime import datetime
from typing import Any, Optional, Dict, List
import uuid
import json
import logging
import sqlite3
import os
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Depends, status
    from fastapi.responses import JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    raise ImportError(
        "FastAPI and uvicorn are required for the app server. "
        "Install with: pip install 'edsl[services]' or poetry install -E services"
    )

from .app import AppBase
from ..base import Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class AppMetadata(BaseModel):
    app_id: str
    name: str
    description: Optional[str] = None
    application_type: str
    created_at: datetime
    parameters: List[tuple] = Field(default_factory=list)
    available_formatters: List[str] = Field(default_factory=list)

class AppExecutionRequest(BaseModel):
    answers: Dict[str, Any]
    formatter_name: Optional[str] = None

class AppExecutionResponse(BaseModel):
    execution_id: str
    status: str  # "running", "completed", "failed"
    result: Optional[Any] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str

class StatsResponse(BaseModel):
    total_apps: int
    total_executions: int
    uptime: str

# Database setup
class DatabaseManager:
    def __init__(self, db_path: str = "edsl_apps.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS apps (
                    app_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    application_type TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    app_data TEXT NOT NULL,
                    parameters TEXT,
                    available_formatters TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    execution_id TEXT PRIMARY KEY,
                    app_id TEXT NOT NULL,
                    status TEXT DEFAULT 'running',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (app_id) REFERENCES apps (app_id)
                )
            """)
            conn.commit()

    def store_app(self, app: AppBase) -> str:
        """Store an app and return its app_id."""
        app_id = str(uuid.uuid4())
        app_data = json.dumps(app.to_dict())
        parameters = json.dumps(app.parameters)
        available_formatters = json.dumps(list(app.output_formatters.mapping.keys()))

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO apps (app_id, name, description, application_type, app_data, parameters, available_formatters)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                app_id,
                app.application_name,
                app.description,
                app.application_type,
                app_data,
                parameters,
                available_formatters
            ))
            conn.commit()

        logger.info(f"Stored app {app_id} ({app.application_name})")
        return app_id

    def get_app(self, app_id: str) -> Optional[AppBase]:
        """Retrieve an app by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT app_data FROM apps WHERE app_id = ?", (app_id,)
            )
            row = cursor.fetchone()

            if row:
                app_data = json.loads(row[0])
                return AppBase.from_dict(app_data)
            return None

    def get_app_metadata(self, app_id: str) -> Optional[AppMetadata]:
        """Get app metadata without full app data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT app_id, name, description, application_type, created_at, parameters, available_formatters
                FROM apps WHERE app_id = ?
            """, (app_id,))
            row = cursor.fetchone()

            if row:
                return AppMetadata(
                    app_id=row[0],
                    name=row[1],
                    description=row[2],
                    application_type=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    parameters=json.loads(row[5]),
                    available_formatters=json.loads(row[6])
                )
            return None

    def list_apps(self) -> List[AppMetadata]:
        """List all apps."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT app_id, name, description, application_type, created_at, parameters, available_formatters
                FROM apps ORDER BY created_at DESC
            """)

            apps = []
            for row in cursor.fetchall():
                apps.append(AppMetadata(
                    app_id=row[0],
                    name=row[1],
                    description=row[2],
                    application_type=row[3],
                    created_at=datetime.fromisoformat(row[4]),
                    parameters=json.loads(row[5]),
                    available_formatters=json.loads(row[6])
                ))
            return apps

    def store_execution(self, app_id: str, execution_id: str, status: str, result: Any = None, error: str = None):
        """Store execution result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO executions (execution_id, app_id, status, result, error)
                VALUES (?, ?, ?, ?, ?)
            """, (execution_id, app_id, status, json.dumps(result) if result else None, error))
            conn.commit()

    def get_execution(self, execution_id: str) -> Optional[AppExecutionResponse]:
        """Get execution status and result."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT execution_id, status, result, error FROM executions WHERE execution_id = ?
            """, (execution_id,))
            row = cursor.fetchone()

            if row:
                result = json.loads(row[2]) if row[2] else None
                return AppExecutionResponse(
                    execution_id=row[0],
                    status=row[1],
                    result=result,
                    error=row[3]
                )
            return None

# Global database manager
db_manager = DatabaseManager()

# FastAPI app
app = FastAPI(
    title="EDSL App Server",
    description="FastAPI backend for EDSL applications",
    version="1.0.0"
)

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

# Dashboard route
@app.get("/")
async def dashboard():
    """Serve the dashboard HTML."""
    dashboard_path = Path(__file__).parent / "index.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    else:
        return {"message": "Dashboard not found. Make sure index.html exists in the app directory."}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get server statistics."""
    with sqlite3.connect(db_manager.db_path) as conn:
        app_count = conn.execute("SELECT COUNT(*) FROM apps").fetchone()[0]
        exec_count = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]

    return StatsResponse(
        total_apps=app_count,
        total_executions=exec_count,
        uptime="N/A"  # TODO: Track actual uptime
    )

# App management endpoints
@app.post("/apps")
async def push_app(app_data: dict):
    """Push a new app to the server."""
    try:
        # Reconstruct the app from the dictionary
        app = AppBase.from_dict(app_data)
        app_id = db_manager.store_app(app)

        return {"app_id": app_id, "message": f"App '{app.application_name}' pushed successfully"}
    except Exception as e:
        logger.error(f"Error pushing app: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid app data: {str(e)}")

@app.get("/apps", response_model=List[AppMetadata])
async def list_apps():
    """List all available apps."""
    return db_manager.list_apps()

@app.get("/apps/{app_id}", response_model=AppMetadata)
async def get_app_metadata(app_id: str):
    """Get app metadata and parameters."""
    metadata = db_manager.get_app_metadata(app_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="App not found")
    return metadata

@app.get("/apps/{app_id}/parameters")
async def get_app_parameters(app_id: str):
    """Get required parameters for an app."""
    metadata = db_manager.get_app_metadata(app_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="App not found")
    return {"parameters": metadata.parameters}

@app.get("/apps/{app_id}/data")
async def get_app_data(app_id: str):
    """Get full app data for reconstruction."""
    with sqlite3.connect(db_manager.db_path) as conn:
        cursor = conn.execute("SELECT app_data FROM apps WHERE app_id = ?", (app_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="App not found")

        app_data = json.loads(row[0])
        return app_data

@app.delete("/apps/{app_id}")
async def delete_app(app_id: str):
    """Remove an app from the server."""
    # Check if app exists
    if not db_manager.get_app_metadata(app_id):
        raise HTTPException(status_code=404, detail="App not found")

    try:
        with sqlite3.connect(db_manager.db_path) as conn:
            # Delete executions first (foreign key constraint)
            conn.execute("DELETE FROM executions WHERE app_id = ?", (app_id,))
            # Delete the app
            cursor = conn.execute("DELETE FROM apps WHERE app_id = ?", (app_id,))
            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="App not found")

        logger.info(f"Deleted app {app_id}")
        return {"message": "App deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting app {app_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting app: {str(e)}")

# App execution endpoints
@app.post("/apps/{app_id}/execute", response_model=AppExecutionResponse)
async def execute_app(app_id: str, request: AppExecutionRequest):
    """Execute an app with provided parameters."""
    # Get the app
    app_instance = db_manager.get_app(app_id)
    if not app_instance:
        raise HTTPException(status_code=404, detail="App not found")

    # Generate execution ID
    execution_id = str(uuid.uuid4())

    try:
        # Execute the app
        logger.info(f"Executing app {app_id} with execution_id {execution_id}")

        # Use the formatter if specified, otherwise use default
        formatter_name = request.formatter_name
        result = app_instance.output(
            answers=request.answers,
            formater_to_use=formatter_name  # Note: typo in original method name
        )

        # Convert result to JSON-serializable format
        try:
            # Try to convert to dict if possible
            if hasattr(result, 'to_dict'):
                serializable_result = result.to_dict()
            elif hasattr(result, '__dict__'):
                serializable_result = {k: str(v) for k, v in result.__dict__.items()}
            else:
                serializable_result = str(result)
        except Exception:
            serializable_result = str(result)

        # Store the successful execution
        db_manager.store_execution(
            app_id=app_id,
            execution_id=execution_id,
            status="completed",
            result=serializable_result
        )

        logger.info(f"App execution {execution_id} completed successfully")
        return AppExecutionResponse(
            execution_id=execution_id,
            status="completed",
            result=serializable_result
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"App execution {execution_id} failed: {error_msg}")

        # Store the failed execution
        db_manager.store_execution(
            app_id=app_id,
            execution_id=execution_id,
            status="failed",
            error=error_msg
        )

        return AppExecutionResponse(
            execution_id=execution_id,
            status="failed",
            error=error_msg
        )

@app.get("/executions/{execution_id}", response_model=AppExecutionResponse)
async def get_execution_status(execution_id: str):
    """Get execution status and results."""
    execution = db_manager.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")