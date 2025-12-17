# server.py
"""
FastAPI server for ScenarioList with push/pull sync capabilities.

Run with: uvicorn backend.server:app --reload
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .sqlite_backend import SQLiteState

# Initialize database
DB_PATH = Path(__file__).parent / "scenarios.db"
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)

# Load schema (only if tables don't exist)
_schema_path = Path(__file__).parent / "schema.sql"
# Check if tables exist
tables_exist = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='scenario_lists'"
).fetchone()
if not tables_exist:
    with open(_schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

app = FastAPI(title="ScenarioList Server", version="0.1.0")

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- Pydantic models ---

class ScenarioCreate(BaseModel):
    payload: Dict[str, Any]

class ListCreate(BaseModel):
    scenarios: List[Dict[str, Any]] = []

class DeltaPayload(BaseModel):
    """Payload for pushing changes to the server."""
    from_version: int
    to_version: int
    scenarios: List[Dict[str, Any]]
    meta_changes: List[Dict[str, Any]]
    overrides: List[Dict[str, Any]]
    history: List[Dict[str, Any]]

class ListInfo(BaseModel):
    list_id: int
    version: int
    length: int

class ListState(BaseModel):
    list_id: int
    version: int
    scenarios: List[Dict[str, Any]]
    meta: Dict[str, Any]


# --- Helper to get backend ---

def get_backend(list_id: int) -> SQLiteState:
    """Get or create a SQLiteState for the given list_id."""
    return SQLiteState(conn, list_id)


# --- Endpoints ---

@app.get("/")
def root():
    """Serve the frontend."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "ScenarioList Server", "version": "0.1.0"}


@app.get("/lists/all", response_model=List[ListInfo])
def get_all_lists():
    """Get info about all lists."""
    rows = conn.execute(
        "SELECT id, current_version FROM scenario_lists ORDER BY id"
    ).fetchall()
    
    result = []
    for row in rows:
        list_id, version = row
        backend = get_backend(list_id)
        result.append(ListInfo(
            list_id=list_id,
            version=version,
            length=backend.get_length()
        ))
    
    return result


@app.post("/lists", response_model=ListInfo)
def create_list(data: ListCreate):
    """Create a new scenario list, optionally with initial data."""
    # Find the next available list_id
    row = conn.execute("SELECT COALESCE(MAX(id), -1) + 1 FROM scenario_lists").fetchone()
    list_id = row[0]
    
    backend = get_backend(list_id)
    
    # Import here to avoid circular imports
    from .ops import sha256_hex, canonical_json
    
    # Add initial scenarios
    for scenario in data.scenarios:
        backend._increment_version()
        position = backend.get_length()
        # Compute digest
        digest = sha256_hex(canonical_json(scenario))
        payload_with_digest = {**scenario, "_digest": digest}
        backend.insert_scenario(position, payload_with_digest)
        backend.append_history("append", (scenario,), {})
    
    conn.commit()
    
    return ListInfo(
        list_id=list_id,
        version=backend.version,
        length=backend.get_length()
    )


@app.get("/lists/{list_id}", response_model=ListState)
def get_list(list_id: int, version: Optional[int] = None):
    """Get the state of a list, optionally at a specific version."""
    backend = get_backend(list_id)
    
    if backend.get_length() == 0 and backend.version == 0:
        # Check if list actually exists
        row = conn.execute("SELECT 1 FROM scenario_lists WHERE id=?", (list_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"List {list_id} not found")
    
    v = version if version is not None else backend.version
    
    return ListState(
        list_id=list_id,
        version=v,
        scenarios=backend.get_all_materialized_scenarios(at_version=v),
        meta=backend.get_meta(at_version=v)
    )


@app.get("/lists/{list_id}/info", response_model=ListInfo)
def get_list_info(list_id: int):
    """Get basic info about a list."""
    backend = get_backend(list_id)
    
    return ListInfo(
        list_id=list_id,
        version=backend.version,
        length=backend.get_length()
    )


@app.get("/lists/{list_id}/history")
def get_list_history(list_id: int, from_version: int = 0):
    """Get the mutation history of a list."""
    backend = get_backend(list_id)
    history = backend.get_history(up_to_version=backend.version)
    
    # Filter to versions >= from_version
    filtered = [
        {"version": v, "method": m, "args": list(a), "kwargs": k}
        for v, m, a, k in history
        if v >= from_version
    ]
    
    return {"list_id": list_id, "history": filtered}


@app.get("/lists/{list_id}/pull")
def pull_changes(list_id: int, from_version: int):
    """
    Pull changes since a specific version.
    
    Client calls this to get all changes they need to apply locally.
    """
    backend = get_backend(list_id)
    
    current_version = backend.version
    if from_version > current_version:
        raise HTTPException(
            status_code=400, 
            detail=f"from_version ({from_version}) is ahead of server ({current_version})"
        )
    
    if from_version == current_version:
        # Already up to date
        return {
            "status": "up_to_date",
            "version": current_version,
            "delta": None
        }
    
    delta = backend.get_delta(from_version, current_version)
    
    return {
        "status": "has_changes",
        "version": current_version,
        "delta": delta
    }


@app.post("/lists/{list_id}/push")
def push_changes(list_id: int, delta: DeltaPayload):
    """
    Push local changes to the server.
    
    Client sends their delta, server applies it if versions match.
    """
    backend = get_backend(list_id)
    
    current_version = backend.version
    
    # Check for conflicts
    if delta.from_version != current_version:
        return {
            "status": "conflict",
            "message": f"Server is at version {current_version}, but delta expects {delta.from_version}",
            "server_version": current_version,
            "hint": "Pull latest changes first, then retry push"
        }
    
    try:
        backend.apply_delta(delta.model_dump())
        conn.commit()
        
        return {
            "status": "success",
            "new_version": backend.version,
            "message": f"Applied {delta.to_version - delta.from_version} version(s)"
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/lists/{list_id}/snapshot")
def create_snapshot(list_id: int):
    """Create a snapshot of the current state for faster future queries."""
    backend = get_backend(list_id)
    backend.save_snapshot()
    conn.commit()
    
    return {
        "status": "success",
        "version": backend.version,
        "message": f"Snapshot created at version {backend.version}"
    }


# --- SQL Explorer ---

class SQLQuery(BaseModel):
    query: str

@app.post("/sql")
def run_sql(data: SQLQuery):
    """Run a read-only SQL query against the database."""
    query = data.query.strip()
    
    # Basic safety check - only allow SELECT and PRAGMA
    query_upper = query.upper()
    if not (query_upper.startswith("SELECT") or query_upper.startswith("PRAGMA")):
        return {"error": "Only SELECT and PRAGMA queries are allowed"}
    
    try:
        cursor = conn.execute(query)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return {"columns": columns, "rows": rows}
    except Exception as e:
        return {"error": str(e)}


# --- Development helpers ---

@app.delete("/lists/{list_id}")
def delete_list(list_id: int):
    """Delete a list and all its data. Use with caution!"""
    conn.execute("DELETE FROM scenarios WHERE list_id=?", (list_id,))
    conn.execute("DELETE FROM scenario_list_meta WHERE list_id=?", (list_id,))
    conn.execute("DELETE FROM scenario_list_overrides WHERE list_id=?", (list_id,))
    conn.execute("DELETE FROM scenario_list_history WHERE list_id=?", (list_id,))
    conn.execute("DELETE FROM scenario_list_snapshots WHERE list_id=?", (list_id,))
    conn.execute("DELETE FROM scenario_lists WHERE id=?", (list_id,))
    conn.commit()
    
    return {"status": "deleted", "list_id": list_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

