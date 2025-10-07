"""FastAPI server for EDSL App backend."""

from datetime import datetime
from typing import Any, Optional, Dict, List
import uuid
import json
import logging
import tempfile
import shutil
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

import sys
from pathlib import Path

# Add parent directories to path to import edsl
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from edsl.app.app import App
from edsl.app.api_payload import build_api_payload
from edsl.app.server.search_utils import rank_apps_bm25

# SQLAlchemy ORM setup
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# SQLAlchemy base and engine
Base = declarative_base()

class AppModel(Base):
    __tablename__ = "apps"
    app_id = Column(String, primary_key=True)
    application_name = Column(Text, nullable=False)  # Python identifier (alias)
    display_name = Column(Text, nullable=False)
    short_description = Column(Text, nullable=True)
    long_description = Column(Text, nullable=True)
    qualified_name = Column(Text, nullable=True)
    application_type = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    app_data = Column(Text, nullable=False)
    parameters = Column(Text, nullable=True)
    available_formatters = Column(Text, nullable=True)
    formatter_metadata = Column(Text, nullable=True)
    default_formatter_name = Column(Text, nullable=True)
    owner = Column(Text, nullable=True)
    source_available = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("owner", "application_name", name="idx_apps_owner_application_name_unique"),
        UniqueConstraint("qualified_name", name="idx_apps_qualified_name_unique"),
    )

class ExecutionModel(Base):
    __tablename__ = "executions"
    execution_id = Column(String, primary_key=True)
    app_id = Column(String, ForeignKey("apps.app_id"), nullable=False)
    status = Column(Text, default="running")
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    application_name: str  # Python identifier
    display_name: str
    short_description: str
    long_description: str
    application_type: str
    created_at: datetime
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    available_formatters: List[str] = Field(default_factory=list)
    formatter_metadata: List[Dict[str, Any]] = Field(default_factory=list)
    default_formatter_name: Optional[str] = None
    owner: Optional[str] = None
    qualified_name: Optional[str] = None  # "owner/application_name" when available

class AppExecutionRequest(BaseModel):
    answers: Dict[str, Any]
    formatter_name: Optional[str] = None
    api_payload: Optional[bool] = True
    return_results: Optional[bool] = None

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

class AppStatsResponse(BaseModel):
    app: AppMetadata
    total_runs: int
    completed_runs: int
    failed_runs: int
    last_run: Optional[str] = None

# Database setup
class DatabaseManager:
    def __init__(self, db_path: str = "edsl_apps.db"):
        self.db_path = db_path
        # SQLite URL for SQLAlchemy
        self.db_url = f"sqlite:///{self.db_path}"
        # create_engine with check_same_thread for FastAPI
        self.engine = create_engine(self.db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.init_database()

    def get_session(self) -> Session:
        return self.SessionLocal()

    def init_database(self):
        """Initialize database by wiping existing file and recreating schema."""
        try:
            db_file = Path(self.db_path)
            if db_file.exists():
                db_file.unlink()
                logger.info("Removed existing database file; recreating schema fresh")
        except Exception as e:
            logger.warning(f"Failed to remove existing database file: {e}")
        # Recreate schema fresh
        Base.metadata.create_all(bind=self.engine)

    def store_app(self, app: App, owner: Optional[str] = None, source_available: Optional[bool] = False, force: bool = False) -> str:
        """Store an app and return its app_id.
        
        Args:
            app: The App instance to store.
            owner: Optional owner string for global uniqueness.
            source_available: If True, the source code is available to future users.
            force: If True, overwrite any existing app with the same owner/alias.
        """
        app_id = str(uuid.uuid4())
        app_dict = app.to_dict()
        app_data = json.dumps(app_dict)

        # Extract simple string fields
        application_name = app.application_name
        display_name = app.display_name
        short_description = app.short_description
        long_description = app.long_description
        
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

        # Extract default formatter name
        default_formatter_name = getattr(app.output_formatters, 'default', None)

        # Extract formatter metadata (output_type)
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

        # Get application_type from the dict to avoid descriptor issues
        application_type = app_dict.get('application_type', 'base')

        # Compute qualified_name if possible
        qualified_name_value = f"{owner}/{application_name}" if owner and application_name else None

        # Enforce global uniqueness of owner/application_name or qualified_name when provided
        session = self.get_session()
        try:
            if qualified_name_value:
                existing = (
                    session.query(AppModel)
                    .filter(AppModel.qualified_name == qualified_name_value)
                    .first()
                )
                if existing:
                    if force:
                        # Delete the existing app and its executions
                        logger.info(f"Force=True: Deleting existing app {existing.app_id} with qualified name '{qualified_name_value}'")
                        session.query(ExecutionModel).filter(ExecutionModel.app_id == existing.app_id).delete()
                        session.delete(existing)
                        session.commit()
                    else:
                        raise ValueError(f"An app with qualified name '{qualified_name_value}' already exists")

            app_row = AppModel(
                app_id=app_id,
                application_name=application_name,
                display_name=display_name,
                short_description=short_description,
                long_description=long_description,
                qualified_name=qualified_name_value,
                application_type=application_type,
                created_at=datetime.utcnow(),
                app_data=app_data,
                parameters=parameters,
                available_formatters=available_formatters,
                formatter_metadata=formatter_metadata,
                default_formatter_name=default_formatter_name,
                owner=owner,
                source_available=bool(source_available),
            )
            session.add(app_row)
            session.commit()
        finally:
            session.close()

        logger.info(f"Stored app {app_id} ({display_name})")
        return app_id

    def get_app(self, app_id: str) -> Optional[App]:
        """Retrieve an app by ID."""
        session = self.get_session()
        try:
            row = session.get(AppModel, app_id)
            if row:
                app_data = json.loads(row.app_data)
                if app_data.get("application_type") == "composite":
                    from edsl.app.composite_app import CompositeApp
                    return CompositeApp.from_dict(app_data)
                return App.from_dict(app_data)
            return None
        finally:
            session.close()

    def get_app_metadata(self, app_id: str) -> Optional[AppMetadata]:
        """Get app metadata without full app data."""
        session = self.get_session()
        try:
            row = session.get(AppModel, app_id)
            if not row:
                return None

            return AppMetadata(
                app_id=row.app_id,
                application_name=row.application_name,
                display_name=row.display_name,
                short_description=row.short_description or "No description provided.",
                long_description=row.long_description or "No description provided.",
                application_type=row.application_type,
                created_at=row.created_at if isinstance(row.created_at, datetime) else datetime.fromisoformat(str(row.created_at)),
                parameters=json.loads(row.parameters) if row.parameters else [],
                available_formatters=json.loads(row.available_formatters) if row.available_formatters else [],
                formatter_metadata=json.loads(row.formatter_metadata) if row.formatter_metadata else [],
                default_formatter_name=row.default_formatter_name,
                owner=row.owner,
                qualified_name=row.qualified_name,
            )
        finally:
            session.close()

    def list_apps(self, search: Optional[str] = None, owner: Optional[str] = None) -> List[AppMetadata]:
        """List all apps, optionally filtered by owner and/or ranked by BM25 for a search query."""
        session = self.get_session()
        try:
            query = session.query(AppModel)
            
            # Filter by owner if provided
            if owner:
                query = query.filter(AppModel.owner == owner)
            
            rows = query.all()

            items_for_ranking = []  # Each item: mapping used by ranker

            for row in rows:
                parameters = json.loads(row.parameters) if row.parameters else []
                available_formatters = json.loads(row.available_formatters) if row.available_formatters else []
                formatter_metadata = json.loads(row.formatter_metadata) if row.formatter_metadata else []

                metadata = AppMetadata(
                    app_id=row.app_id,
                    application_name=row.application_name,
                    display_name=row.display_name,
                    short_description=row.short_description or "No description provided.",
                    long_description=row.long_description or "No description provided.",
                    application_type=row.application_type,
                    created_at=row.created_at if isinstance(row.created_at, datetime) else datetime.fromisoformat(str(row.created_at)),
                    parameters=parameters,
                    available_formatters=available_formatters,
                    formatter_metadata=formatter_metadata,
                    default_formatter_name=row.default_formatter_name,
                    owner=row.owner,
                    qualified_name=row.qualified_name,
                )

                items_for_ranking.append({
                    "meta": metadata,
                    "name": row.display_name,
                    "short_desc": row.short_description or "No description provided.",
                    "long_desc": row.long_description or "No description provided.",
                    "application_type": row.application_type,
                    "parameters": parameters,
                    "available_formatters": available_formatters,
                })

            # If no search provided, preserve created_at DESC order as before
            if not search or not search.strip():
                return sorted([it["meta"] for it in items_for_ranking], key=lambda m: m.created_at, reverse=True)

            # Use search utility for BM25 ranking
            ranked_metas = rank_apps_bm25(items_for_ranking, search)
            return ranked_metas
        finally:
            session.close()

    def store_execution(self, app_id: str, execution_id: str, status: str, result: Any = None, error: str = None):
        """Store execution result."""
        session = self.get_session()
        try:
            row = session.get(ExecutionModel, execution_id)
            if row is None:
                row = ExecutionModel(
                    execution_id=execution_id,
                    app_id=app_id,
                    status=status,
                    result=json.dumps(result) if result is not None else None,
                    error=error,
                    created_at=datetime.utcnow(),
                )
                session.add(row)
            else:
                row.status = status
                row.result = json.dumps(result) if result is not None else None
                row.error = error
            session.commit()
        finally:
            session.close()

    def get_execution(self, execution_id: str) -> Optional[AppExecutionResponse]:
        """Get execution status and result."""
        session = self.get_session()
        try:
            row = session.get(ExecutionModel, execution_id)
            if row:
                result = json.loads(row.result) if row.result else None
                return AppExecutionResponse(
                    execution_id=row.execution_id,
                    status=row.status,
                    result=result,
                    error=row.error,
                )
            return None
        finally:
            session.close()

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
    session = db_manager.get_session()
    try:
        app_count = session.query(AppModel).count()
        exec_count = session.query(ExecutionModel).count()
    finally:
        session.close()

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
        # Capture optional owner from payload and remove it from app dict used to construct the App
        owner = app_data.pop("owner", None)
        if owner is None or str(owner).strip() == "":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner is required to deploy an app")
        # Capture source_available flag; not part of App schema
        source_available = bool(app_data.pop("source_available", False))
        # Capture force flag; not part of App schema
        force = bool(app_data.pop("force", False))

        # Extract and validate required fields
        application_name = app_data.get("application_name")
        display_name = app_data.get("display_name")
        
        if not application_name or not isinstance(application_name, str) or not application_name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="application_name is required and must be a non-empty string (Python identifier)")
        
        if not display_name or not isinstance(display_name, str) or not display_name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="display_name is required and must be a non-empty string")
        
        logger.info(f"Deploy: application_name={application_name}, display_name={display_name}, owner={owner}")

        # Reconstruct the app from the dictionary
        # Check if it's a CompositeApp
        if app_data.get("application_type") == "composite":
            from edsl.app.composite_app import CompositeApp
            app_instance = CompositeApp.from_dict(app_data)
        else:
            app_instance = App.from_dict(app_data)
        app_id = db_manager.store_app(app_instance, owner=owner, source_available=source_available, force=force)

        # Construct qualified name
        qualified_name = f"{owner}/{application_name}" if owner and application_name else None
        
        response_dict = {
            "app_id": app_id, 
            "message": f"App '{display_name}' pushed successfully", 
            "owner": owner,
            "qualified_name": qualified_name
        }
        
        logger.info(f"Returning deployment response: {response_dict}")
        return response_dict
    except ValueError as e:
        logger.error(f"Error pushing app (conflict): {str(e)}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error(f"Error pushing app: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid app data: {str(e)}")

@app.get("/apps", response_model=List[AppMetadata])
async def list_apps(search: Optional[str] = None, owner: Optional[str] = None):
    """List all available apps, optionally filtered by owner and/or ranked by BM25 if 'search' is provided."""
    return db_manager.list_apps(search=search, owner=owner)

@app.get("/apps/resolve")
async def resolve_app_id(qualified_name: str):
    """Resolve a qualified name 'owner/application_name' to an app_id."""
    try:
        if "/" not in qualified_name:
            raise HTTPException(status_code=400, detail="qualified_name must be in the form 'owner/application_name'")
        owner, app_name = qualified_name.split("/", 1)
        owner = owner.strip()
        app_name = app_name.strip()
        if not owner or not app_name:
            raise HTTPException(status_code=400, detail="Both owner and application_name must be non-empty")
        session = db_manager.get_session()
        try:
            # Direct lookup by qualified_name
            app_row = (
                session.query(AppModel)
                .filter(AppModel.qualified_name == qualified_name)
                .first()
            )
            if not app_row:
                # Fallback: match by owner/application_name columns
                app_row = (
                    session.query(AppModel)
                    .filter(AppModel.owner == owner, AppModel.application_name == app_name)
                    .first()
                )
        finally:
            session.close()
        if not app_row:
            raise HTTPException(status_code=404, detail="App not found for qualified name")
        return {"app_id": app_row.app_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving qualified name '{qualified_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve qualified name: {str(e)}")

@app.get("/apps/{app_id}", response_model=AppMetadata)
async def get_app_metadata(app_id: str):
    """Get app metadata and parameters."""
    metadata = db_manager.get_app_metadata(app_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="App not found")
    return metadata

@app.get("/apps/{app_id}/stats", response_model=AppStatsResponse)
async def get_app_stats(app_id: str):
    """Return app metadata and execution statistics for frontend consumption."""
    metadata = db_manager.get_app_metadata(app_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="App not found")
    session = db_manager.get_session()
    try:
        total_runs = session.query(ExecutionModel).filter(ExecutionModel.app_id == app_id).count()
        completed_runs = (
            session.query(ExecutionModel)
            .filter(ExecutionModel.app_id == app_id, ExecutionModel.status == "completed")
            .count()
        )
        failed_runs = (
            session.query(ExecutionModel)
            .filter(ExecutionModel.app_id == app_id, ExecutionModel.status == "failed")
            .count()
        )
        last_run_row = (
            session.query(ExecutionModel.created_at)
            .filter(ExecutionModel.app_id == app_id)
            .order_by(ExecutionModel.created_at.desc())
            .first()
        )
    finally:
        session.close()

    last_run_iso = None
    if last_run_row and last_run_row[0]:
        try:
            last_run_value = last_run_row[0]
            last_run_iso = last_run_value.isoformat() if isinstance(last_run_value, datetime) else datetime.fromisoformat(str(last_run_value)).isoformat()
        except Exception:
            last_run_iso = str(last_run_row[0])

    return AppStatsResponse(
        app=metadata,
        total_runs=total_runs,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        last_run=last_run_iso,
    )

@app.get("/apps/{app_id}/page", response_class=HTMLResponse)
async def get_app_page(app_id: str):
    """Render an HTML page with detailed app metadata and execution statistics."""
    metadata = db_manager.get_app_metadata(app_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="App not found")

    # Compute execution statistics
    session = db_manager.get_session()
    try:
        total_runs = session.query(ExecutionModel).filter(ExecutionModel.app_id == app_id).count()
        completed_runs = (
            session.query(ExecutionModel)
            .filter(ExecutionModel.app_id == app_id, ExecutionModel.status == "completed")
            .count()
        )
        failed_runs = (
            session.query(ExecutionModel)
            .filter(ExecutionModel.app_id == app_id, ExecutionModel.status == "failed")
            .count()
        )
        last_run_row = (
            session.query(ExecutionModel.created_at)
            .filter(ExecutionModel.app_id == app_id)
            .order_by(ExecutionModel.created_at.desc())
            .first()
        )
        last_run = last_run_row[0] if last_run_row else None
    finally:
        session.close()

    # Build HTML content
    app_name = metadata.display_name
    alias = metadata.application_name
    short_desc = metadata.short_description
    long_desc = metadata.long_description
    created_at_str = metadata.created_at.isoformat()
    application_type = metadata.application_type
    default_formatter = metadata.default_formatter_name or "None"

    # Formatters table rows
    formatter_rows = "".join([
        f"<tr><td>{fm.get('name','')}</td><td>{fm.get('output_type','auto')}</td><td>{(fm.get('description') or '')}</td></tr>"
        for fm in (metadata.formatter_metadata or [])
    ])
    if not formatter_rows:
        formatter_rows = "<tr><td colspan='3'>No formatter metadata available</td></tr>"

    # Parameters list
    param_items = "".join([
        f"<li><strong>{p.get('question_name','')}</strong> — {p.get('question_text','')} <em>({p.get('question_type','')})</em></li>"
        for p in (metadata.parameters or [])
    ]) or "<li>No parameters</li>"

    last_run_html = last_run or "Never"

    html = f"""
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>{app_name} — App Details</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, 'Fira Sans', 'Droid Sans', 'Helvetica Neue', Arial, sans-serif; margin: 24px; color: #111; }}
            .container {{ max-width: 960px; margin: 0 auto; }}
            h1 {{ margin-bottom: 0; }}
            .muted {{ color: #666; }}
            .section {{ margin-top: 24px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
            th, td {{ text-align: left; border-bottom: 1px solid #eee; padding: 8px; vertical-align: top; }}
            code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 4px; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-top: 12px; }}
            .card {{ border: 1px solid #eee; border-radius: 8px; padding: 12px; }}
            a {{ color: #0366d6; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
      <div class=\"container\">
        <a href=\"/\">← Back to apps</a>
        <h1>{app_name}</h1>
        <div class=\"muted\">Alias: <code>{alias}</code> · Type: <code>{application_type}</code> · Created: {created_at_str}</div>

        <div class=\"section\">
          <h2>Description</h2>
          <p>{short_desc}</p>
          <details><summary>Full description</summary><p>{long_desc}</p></details>
        </div>

        <div class=\"section\">
          <h2>Execution statistics</h2>
          <div class=\"stats\">
            <div class=\"card\"><div class=\"muted\">Total runs</div><div><strong>{total_runs}</strong></div></div>
            <div class=\"card\"><div class=\"muted\">Completed</div><div><strong>{completed_runs}</strong></div></div>
            <div class=\"card\"><div class=\"muted\">Failed</div><div><strong>{failed_runs}</strong></div></div>
            <div class=\"card\"><div class=\"muted\">Last run</div><div><strong>{last_run_html}</strong></div></div>
          </div>
        </div>

        <div class=\"section\">
          <h2>Output formatters</h2>
          <div class=\"muted\">Default: <code>{default_formatter}</code></div>
          <table>
            <thead><tr><th>Name</th><th>Output type</th><th>Description</th></tr></thead>
            <tbody>
              {formatter_rows}
            </tbody>
          </table>
        </div>

        <div class=\"section\">
          <h2>Parameters</h2>
          <ul>
            {param_items}
          </ul>
        </div>
      </div>
    </body>
    </html>
    """

    return HTMLResponse(content=html)

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
    session = db_manager.get_session()
    try:
        row = session.get(AppModel, app_id)
        if not row:
            raise HTTPException(status_code=404, detail="App not found")
        app_data = json.loads(row.app_data)
        return app_data
    finally:
        session.close()

@app.get("/instantiate_remote_app_client/{app_id}")
async def instantiate_remote_app_client(app_id: str):
    """Return app dict suitable for client instantiation.
    
    If source_available=True, includes jobs_object. Otherwise, jobs_object is omitted.
    """
    app_instance = db_manager.get_app(app_id)
    if not app_instance:
        raise HTTPException(status_code=404, detail="App not found")
    
    # Check if source is available by querying the database
    session = db_manager.get_session()
    try:
        app_row = session.get(AppModel, app_id)
        source_available = app_row.source_available if app_row else False
    finally:
        session.close()
    
    try:
        if source_available:
            # Include full app dict with jobs_object
            return app_instance.to_dict()
        else:
            # Return client-safe dict without jobs_object
            return app_instance.to_dict_for_client()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to serialize app for client: {str(e)}")

@app.delete("/apps/{app_id}")
async def delete_app(app_id: str, owner: Optional[str] = None):
    """Remove an app from the server."""
    try:
        session = db_manager.get_session()
        try:
            app_row = session.get(AppModel, app_id)
            if not app_row:
                raise HTTPException(status_code=404, detail="App not found")

            stored_owner = app_row.owner
            if stored_owner:
                if owner is None:
                    raise HTTPException(status_code=400, detail="Owner is required to delete this app")
                if owner != stored_owner:
                    raise HTTPException(status_code=403, detail="Owner mismatch. Only the owner can delete this app")

            # Delete executions first (no cascade configured here)
            session.query(ExecutionModel).filter(ExecutionModel.app_id == app_id).delete()
            session.delete(app_row)
            session.commit()
        finally:
            session.close()

        logger.info(f"Deleted app {app_id}")
        return {"message": "App deleted successfully"}
    except HTTPException:
        # Re-raise HTTPExceptions so their status codes propagate correctly to the client
        raise
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

    logger.info(f"App instance jobs_object: {str(app_instance.jobs_object)}")
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

        # Generate results and send back with formatters
        formatter_name = request.formatter_name
        logger.info(f"Generating results for app {app_id}")

        # Prepare head attachments and generate results
        head_attachments = app_instance._prepare_head_attachments(processed_answers)
        modified_jobs_object = head_attachments.attach_to_head(app_instance.jobs_object)

        # Force local execution: disable proxy and offloading explicitly
        results = modified_jobs_object.run(
            stop_on_exception=True,
            disable_remote_inference=True,
        )

        logger.info(f"Results generated successfully, type: {type(results)}")

        # Serialize and/or format results depending on flags
        if results is None:
            raise RuntimeError("Jobs.run returned None; no results were produced. Check inputs and configuration.")

        # Determine selected formatter name (robust fallbacks to avoid 'raw_results')
        mapping_keys = list(getattr(app_instance.output_formatters, "mapping", {}).keys())
        non_raw_keys = [k for k in mapping_keys if k != "raw_results"]
        selected_formatter_name = (
            formatter_name
            or getattr(app_instance.output_formatters, "default", None)
            or ("survey_table" if "survey_table" in mapping_keys else None)
            or (non_raw_keys[0] if non_raw_keys else None)
        )

        # Apply formatter server-side for payload/raw paths
        try:
            formatted_output = app_instance._format_output(results, selected_formatter_name, processed_answers)
        except Exception as e:
            logger.error(f"Failed to apply formatter '{formatter_name}': {e}")
            raise

        # Packet used by client-side reconstruction path
        results_packet = {
            "results": results.to_dict(add_edsl_version=True),
            "formatters": app_instance.output_formatters.to_dict(),
            "selected_formatter": selected_formatter_name,
        }

        # Choose response payload according to flags
        if request.return_results:
            # Return raw results + formatters for client-side rendering
            serializable_result = results_packet
        else:
            if request.api_payload:
                # Return standardized API payload with meta + data for frontend rendering
                serializable_result = build_api_payload(
                    formatted_output, selected_formatter_name, app_instance, processed_answers
                )
            else:
                # Return raw formatted output (string/dict/FileStore/etc.)
                serializable_result = formatted_output

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

class PushObjectRequest(BaseModel):
    object_dict: Dict[str, Any]
    visibility: str = "unlisted"  # unlisted, public, private
    alias: Optional[str] = None
    description: Optional[str] = None

@app.post("/push-object")
async def push_edsl_object(request: PushObjectRequest):
    """Push an EDSL object to Coop."""
    try:
        object_dict = request.object_dict

        # Determine object type from the dict (supports both object_type and edsl_class_name)
        object_type = object_dict.get('object_type') or object_dict.get('edsl_class_name')
        if not object_type:
            raise HTTPException(status_code=400, detail="Object dict must contain 'object_type' or 'edsl_class_name' field")

        # Normalize to lowercase with underscores
        object_type = object_type.lower().replace(' ', '_')

        logger.info(f"Pushing {object_type} to Coop with visibility={request.visibility}, alias={request.alias}")

        # Reconstruct the object from dict
        if object_type == "survey":
            from edsl import Survey
            obj = Survey.from_dict(object_dict)
        elif object_type == "scenario_list" or object_type == "scenariolist":
            from edsl import ScenarioList
            obj = ScenarioList.from_dict(object_dict)
        elif object_type == "scenario":
            from edsl import Scenario
            obj = Scenario.from_dict(object_dict)
        elif object_type == "agent_list" or object_type == "agentlist":
            from edsl import AgentList
            obj = AgentList.from_dict(object_dict)
        elif object_type == "agent":
            from edsl import Agent
            obj = Agent.from_dict(object_dict)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported object type: {object_type}")

        # Push to Coop
        result = obj.push(
            visibility=request.visibility,
            description=request.description,
            alias=request.alias
        )

        logger.info(f"Successfully pushed {object_type} to Coop: {result}")

        return {
            "success": True,
            "message": f"{object_type.replace('_', ' ').title()} pushed to Coop successfully",
            "result": result
        }

    except Exception as e:
        import traceback
        error_msg = str(e)
        full_traceback = traceback.format_exc()
        logger.error(f"Failed to push object to Coop: {error_msg}")
        logger.error(f"Full traceback:\n{full_traceback}")
        raise HTTPException(status_code=500, detail=f"Failed to push object: {error_msg}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")