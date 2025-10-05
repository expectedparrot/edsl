"""FastAPI server for EDSL App backend."""

from datetime import datetime
from typing import Any, Optional, Dict, List
import uuid
import json
import logging
import sqlite3
import tempfile
import shutil
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
    from fastapi.responses import JSONResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel, Field
    import uvicorn
except ImportError:
    raise ImportError(
        "FastAPI and uvicorn are required for the app server. "
        "Install with: pip install fastapi uvicorn pydantic"
    )

import sys
from pathlib import Path

# Add parent directories to path to import edsl
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from edsl.app.app import App

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for API
class FormatterMetadata(BaseModel):
    name: str
    description: Optional[str] = None
    output_type: str = "auto"

class AppMetadata(BaseModel):
    app_id: str
    name: str
    description: Optional[str] = None
    application_type: str
    created_at: datetime
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    available_formatters: List[str] = Field(default_factory=list)
    formatter_metadata: List[Dict[str, Any]] = Field(default_factory=list)

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

    def store_app(self, app: App) -> str:
        """Store an app and return its app_id."""
        app_id = str(uuid.uuid4())
        app_dict = app.to_dict()
        app_data = json.dumps(app_dict)

        # Extract parameters from initial_survey
        parameters = json.dumps([
            {
                "question_name": q.question_name,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "question_options": getattr(q, 'question_options', None),
                "expected_object_type": getattr(q, 'expected_object_type', None)
            }
            for q in app.initial_survey.questions
        ])
        available_formatters = json.dumps(list(app.output_formatters.mapping.keys()))

        # Extract formatter metadata (output_type)
        try:
            formatter_metadata_list = [
                {
                    "name": name,
                    "description": getattr(formatter, 'description', None),
                    "output_type": getattr(formatter, 'output_type', 'auto')
                }
                for name, formatter in app.output_formatters.mapping.items()
            ]
            logger.info(f"Extracted formatter metadata: {formatter_metadata_list}")
            formatter_metadata = json.dumps(formatter_metadata_list)
        except Exception as e:
            logger.error(f"Failed to extract formatter metadata: {e}")
            formatter_metadata = json.dumps([])

        # Get application_type from the dict to avoid descriptor issues
        application_type = app_dict.get('application_type', 'base')

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO apps (app_id, name, description, application_type, app_data, parameters, available_formatters, formatter_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                app_id,
                app.application_name,
                app.description,
                application_type,
                app_data,
                parameters,
                available_formatters,
                formatter_metadata
            ))
            conn.commit()

        logger.info(f"Stored app {app_id} ({app.application_name})")
        return app_id

    def get_app(self, app_id: str) -> Optional[App]:
        """Retrieve an app by ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT app_data FROM apps WHERE app_id = ?", (app_id,)
            )
            row = cursor.fetchone()

            if row:
                app_data = json.loads(row[0])
                # Check if it's a CompositeApp
                if app_data.get("application_type") == "composite":
                    from edsl.app.composite_app import CompositeApp
                    return CompositeApp.from_dict(app_data)
                return App.from_dict(app_data)
            return None

    def get_app_metadata(self, app_id: str) -> Optional[AppMetadata]:
        """Get app metadata without full app data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT app_id, name, description, application_type, created_at, parameters, available_formatters, formatter_metadata
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
                    available_formatters=json.loads(row[6]),
                    formatter_metadata=json.loads(row[7]) if len(row) > 7 and row[7] else []
                )
            return None

    def list_apps(self) -> List[AppMetadata]:
        """List all apps."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT app_id, name, description, application_type, created_at, parameters, available_formatters, formatter_metadata
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
                    available_formatters=json.loads(row[6]),
                    formatter_metadata=json.loads(row[7]) if len(row) > 7 and row[7] else []
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

# EDSL object listing endpoint
@app.get("/edsl-objects/{object_type}")
async def list_edsl_objects(object_type: str):
    """List available EDSL objects from Coop for a given type."""
    try:
        # Import and call .list() on the appropriate class
        if object_type == "Survey":
            from edsl import Survey
            objects = Survey.list()
        elif object_type == "ScenarioList":
            from edsl import ScenarioList
            objects = ScenarioList.list()
        elif object_type == "Scenario":
            from edsl import Scenario
            objects = Scenario.list()
        elif object_type == "AgentList":
            from edsl import AgentList
            objects = AgentList.list()
        elif object_type == "Agent":
            from edsl import Agent
            objects = Agent.list()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown object type: {object_type}")

        # Convert to list of dicts with key fields
        object_list = []
        for obj in objects:
            obj_dict = obj if isinstance(obj, dict) else (obj.to_dict() if hasattr(obj, 'to_dict') else {})
            object_list.append({
                "uuid": obj_dict.get("uuid"),
                "alias": obj_dict.get("alias"),
                "description": obj_dict.get("description"),
                "owner_username": obj_dict.get("owner_username"),
                "url": obj_dict.get("url")
            })

        logger.info(f"Listed {len(object_list)} {object_type} objects from Coop")
        return {"objects": object_list}

    except Exception as e:
        logger.error(f"Error listing {object_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list objects: {str(e)}")

# App management endpoints
@app.post("/apps")
async def push_app(app_data: dict):
    """Push a new app to the server."""
    try:
        # Reconstruct the app from the dictionary
        # Check if it's a CompositeApp
        if app_data.get("application_type") == "composite":
            from edsl.app.composite_app import CompositeApp
            app_instance = CompositeApp.from_dict(app_data)
        else:
            app_instance = App.from_dict(app_data)
        app_id = db_manager.store_app(app_instance)

        return {"app_id": app_id, "message": f"App '{app_instance.application_name}' pushed successfully"}
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

# File upload endpoint
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and return its temporary path."""
    try:
        # Create a temporary file
        suffix = Path(file.filename).suffix if file.filename else ''
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

        # Write uploaded content to temp file
        shutil.copyfileobj(file.file, temp_file)
        temp_file.close()

        logger.info(f"File uploaded: {file.filename} -> {temp_file.name}")

        return {
            "file_path": temp_file.name,
            "original_filename": file.filename
        }
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

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
        logger.info(f"Request answers: {request.answers}")
        logger.info(f"Request formatter_name: {request.formatter_name}")

        # Process EDSL object parameters - pull from Coop if UUIDs provided
        processed_answers = dict(request.answers)
        logger.info(f"Initial processed_answers: {processed_answers}")

        for q in app_instance.initial_survey.questions:
            if q.question_type == "edsl_object" and q.question_name in processed_answers:
                uuid_value = processed_answers[q.question_name]
                if isinstance(uuid_value, str) and len(uuid_value) == 36:  # Looks like a UUID
                    logger.info(f"Pulling {q.expected_object_type} with UUID: {uuid_value}")
                    try:
                        # Pull the object from Coop
                        if q.expected_object_type == "Survey":
                            from edsl import Survey
                            obj = Survey.pull(uuid_value)
                        elif q.expected_object_type == "ScenarioList":
                            from edsl import ScenarioList
                            obj = ScenarioList.pull(uuid_value)
                        elif q.expected_object_type == "Scenario":
                            from edsl import Scenario
                            obj = Scenario.pull(uuid_value)
                        elif q.expected_object_type == "AgentList":
                            from edsl import AgentList
                            obj = AgentList.pull(uuid_value)
                        elif q.expected_object_type == "Agent":
                            from edsl import Agent
                            obj = Agent.pull(uuid_value)
                        else:
                            continue

                        # Store the object's dict - app.output will reconstruct it
                        # Important: Pass the dict, not the object instance, because app.output
                        # expects dicts for edsl_object types and will reconstruct them
                        processed_answers[q.question_name] = obj.to_dict()
                        logger.info(f"Successfully pulled and serialized {q.expected_object_type}")
                        logger.info(f"Object dict keys: {obj.to_dict().keys()}")
                    except Exception as e:
                        logger.error(f"Failed to pull {q.expected_object_type}: {e}")
                        raise HTTPException(status_code=400, detail=f"Failed to load {q.expected_object_type}: {str(e)}")

        logger.info(f"Final processed_answers keys: {processed_answers.keys()}")
        logger.info(f"Final processed_answers: {processed_answers}")

        # Use the formatter if specified, otherwise use default
        formatter_name = request.formatter_name
        logger.info(f"About to call app_instance.output with formatter_name={formatter_name}")

        result = app_instance.output(
            params=processed_answers,
            formatter_name=formatter_name,
            stop_on_exception=True  # Make errors visible
        )

        logger.info(f"app_instance.output completed successfully, result type: {type(result)}")

        # Convert result to JSON-serializable format
        try:
            # Check if it's a Results object or has to_dict
            if hasattr(result, 'to_dict'):
                try:
                    result_dict = result.to_dict()
                    # Check if it's a FileStore with text content (markdown, txt, etc.)
                    if isinstance(result_dict, dict) and 'base64_string' in result_dict:
                        # Check if it's a text file (markdown, txt, etc.) vs binary
                        # Check both 'suffix' field and extract from 'path'
                        suffix = result_dict.get('suffix', '')
                        if not suffix and 'path' in result_dict:
                            suffix = Path(result_dict['path']).suffix

                        if suffix in ['.md', '.txt', '.markdown']:
                            # Decode and return as string for inline display
                            import base64
                            try:
                                text_content = base64.b64decode(result_dict['base64_string']).decode('utf-8')
                                serializable_result = text_content
                            except:
                                # If decode fails, return as file
                                serializable_result = result_dict
                        else:
                            # Binary file - return as-is for download
                            serializable_result = result_dict
                    else:
                        serializable_result = result_dict
                except Exception as e:
                    logger.warning(f"to_dict() failed: {e}, falling back to string")
                    serializable_result = str(result)
            # Check if it's a FileStore dict
            elif isinstance(result, dict) and 'base64_string' in result:
                serializable_result = result
            elif hasattr(result, '__dict__'):
                serializable_result = {k: str(v) for k, v in result.__dict__.items()}
            else:
                serializable_result = str(result)
        except Exception as e:
            logger.warning(f"Serialization failed: {e}")
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
        import traceback
        error_msg = str(e)
        full_traceback = traceback.format_exc()
        logger.error(f"App execution {execution_id} failed: {error_msg}")
        logger.error(f"Full traceback:\n{full_traceback}")

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