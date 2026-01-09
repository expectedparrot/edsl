"""
HTTP Remote server and client for object versioning.

Server: FastAPI application that stores commits, states, and refs.
        Supports multiple repositories with UUIDs and user/alias naming.

Client: HTTPRemote class that implements the Remote protocol.

Usage (Server):
    python -m edsl.versioning.http_remote --port 8765

Usage (Client):
    from edsl.versioning import HTTPRemote, ObjectVersionsServer

    # Connect by alias
    remote = HTTPRemote.from_alias("http://localhost:8765", "john/my-list")

    # Or connect by repo UUID
    remote = HTTPRemote("http://localhost:8765", repo_id="abc123")

    # High-level server interface
    server = ObjectVersionsServer("http://localhost:8765")
    data = server.clone("my-repo")  # Returns dict with entries/meta

    # Apply events via API
    import requests
    requests.post(f"{server.url}/api/repos/{repo_id}/events", json={
        "event_name": "append_row",
        "event_payload": {"row": {"x": 1}},
        "message": "Added row"
    })
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal

from pydantic import BaseModel

# Lazy import for requests to speed up module import time
_requests = None

def _get_requests():
    """Lazily import requests module."""
    global _requests
    if _requests is None:
        import requests as _requests
    return _requests

from .models import Commit, Ref
from .protocols import Remote
from .storage import BaseObjectStore
from .utils import _utcnow

# Import event system from edsl.store
from edsl.store import Store, create_event, apply_event, list_events

# Import versioning modules
from .snapshot_manager import SnapshotManager, SnapshotConfig, get_snapshot_stats
from .event_compaction import EventCompactor, compact_events, analyze_events
from .time_travel import TimeTraveler, get_history, find_commit_at_time
from .validation import EventValidator, validate_event, dry_run
from .metrics import MetricsCollector, StorageAnalyzer, get_collector, timed


# ----------------------------
# Pydantic models for API
# ----------------------------

class CommitModel(BaseModel):
    commit_id: str
    parents: List[str]
    timestamp: str
    message: str
    event_name: str
    event_payload: Dict[str, Any]
    author: str = "unknown"
    state_id: str


class RefModel(BaseModel):
    name: str
    commit_id: str
    kind: str = "branch"


class CreateRepoModel(BaseModel):
    alias: Optional[str] = None  # e.g., "john/my-list"
    description: Optional[str] = None


class ApplyEventModel(BaseModel):
    """Event to apply to a repository."""
    event_name: str  # e.g., "append_row", "update_row", "delete_row"
    event_payload: Dict[str, Any]  # e.g., {"row": {"x": 1}} or {"index": 0}
    message: str = ""  # Commit message
    author: str = "web"
    branch: str = "main"


class EventItem(BaseModel):
    """A single event in a batch."""
    event_name: str
    event_payload: Dict[str, Any]


class BatchCommitModel(BaseModel):
    """Batch of events to commit together."""
    events: List[EventItem]
    message: str = ""
    author: str = "web"
    branch: str = "main"


class RepoInfo(BaseModel):
    repo_id: str
    alias: Optional[str]
    description: Optional[str]
    created_at: str
    refs_count: int
    commits_count: int


class DryRunModel(BaseModel):
    """Events to validate via dry-run."""
    events: List[EventItem]
    branch: str = "main"
    strict: bool = False  # Treat warnings as errors


# ----------------------------
# HTTP Remote Client
# ----------------------------

@dataclass
class HTTPRemote:
    """
    Remote that connects to an HTTP server.
    Implements the Remote protocol for use with GitMixin classes.
    """
    url: str
    repo_id: str
    name: str = "origin"
    timeout: int = 30

    @classmethod
    def from_alias(cls, url: str, alias: str, name: str = "origin", timeout: int = 30) -> "HTTPRemote":
        """
        Create HTTPRemote by resolving an alias (e.g., "john/my-list").
        """
        # Resolve alias to repo_id
        resp = _get_requests().get(
            f"{url.rstrip('/')}/api/aliases/{alias}",
            timeout=timeout
        )
        resp.raise_for_status()
        repo_id = resp.json()["repo_id"]
        return cls(url=url, repo_id=repo_id, name=name, timeout=timeout)

    @classmethod
    def create_repo(cls, url: str, alias: Optional[str] = None,
                    description: Optional[str] = None,
                    name: str = "origin", timeout: int = 30) -> "HTTPRemote":
        """
        Create a new repository on the server.
        Returns an HTTPRemote connected to the new repo.
        """
        resp = _get_requests().post(
            f"{url.rstrip('/')}/api/repos",
            json={"alias": alias, "description": description},
            timeout=timeout
        )
        resp.raise_for_status()
        repo_id = resp.json()["repo_id"]
        return cls(url=url, repo_id=repo_id, name=name, timeout=timeout)

    def _request(self, method: str, path: str, **kwargs):
        """Make HTTP request to server."""
        url = f"{self.url.rstrip('/')}/api/repos/{self.repo_id}{path}"
        kwargs.setdefault('timeout', self.timeout)
        response = _get_requests().request(method, url, **kwargs)
        response.raise_for_status()
        return response

    # --- State operations ---

    def has_state(self, state_id: str) -> bool:
        try:
            resp = self._request('GET', f'/states/{state_id}/exists')
            return resp.json().get('exists', False)
        except _get_requests().HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise

    def get_state_bytes(self, state_id: str) -> bytes:
        resp = self._request('GET', f'/states/{state_id}')
        return resp.content

    def put_state_bytes(self, state_id: str, data: bytes) -> None:
        self._request('PUT', f'/states/{state_id}',
                      data=data,
                      headers={'Content-Type': 'application/octet-stream'})

    # --- Commit operations ---

    def has_commit(self, commit_id: str) -> bool:
        try:
            resp = self._request('GET', f'/commits/{commit_id}/exists')
            return resp.json().get('exists', False)
        except _get_requests().HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise

    def get_commit(self, commit_id: str) -> Commit:
        resp = self._request('GET', f'/commits/{commit_id}')
        data = resp.json()
        return Commit(
            commit_id=data['commit_id'],
            parents=tuple(data['parents']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            message=data['message'],
            event_name=data['event_name'],
            event_payload=data['event_payload'],
            author=data.get('author', 'unknown'),
        )

    def put_commit(self, commit: Commit, state_id: str) -> None:
        data = {
            'commit_id': commit.commit_id,
            'parents': list(commit.parents),
            'timestamp': commit.timestamp.isoformat(),
            'message': commit.message,
            'event_name': commit.event_name,
            'event_payload': commit.event_payload,
            'author': commit.author,
            'state_id': state_id,
        }
        self._request('PUT', f'/commits/{commit.commit_id}', json=data)

    def get_commit_state_id(self, commit_id: str) -> str:
        resp = self._request('GET', f'/commits/{commit_id}/state_id')
        return resp.json()['state_id']

    # --- Ref operations ---

    def has_ref(self, name: str) -> bool:
        try:
            resp = self._request('GET', f'/refs/{name}/exists')
            return resp.json().get('exists', False)
        except _get_requests().HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise

    def get_ref(self, name: str) -> Ref:
        resp = self._request('GET', f'/refs/{name}')
        data = resp.json()
        return Ref(
            name=data['name'],
            commit_id=data['commit_id'],
            kind=data.get('kind', 'branch'),
            updated_at=datetime.fromisoformat(data['updated_at']) if 'updated_at' in data else _utcnow(),
        )

    def list_refs(self) -> List[Ref]:
        resp = self._request('GET', '/refs')
        refs_data = resp.json()
        return [
            Ref(
                name=r['name'],
                commit_id=r['commit_id'],
                kind=r.get('kind', 'branch'),
            )
            for r in refs_data
        ]

    def upsert_ref(self, name: str, commit_id: str, kind: Literal["branch", "tag"] = "branch") -> None:
        data = {
            'name': name,
            'commit_id': commit_id,
            'kind': kind,
        }
        self._request('PUT', f'/refs/{name}', json=data)

    def delete_ref(self, name: str) -> None:
        self._request('DELETE', f'/refs/{name}')


# ----------------------------
# Server Connection Helper
# ----------------------------

@dataclass
class ObjectVersionsServer:
    """
    High-level interface for connecting to an Object Versions server.

    Usage:
        server = ObjectVersionsServer("http://localhost:8766")

        # List available repos
        repos = server.list_repos()

        # Clone by alias or repo_id
        data = server.clone("demo/products")
        data = server.clone("1b1adf09bd32432885b71fe421a5fa10")

        # Create a new repo
        data = server.create("my-alias", initial_data=[{"x": 1}])
    """
    url: str
    timeout: int = 30

    def _resolve_repo(self, repo: str) -> str:
        """Resolve alias or repo_id to repo_id."""
        # First, try as alias
        try:
            resp = _get_requests().get(
                f"{self.url.rstrip('/')}/api/aliases/{repo}",
                timeout=self.timeout
            )
            if resp.status_code == 200:
                return resp.json()["repo_id"]
        except _get_requests().RequestException:
            pass

        # Assume it's a repo_id
        return repo

    def list_repos(self) -> List[Dict[str, Any]]:
        """List all repositories on the server."""
        resp = _get_requests().get(
            f"{self.url.rstrip('/')}/api/repos",
            timeout=self.timeout
        )
        resp.raise_for_status()
        return resp.json()

    def get_remote(self, repo: str, name: str = "origin") -> HTTPRemote:
        """
        Get an HTTPRemote for a specific repo.

        Args:
            repo: Alias (e.g., "demo/products") or repo_id
            name: Remote name (default: "origin")
        """
        repo_id = self._resolve_repo(repo)
        return HTTPRemote(url=self.url, repo_id=repo_id, name=name, timeout=self.timeout)

    def clone(self, repo: str, ref_name: str = "main") -> Dict[str, Any]:
        """
        Clone a repository from the server.

        Args:
            repo: Alias (e.g., "demo/products") or repo_id
            ref_name: Branch to clone (default: "main")

        Returns:
            Dict with 'entries', 'meta', 'remote', 'repo_id', 'branch'
        """
        repo_id = self._resolve_repo(repo)
        remote = self.get_remote(repo)

        # Fetch current data
        resp = _get_requests().get(
            f"{self.url.rstrip('/')}/api/repos/{repo_id}/data",
            params={"branch": ref_name},
            timeout=self.timeout
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "entries": data.get("entries", data.get("rows", [])),
            "meta": data.get("meta", data.get("metadata", {})),
            "remote": remote,
            "repo_id": repo_id,
            "branch": ref_name,
            "commit_id": data.get("commit_id"),
        }

    def create(self, alias: Optional[str] = None, description: Optional[str] = None,
               initial_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Create a new repository on the server.

        Args:
            alias: Optional alias (e.g., "my-data")
            description: Optional description
            initial_data: Optional initial entries

        Returns:
            Dict with 'entries', 'meta', 'remote', 'repo_id'
        """
        remote = HTTPRemote.create_repo(
            url=self.url,
            alias=alias,
            description=description,
            timeout=self.timeout
        )

        # If initial data provided, push it via events
        if initial_data:
            # Create initial commit with all data
            resp = _get_requests().post(
                f"{self.url.rstrip('/')}/api/repos/{remote.repo_id}/events",
                json={
                    "event_name": "replace_all_entries",
                    "event_payload": {"entries": initial_data},
                    "message": "Initial data",
                    "author": "api",
                    "branch": "main"
                },
                timeout=self.timeout
            )
            # If branch doesn't exist yet, we need to initialize first
            if resp.status_code == 400:
                # Initialize with empty state first, then add data
                # For now, just return the remote - initialization handled elsewhere
                pass

        return {
            "entries": initial_data or [],
            "meta": {},
            "remote": remote,
            "repo_id": remote.repo_id,
            "alias": alias,
        }


# ----------------------------
# Repository storage
# ----------------------------

@dataclass
class RepoStorage:
    """Storage for a single repository."""
    repo_id: str
    alias: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = field(default_factory=_utcnow)
    store: BaseObjectStore = field(default_factory=BaseObjectStore)
    commit_to_state: Dict[str, str] = field(default_factory=dict)


# ----------------------------
# FastAPI Server
# ----------------------------

def create_app(db_url: Optional[str] = None):
    """
    Create FastAPI application.

    Args:
        db_url: SQLAlchemy database URL for persistent storage.
                If None, uses in-memory storage.
                Examples:
                - "sqlite:///object_versions.db" (file-based SQLite)
                - "sqlite:///:memory:" (in-memory SQLite)
                - "postgresql://user:pass@localhost/dbname"
    """
    from fastapi import FastAPI, HTTPException, Response, Body, Request
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.middleware.cors import CORSMiddleware
    import asyncio

    app = FastAPI(title="Object Versions Remote Server")

    # Add CORS middleware for SSE from different ports (e.g., Vite dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SSE subscribers: repo_id -> list of asyncio.Queue
    subscribers: Dict[str, List[asyncio.Queue]] = {}

    def notify_subscribers(repo_id: str, event_type: str, data: Dict[str, Any]):
        """Notify all subscribers of a repo about an event."""
        print(f"[SSE] notify_subscribers called: repo={repo_id}, event={event_type}, subscribers={len(subscribers.get(repo_id, []))}")
        if repo_id in subscribers:
            for queue in subscribers[repo_id]:
                try:
                    queue.put_nowait({"event": event_type, "data": data})
                    print(f"[SSE] Queued {event_type} event for repo {repo_id}")
                except asyncio.QueueFull:
                    print(f"[SSE] Queue full, skipping event for repo {repo_id}")
        else:
            print(f"[SSE] No subscribers for repo {repo_id}")

    # Choose storage backend
    if db_url:
        from .db_backend import DatabaseManager
        db = DatabaseManager(db_url)
        use_db = True
    else:
        # In-memory storage (original behavior)
        repos: Dict[str, RepoStorage] = {}
        aliases: Dict[str, str] = {}
        use_db = False

    def get_repo_storage(repo_id: str):
        if use_db:
            repo = db.get_repo(repo_id)
            if not repo:
                raise HTTPException(404, f"Repository '{repo_id}' not found")
            return db.get_repo_storage(repo_id)
        else:
            if repo_id not in repos:
                raise HTTPException(404, f"Repository '{repo_id}' not found")
            # Return the store, not the RepoStorage wrapper
            return repos[repo_id].store

    def get_repo_info(repo_id: str):
        if use_db:
            repo = db.get_repo(repo_id)
            if not repo:
                raise HTTPException(404, f"Repository '{repo_id}' not found")
            storage = db.get_repo_storage(repo_id)
            return {
                "repo_id": repo.repo_id,
                "alias": repo.alias,
                "description": repo.description,
                "created_at": repo.created_at,
                "refs_count": storage.refs_count(),
                "commits_count": storage.commits_count(),
            }
        else:
            if repo_id not in repos:
                raise HTTPException(404, f"Repository '{repo_id}' not found")
            r = repos[repo_id]
            return {
                "repo_id": r.repo_id,
                "alias": r.alias,
                "description": r.description,
                "created_at": r.created_at,
                "refs_count": len(r.store._refs),
                "commits_count": len(r.store._commits),
            }

    # --- Repository management ---

    @app.get("/api/repos")
    def list_repos_endpoint():
        if use_db:
            repos_list = db.list_repos()
            result = []
            for r in repos_list:
                storage = db.get_repo_storage(r.repo_id)
                result.append({
                    "repo_id": r.repo_id,
                    "alias": r.alias,
                    "description": r.description,
                    "created_at": r.created_at.isoformat(),
                    "refs_count": storage.refs_count(),
                    "commits_count": storage.commits_count(),
                })
            return result
        else:
            return [
                {
                    "repo_id": r.repo_id,
                    "alias": r.alias,
                    "description": r.description,
                    "created_at": r.created_at.isoformat(),
                    "refs_count": len(r.store._refs),
                    "commits_count": len(r.store._commits),
                }
                for r in repos.values()
            ]

    def initialize_repo_with_empty_state(storage, repo_id: str):
        """Initialize a repository with an empty state and main branch."""
        import hashlib

        # Create empty initial state
        initial_store = Store(entries=[], meta={})
        state_bytes = serialize_store(initial_store)
        state_id = hashlib.sha256(state_bytes).hexdigest()[:16]

        # Create initial commit
        now = _utcnow()
        commit_data = {
            "parents": [],
            "timestamp": now.isoformat(),
            "message": "Initial commit",
            "event_name": "init",
            "event_payload": {},
            "author": "system",
        }
        commit_str = json.dumps(commit_data, sort_keys=True)
        commit_id = hashlib.sha256(commit_str.encode()).hexdigest()[:16]

        commit = Commit(
            commit_id=commit_id,
            parents=(),
            timestamp=now,
            message="Initial commit",
            event_name="init",
            event_payload={},
            author="system",
        )

        # Store state, commit, and create main branch
        storage.put_state_bytes(state_id, state_bytes)
        storage.put_commit(commit, state_id)
        storage.upsert_ref("main", commit_id, "branch")

        return commit_id

    @app.post("/api/repos")
    def create_repo_endpoint(payload: CreateRepoModel = Body(...)):
        repo_id = uuid.uuid4().hex
        if use_db:
            db.create_repo(repo_id, alias=payload.alias, description=payload.description)
            repo = db.get_repo(repo_id)
            storage = db.get_repo_storage(repo_id)
            # Initialize with empty state and main branch
            commit_id = initialize_repo_with_empty_state(storage, repo_id)
            return {
                "repo_id": repo_id,
                "alias": payload.alias,
                "created_at": repo.created_at.isoformat(),
                "initial_commit": commit_id,
            }
        else:
            repo = RepoStorage(
                repo_id=repo_id,
                alias=payload.alias,
                description=payload.description,
            )
            repos[repo_id] = repo
            if payload.alias:
                aliases[payload.alias] = repo_id
            # Initialize with empty state and main branch
            commit_id = initialize_repo_with_empty_state(repo.store, repo_id)
            return {
                "repo_id": repo_id,
                "alias": payload.alias,
                "created_at": repo.created_at.isoformat(),
                "initial_commit": commit_id,
            }

    @app.get("/api/repos/{repo_id}")
    def get_repo_info_endpoint(repo_id: str):
        info = get_repo_info(repo_id)
        info["created_at"] = info["created_at"].isoformat() if hasattr(info["created_at"], "isoformat") else info["created_at"]
        return info

    @app.put("/api/repos/{repo_id}/alias")
    def set_alias_endpoint(repo_id: str, alias: str):
        if use_db:
            db.set_alias(repo_id, alias)
        else:
            repo = repos.get(repo_id)
            if not repo:
                raise HTTPException(404, f"Repository '{repo_id}' not found")
            if repo.alias and repo.alias in aliases:
                del aliases[repo.alias]
            repo.alias = alias
            aliases[alias] = repo_id
        return {"status": "ok", "alias": alias}

    @app.get("/api/aliases/{alias:path}")
    def resolve_alias_endpoint(alias: str):
        if use_db:
            repo = db.get_repo_by_alias(alias)
            if not repo:
                raise HTTPException(404, f"Alias '{alias}' not found")
            return {"repo_id": repo.repo_id, "alias": alias}
        else:
            if alias not in aliases:
                raise HTTPException(404, f"Alias '{alias}' not found")
            return {"repo_id": aliases[alias], "alias": alias}

    # --- State endpoints ---

    @app.get("/api/repos/{repo_id}/states/{state_id}/exists")
    def state_exists_endpoint(repo_id: str, state_id: str):
        storage = get_repo_storage(repo_id)
        return {"exists": storage.has_state(state_id)}

    @app.get("/api/repos/{repo_id}/states/{state_id}")
    def get_state_endpoint(repo_id: str, state_id: str):
        storage = get_repo_storage(repo_id)
        if not storage.has_state(state_id):
            raise HTTPException(404, "State not found")
        return Response(
            content=storage.get_state_bytes(state_id),
            media_type="application/octet-stream"
        )

    @app.put("/api/repos/{repo_id}/states/{state_id}")
    async def put_state_endpoint(repo_id: str, state_id: str, body: bytes = Body(...)):
        storage = get_repo_storage(repo_id)
        storage.put_state_bytes(state_id, body)
        return {"status": "ok", "size": len(body)}

    # --- Commit endpoints ---

    @app.get("/api/repos/{repo_id}/commits/{commit_id}/exists")
    def commit_exists_endpoint(repo_id: str, commit_id: str):
        storage = get_repo_storage(repo_id)
        return {"exists": storage.has_commit(commit_id)}

    @app.get("/api/repos/{repo_id}/commits/{commit_id}")
    def get_commit_endpoint(repo_id: str, commit_id: str):
        storage = get_repo_storage(repo_id)
        if not storage.has_commit(commit_id):
            raise HTTPException(404, "Commit not found")
        commit = storage.get_commit(commit_id)
        return {
            "commit_id": commit.commit_id,
            "parents": list(commit.parents),
            "timestamp": commit.timestamp.isoformat(),
            "message": commit.message,
            "event_name": commit.event_name,
            "event_payload": commit.event_payload,
            "author": commit.author,
        }

    @app.get("/api/repos/{repo_id}/commits/{commit_id}/state_id")
    def get_commit_state_id_endpoint(repo_id: str, commit_id: str):
        storage = get_repo_storage(repo_id)
        try:
            state_id = storage.get_commit_state_id(commit_id)
            return {"state_id": state_id}
        except KeyError:
            raise HTTPException(404, "Commit not found")

    @app.put("/api/repos/{repo_id}/commits/{commit_id}")
    def put_commit_endpoint(repo_id: str, commit_id: str, payload: CommitModel = Body(...)):
        storage = get_repo_storage(repo_id)
        commit = Commit(
            commit_id=payload.commit_id,
            parents=tuple(payload.parents),
            timestamp=datetime.fromisoformat(payload.timestamp),
            message=payload.message,
            event_name=payload.event_name,
            event_payload=payload.event_payload,
            author=payload.author,
        )
        storage.put_commit(commit, payload.state_id)
        return {"status": "ok"}

    # --- Ref endpoints ---

    @app.get("/api/repos/{repo_id}/refs/{name}/exists")
    def ref_exists_endpoint(repo_id: str, name: str):
        storage = get_repo_storage(repo_id)
        return {"exists": storage.has_ref(name)}

    @app.get("/api/repos/{repo_id}/refs/{name}")
    def get_ref_endpoint(repo_id: str, name: str):
        storage = get_repo_storage(repo_id)
        if not storage.has_ref(name):
            raise HTTPException(404, "Ref not found")
        ref = storage.get_ref(name)
        return {
            "name": ref.name,
            "commit_id": ref.commit_id,
            "kind": ref.kind,
            "updated_at": ref.updated_at.isoformat(),
        }

    @app.get("/api/repos/{repo_id}/refs")
    def list_refs_endpoint(repo_id: str):
        storage = get_repo_storage(repo_id)
        refs = storage.list_refs()
        return [
            {
                "name": r.name,
                "commit_id": r.commit_id,
                "kind": r.kind,
            }
            for r in refs
        ]

    @app.put("/api/repos/{repo_id}/refs/{name}")
    def upsert_ref_endpoint(repo_id: str, name: str, payload: RefModel = Body(...)):
        storage = get_repo_storage(repo_id)
        storage.upsert_ref(payload.name, payload.commit_id, payload.kind)

        # Notify SSE subscribers (this is how Python clients push updates)
        notify_subscribers(repo_id, "ref_update", {
            "ref_name": payload.name,
            "commit_id": payload.commit_id,
            "kind": payload.kind,
        })

        return {"status": "ok"}

    @app.delete("/api/repos/{repo_id}/refs/{name}")
    def delete_ref_endpoint(repo_id: str, name: str):
        storage = get_repo_storage(repo_id)
        if not storage.has_ref(name):
            raise HTTPException(404, "Ref not found")
        storage.delete_ref(name)
        return {"status": "ok"}

    # --- Status endpoint ---

    @app.get("/api/status")
    def get_status_endpoint():
        if use_db:
            return db.get_stats()
        else:
            total_refs = sum(len(r.store._refs) for r in repos.values())
            total_commits = sum(len(r.store._commits) for r in repos.values())
            total_states = sum(len(r.store._states) for r in repos.values())
            return {
                "repos_count": len(repos),
                "total_refs": total_refs,
                "total_commits": total_commits,
                "total_states": total_states,
            }

    # --- SSE endpoint for real-time updates ---

    @app.get("/api/repos/{repo_id}/events/stream")
    async def events_stream(repo_id: str):
        """
        Server-Sent Events stream for real-time updates.
        Clients receive notifications when commits happen.
        """
        # Verify repo exists
        get_repo_storage(repo_id)

        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        # Register subscriber
        if repo_id not in subscribers:
            subscribers[repo_id] = []
        subscribers[repo_id].append(queue)
        print(f"[SSE] Client connected to repo {repo_id}, total subscribers: {len(subscribers[repo_id])}")

        async def event_generator():
            try:
                # Send initial connected event
                yield f"event: connected\ndata: {json.dumps({'repo_id': repo_id})}\n\n"
                print(f"[SSE] Sent connected event for repo {repo_id}")

                while True:
                    try:
                        # Wait for events with timeout (sends keepalive on timeout)
                        msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                        event_str = f"event: {msg['event']}\ndata: {json.dumps(msg['data'])}\n\n"
                        print(f"[SSE] Sending event to repo {repo_id}: {msg['event']}")
                        yield event_str
                    except asyncio.TimeoutError:
                        # Send keepalive comment (keeps connection alive)
                        yield ": keepalive\n\n"
            except asyncio.CancelledError:
                print(f"[SSE] Client disconnected from repo {repo_id}")
            except GeneratorExit:
                print(f"[SSE] Generator exited for repo {repo_id}")
            except Exception as e:
                print(f"[SSE] Error in event generator for repo {repo_id}: {e}")
            finally:
                # Unregister subscriber on disconnect
                print(f"[SSE] Cleaning up subscriber for repo {repo_id}")
                if repo_id in subscribers and queue in subscribers[repo_id]:
                    subscribers[repo_id].remove(queue)
                    if not subscribers[repo_id]:
                        del subscribers[repo_id]

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering if present
            }
        )

    # --- Helper function to load state from either format ---

    def load_store_from_state(state_bytes: bytes) -> Store:
        """
        Load a Store from state bytes, supporting both old and new formats.

        Old format (ListStore): [{"rows": [...], "metadata": {...}}]
        New format (Store): [{"entries": [...], "meta": {...}}]
        """
        state_list = json.loads(state_bytes.decode('utf-8'))
        state_dict = state_list[0] if isinstance(state_list, list) else state_list

        # Support both formats
        if "entries" in state_dict:
            # New format
            return Store(
                entries=list(state_dict.get("entries", [])),
                meta=dict(state_dict.get("meta", {}))
            )
        else:
            # Old ListStore format - convert
            return Store(
                entries=list(state_dict.get("rows", [])),
                meta=dict(state_dict.get("metadata", {}))
            )

    def serialize_store(store: Store) -> bytes:
        """Serialize a Store to bytes in the standard format."""
        # Use new format with entries/meta
        state_dict = {"entries": store.entries, "meta": store.meta}
        state_list = [state_dict]
        return json.dumps(state_list, sort_keys=True).encode('utf-8')

    def materialize_at_commit(storage, commit_id: str) -> Store:
        """
        Materialize the state at a specific commit by replaying events.

        Finds the nearest ancestor with a snapshot and replays events forward.
        Handles batch events by unpacking and applying sub-events.

        Args:
            storage: The storage backend
            commit_id: Target commit to materialize

        Returns:
            Store with materialized state

        Raises:
            HTTPException: If no snapshot found in ancestry
        """
        snapshot_commit_id, state_id, events_to_replay = storage.find_nearest_snapshot(commit_id)

        if state_id is None:
            raise HTTPException(500, f"No snapshot found in ancestry of commit {commit_id}")

        # Load the snapshot
        state_bytes = storage.get_state_bytes(state_id)
        store = load_store_from_state(state_bytes)

        # Replay events to reach target commit
        for event_name, event_payload in events_to_replay:
            try:
                if event_name == "batch":
                    # Unpack batch events and apply each sub-event
                    sub_events = event_payload.get("events", [])
                    for sub in sub_events:
                        sub_event = create_event(sub["event_name"], sub["event_payload"])
                        apply_event(sub_event, store)
                else:
                    event = create_event(event_name, event_payload)
                    apply_event(event, store)
            except ValueError as e:
                raise HTTPException(500, f"Error replaying event '{event_name}': {e}")

        return store

    # --- List available events endpoint ---

    @app.get("/api/events")
    def list_events_endpoint():
        """List all available events with their parameter schemas."""
        return list_events()

    # --- Apply Event endpoint (server-side mutation) ---

    @app.post("/api/repos/{repo_id}/events")
    def apply_event_endpoint(repo_id: str, payload: ApplyEventModel = Body(...)):
        """
        Apply an event to the repository, creating a new commit.

        Events are stored without creating a state snapshot (event-sourcing).
        State is materialized on-demand by replaying events from the nearest snapshot.
        Use POST /api/repos/{repo_id}/snapshot to create a snapshot.

        Uses the dynamic event registry from edsl.store. Events are specified
        by snake_case name (e.g., 'append_row', 'remove_rows', 'rename_fields')
        and their payloads are passed directly to the event constructor.

        See GET /api/events for a list of available events and their schemas.
        """
        import hashlib

        storage = get_repo_storage(repo_id)
        branch = payload.branch

        # Get current HEAD for the branch
        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        head_commit_id = ref.commit_id

        # Validate the event can be created (don't need to apply it for storage)
        event_name = payload.event_name
        event_payload = payload.event_payload

        try:
            # Just validate the event - don't need full materialization
            event = create_event(event_name, event_payload)
        except ValueError as e:
            raise HTTPException(400, str(e))

        # Create commit (event-only, no state snapshot)
        now = _utcnow()
        commit_data = {
            "parents": [head_commit_id],
            "timestamp": now.isoformat(),
            "message": payload.message or f"{event_name}",
            "event_name": event_name,
            "event_payload": event_payload,
            "author": payload.author,
        }
        commit_str = json.dumps(commit_data, sort_keys=True)
        new_commit_id = hashlib.sha256(commit_str.encode()).hexdigest()[:16]

        commit = Commit(
            commit_id=new_commit_id,
            parents=(head_commit_id,),
            timestamp=now,
            message=payload.message or f"{event_name}",
            event_name=event_name,
            event_payload=event_payload,
            author=payload.author,
        )

        # Store commit WITHOUT state snapshot (event-only)
        storage.put_commit(commit)  # No state_id
        storage.upsert_ref(branch, new_commit_id, "branch")

        # Notify SSE subscribers
        notify_subscribers(repo_id, "commit", {
            "commit_id": new_commit_id,
            "branch": branch,
            "message": payload.message or event_name,
            "event_name": event_name,
        })

        return {
            "status": "ok",
            "commit_id": new_commit_id,
            "snapshot": False,  # No snapshot created
        }

    # --- Batch commit endpoint (multiple events -> one commit) ---

    @app.post("/api/repos/{repo_id}/batch")
    def batch_commit_endpoint(repo_id: str, payload: BatchCommitModel = Body(...)):
        """
        Apply multiple events as a single commit.

        Events are stored without creating a state snapshot (event-sourcing).
        The batch is stored as a single commit with event_name="batch".
        State is materialized on-demand by replaying events.

        See GET /api/events for a list of available events and their schemas.
        """
        import hashlib

        if not payload.events:
            raise HTTPException(400, "No events to commit")

        storage = get_repo_storage(repo_id)
        branch = payload.branch

        # Get current HEAD for the branch
        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        head_commit_id = ref.commit_id

        # Validate all events can be created
        validated_events = []
        for ev in payload.events:
            event_name = ev.event_name
            event_payload = ev.event_payload

            try:
                # Validate by creating the event
                event = create_event(event_name, event_payload)
                validated_events.append({"event_name": event_name, "event_payload": event_payload})
            except ValueError as e:
                raise HTTPException(400, f"Error validating event '{event_name}': {e}")

        # Create commit with batch event (no state snapshot)
        now = _utcnow()
        commit_data = {
            "parents": [head_commit_id],
            "timestamp": now.isoformat(),
            "message": payload.message or f"batch ({len(validated_events)} events)",
            "event_name": "batch",
            "event_payload": {"events": validated_events},
            "author": payload.author,
        }
        commit_str = json.dumps(commit_data, sort_keys=True)
        new_commit_id = hashlib.sha256(commit_str.encode()).hexdigest()[:16]

        commit = Commit(
            commit_id=new_commit_id,
            parents=(head_commit_id,),
            timestamp=now,
            message=payload.message or f"batch ({len(validated_events)} events)",
            event_name="batch",
            event_payload={"events": validated_events},
            author=payload.author,
        )

        # Store commit WITHOUT state snapshot (event-only)
        storage.put_commit(commit)  # No state_id
        storage.upsert_ref(branch, new_commit_id, "branch")

        # Notify SSE subscribers
        notify_subscribers(repo_id, "commit", {
            "commit_id": new_commit_id,
            "branch": branch,
            "message": payload.message or f"batch ({len(validated_events)} events)",
            "events_applied": len(validated_events),
        })

        return {
            "status": "ok",
            "commit_id": new_commit_id,
            "snapshot": False,  # No snapshot created
            "events_applied": len(validated_events),
        }

    # --- Create snapshot endpoint ---

    @app.post("/api/repos/{repo_id}/snapshot")
    def create_snapshot_endpoint(repo_id: str, branch: str = "main"):
        """
        Create a state snapshot at the current HEAD of a branch.

        Materializes the current state by replaying events from the nearest
        existing snapshot, then stores the result as a new snapshot.

        Use this periodically to improve read performance by reducing
        the number of events that need to be replayed.
        """
        import hashlib

        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        commit_id = ref.commit_id

        # Check if snapshot already exists
        if storage.has_snapshot(commit_id):
            return {
                "status": "exists",
                "commit_id": commit_id,
                "message": "Snapshot already exists for this commit",
            }

        # Materialize state at this commit
        store = materialize_at_commit(storage, commit_id)

        # Store the snapshot
        state_bytes = serialize_store(store)
        state_id = hashlib.sha256(state_bytes).hexdigest()[:16]
        storage.put_state_bytes(state_id, state_bytes)

        # Link snapshot to commit
        storage._commit_to_state[commit_id] = state_id

        return {
            "status": "ok",
            "commit_id": commit_id,
            "state_id": state_id,
            "entries_count": len(store.entries),
        }

    # --- Snapshot statistics endpoint ---

    @app.get("/api/repos/{repo_id}/snapshot/stats")
    def get_snapshot_stats_endpoint(repo_id: str, branch: str = "main"):
        """
        Get snapshot statistics for the repository.

        Returns information about snapshot coverage, replay efficiency,
        and recommendations for creating new snapshots.
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        stats = get_snapshot_stats(storage, ref.commit_id)

        return {
            "total_commits": stats.total_commits,
            "total_snapshots": stats.total_snapshots,
            "snapshot_coverage": round(stats.snapshot_coverage * 100, 2),
            "max_events_to_replay": stats.max_events_to_replay,
            "avg_events_to_replay": round(stats.avg_events_to_replay, 2),
            "events_since_last_snapshot": stats.events_since_last_snapshot,
            "snapshot_commits": stats.snapshot_commits[:10],  # Limit to 10
            "recommendations": _get_snapshot_recommendations(stats),
        }

    def _get_snapshot_recommendations(stats):
        """Generate recommendations based on snapshot stats."""
        recommendations = []
        if stats.events_since_last_snapshot > 50:
            recommendations.append("Create a snapshot - many events since last snapshot")
        if stats.snapshot_coverage < 0.02:
            recommendations.append("Low snapshot coverage - consider creating more snapshots")
        if stats.max_events_to_replay > 100:
            recommendations.append("High max replay count - snapshots would improve read performance")
        return recommendations

    # --- Snapshot garbage collection endpoint ---

    @app.post("/api/repos/{repo_id}/snapshot/gc")
    def gc_snapshots_endpoint(repo_id: str, branch: str = "main", keep: int = 10):
        """
        Garbage collect old snapshots, keeping only the most recent N.

        Always keeps:
        - The initial commit snapshot (required for replay)
        - The most recent N snapshots
        """
        from .snapshot_manager import gc_snapshots as gc_fn

        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        result = gc_fn(storage, ref.commit_id, keep_count=keep)

        return result

    # --- Event compaction analysis endpoint ---

    @app.get("/api/repos/{repo_id}/events/compact/analyze")
    def analyze_compaction_endpoint(repo_id: str, branch: str = "main"):
        """
        Analyze potential compaction savings for the event log.

        Shows how many events could be reduced through compaction
        without actually performing the compaction.
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)

        # Collect all events in history
        events = []
        current = ref.commit_id
        while current:
            if not storage.has_commit(current):
                break
            commit = storage.get_commit(current)
            if commit.event_name != "init":
                if commit.event_name == "batch":
                    for sub in commit.event_payload.get("events", []):
                        events.append((sub["event_name"], sub["event_payload"]))
                else:
                    events.append((commit.event_name, commit.event_payload))
            if not commit.parents:
                break
            current = commit.parents[0]

        events.reverse()  # Oldest first
        analysis = analyze_events(events)

        return analysis

    # --- Time travel / history endpoints ---

    @app.get("/api/repos/{repo_id}/history/at")
    def get_state_at_time_endpoint(
        repo_id: str,
        timestamp: str,
        branch: str = "main"
    ):
        """
        Get the state at a specific point in time.

        Args:
            timestamp: ISO format timestamp (e.g., "2024-01-15T10:30:00")
        """
        from datetime import datetime as dt

        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        try:
            target_time = dt.fromisoformat(timestamp)
        except ValueError:
            raise HTTPException(400, f"Invalid timestamp format: {timestamp}")

        ref = storage.get_ref(branch)
        commit_id = find_commit_at_time(storage, ref.commit_id, target_time)

        if not commit_id:
            raise HTTPException(404, f"No commit found at or before {timestamp}")

        # Materialize state at that commit
        store = materialize_at_commit(storage, commit_id)
        commit = storage.get_commit(commit_id)

        return {
            "commit_id": commit_id,
            "timestamp": commit.timestamp.isoformat(),
            "message": commit.message,
            "entries": store.entries,
            "meta": store.meta,
            "entries_count": len(store.entries),
        }

    @app.get("/api/repos/{repo_id}/history/search")
    def search_history_endpoint(
        repo_id: str,
        query: str,
        branch: str = "main",
        limit: int = 20
    ):
        """
        Search commit history by message.

        Args:
            query: Search pattern (case-insensitive substring match)
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        traveler = TimeTraveler(storage)
        commit_ids = traveler.find_commit_by_message(ref.commit_id, query)[:limit]

        results = []
        for cid in commit_ids:
            commit = storage.get_commit(cid)
            results.append({
                "commit_id": cid,
                "message": commit.message,
                "event_name": commit.event_name,
                "author": commit.author,
                "timestamp": commit.timestamp.isoformat(),
            })

        return {"query": query, "results": results, "count": len(results)}

    @app.get("/api/repos/{repo_id}/history/diff")
    def diff_commits_endpoint(
        repo_id: str,
        from_commit: str,
        to_commit: str
    ):
        """
        Get the diff between two commits.

        Shows entries added, removed, modified, and field changes.
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_commit(from_commit):
            raise HTTPException(404, f"Commit '{from_commit}' not found")
        if not storage.has_commit(to_commit):
            raise HTTPException(404, f"Commit '{to_commit}' not found")

        # Materialize both states
        state1 = materialize_at_commit(storage, from_commit)
        state2 = materialize_at_commit(storage, to_commit)

        traveler = TimeTraveler(storage)
        diff = traveler.diff_states(
            {"entries": state1.entries, "meta": state1.meta},
            {"entries": state2.entries, "meta": state2.meta},
            from_commit, to_commit
        )

        return {
            "from_commit": diff.from_commit,
            "to_commit": diff.to_commit,
            "entries_added": diff.entries_added,
            "entries_removed": diff.entries_removed,
            "entries_modified": diff.entries_modified,
            "fields_added": diff.fields_added,
            "fields_removed": diff.fields_removed,
            "meta_changes": {k: {"old": v[0], "new": v[1]} for k, v in diff.meta_changes.items()},
        }

    # --- Validation / dry-run endpoint ---

    @app.post("/api/repos/{repo_id}/events/validate")
    def validate_events_endpoint(repo_id: str, payload: DryRunModel = Body(...)):
        """
        Validate events without applying them (dry-run).

        Returns validation results for each event, showing any errors
        or warnings that would occur if the events were applied.
        """
        storage = get_repo_storage(repo_id)
        branch = payload.branch

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)

        # Materialize current state
        store = materialize_at_commit(storage, ref.commit_id)
        current_state = {"entries": store.entries, "meta": store.meta}

        # Define apply function for dry-run
        def apply_fn(event_name, event_payload, state):
            import copy
            temp_store = Store(
                entries=copy.deepcopy(state.get("entries", [])),
                meta=copy.deepcopy(state.get("meta", {}))
            )
            event = create_event(event_name, event_payload)
            apply_event(event, temp_store)
            return {"entries": temp_store.entries, "meta": temp_store.meta}

        # Run dry-run
        events = [(e.event_name, e.event_payload) for e in payload.events]
        validator = EventValidator(strict=payload.strict)
        result = validator.dry_run(events, current_state, apply_fn)

        # Format results
        validation_results = []
        for event_name, event_payload, vr in result.validation_results:
            validation_results.append({
                "event_name": event_name,
                "valid": vr.valid,
                "issues": [
                    {
                        "severity": i.severity.value,
                        "code": i.code,
                        "message": i.message,
                        "field": i.field,
                    }
                    for i in vr.issues
                ]
            })

        return {
            "success": result.success,
            "summary": result.summary,
            "validation_results": validation_results,
            "final_state_preview": {
                "entries_count": len(result.final_state.get("entries", [])) if result.final_state else None,
            } if result.success else None,
        }

    # --- Metrics endpoint ---

    @app.get("/api/repos/{repo_id}/metrics")
    def get_repo_metrics_endpoint(repo_id: str, branch: str = "main"):
        """
        Get metrics for a repository.

        Returns storage metrics, health status, and recommendations.
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)

        # Get storage metrics
        analyzer = StorageAnalyzer(storage)
        storage_metrics = analyzer.get_storage_metrics(ref.commit_id)
        health = analyzer.check_health(ref.commit_id)

        return {
            "storage": {
                "total_commits": storage_metrics.total_commits,
                "total_snapshots": storage_metrics.total_snapshots,
                "total_events": storage_metrics.total_events,
                "snapshot_coverage": round(storage_metrics.snapshot_coverage * 100, 2),
                "avg_snapshot_size_bytes": round(storage_metrics.avg_snapshot_size_bytes),
                "total_storage_bytes": storage_metrics.total_storage_bytes,
            },
            "health": {
                "healthy": health.healthy,
                "issues": health.issues,
                "recommendations": health.recommendations,
                "scores": health.scores,
            },
        }

    @app.get("/api/metrics")
    def get_global_metrics_endpoint():
        """
        Get global server metrics.

        Returns performance metrics, counters, and timing information.
        """
        from .metrics import get_metrics_summary
        return get_metrics_summary()

    # --- Get state at specific commit ---

    @app.get("/api/repos/{repo_id}/commits/{commit_id}/data")
    def get_commit_data_endpoint(repo_id: str, commit_id: str):
        """
        Get the data (entries) at a specific commit.

        Materializes state by replaying events from the nearest snapshot.
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_commit(commit_id):
            raise HTTPException(404, f"Commit '{commit_id}' not found")

        # Materialize state at this commit (replays events if needed)
        store = materialize_at_commit(storage, commit_id)
        commit = storage.get_commit(commit_id)

        # Check how many events were replayed
        snapshot_id, _, events = storage.find_nearest_snapshot(commit_id)

        return {
            "entries": store.entries,
            "meta": store.meta,
            # Backward compatibility aliases
            "rows": store.entries,
            "metadata": store.meta,
            "commit_id": commit_id,
            "message": commit.message,
            "author": commit.author,
            "timestamp": commit.timestamp.isoformat(),
            "entries_count": len(store.entries),
            "events_replayed": len(events),
        }

    # --- Get commit history ---

    @app.get("/api/repos/{repo_id}/history")
    def get_history_endpoint(repo_id: str, branch: str = "main", limit: int = 50):
        """Get commit history for a branch."""
        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        commits = []
        current = ref.commit_id

        for _ in range(limit):
            if not storage.has_commit(current):
                break
            commit = storage.get_commit(current)
            commits.append({
                "commit_id": commit.commit_id,
                "message": commit.message,
                "event_name": commit.event_name,
                "author": commit.author,
                "timestamp": commit.timestamp.isoformat(),
                "parents": list(commit.parents),
            })
            if not commit.parents:
                break
            current = commit.parents[0]

        return {"commits": commits, "branch": branch}

    # --- Get current data endpoint ---

    @app.get("/api/repos/{repo_id}/data")
    def get_data_endpoint(repo_id: str, branch: str = "main"):
        """
        Get the current data (entries) for a repository.

        Materializes state by replaying events from the nearest snapshot.
        """
        storage = get_repo_storage(repo_id)

        if not storage.has_ref(branch):
            raise HTTPException(400, f"Branch '{branch}' does not exist")

        ref = storage.get_ref(branch)
        commit_id = ref.commit_id

        # Materialize state at HEAD (replays events if needed)
        store = materialize_at_commit(storage, commit_id)

        # Check how many events were replayed
        snapshot_id, _, events = storage.find_nearest_snapshot(commit_id)

        return {
            "entries": store.entries,
            "meta": store.meta,
            # Backward compatibility aliases
            "rows": store.entries,
            "metadata": store.meta,
            "branch": branch,
            "commit_id": commit_id,
            "entries_count": len(store.entries),
            "events_replayed": len(events),
        }

    # --- Web UI ---

    @app.get("/", response_class=HTMLResponse)
    def web_ui():
        if use_db:
            repos_list = db.list_repos()
            stats = db.get_stats()
            recent_commits_data = db.get_recent_commits(15)
        else:
            repos_list = list(repos.values())
            stats = {
                "repos_count": len(repos),
                "total_refs": sum(len(r.store._refs) for r in repos.values()),
                "total_commits": sum(len(r.store._commits) for r in repos.values()),
            }
            recent_commits_data = []
            for repo in repos_list:
                for commit in repo.store._commits.values():
                    recent_commits_data.append({
                        "repo_id": repo.repo_id,
                        "alias": repo.alias,
                        "commit_id": commit.commit_id,
                        "message": commit.message,
                        "event_name": commit.event_name,
                        "author": commit.author,
                        "timestamp": commit.timestamp,
                    })
            recent_commits_data.sort(key=lambda x: x["timestamp"], reverse=True)
            recent_commits_data = recent_commits_data[:15]

        # Build repos table
        repos_rows = ""
        for repo in repos_list:
            if use_db:
                storage = db.get_repo_storage(repo.repo_id)
                refs = storage.list_refs()
                refs_count = storage.refs_count()
                commits_count = storage.commits_count()
            else:
                refs = repo.store.list_refs()
                refs_count = len(repo.store._refs)
                commits_count = len(repo.store._commits)
            refs_str = ", ".join(r.name for r in refs) if refs else "(empty)"
            repos_rows += f"""
            <tr>
                <td><a href="/repos/{repo.repo_id}"><code>{repo.repo_id[:12]}...</code></a></td>
                <td><a href="/repos/{repo.repo_id}">{repo.alias or '<em>none</em>'}</a></td>
                <td>{repo.description or ''}</td>
                <td>{refs_count}</td>
                <td>{commits_count}</td>
                <td>{refs_str}</td>
            </tr>
            """

        # Build recent commits table
        commits_rows = ""
        for c in recent_commits_data:
            repo_name = c["alias"] if c["alias"] else c["repo_id"][:8]
            commits_rows += f"""
            <tr>
                <td>{repo_name}</td>
                <td><code>{c["commit_id"][:10]}</code></td>
                <td>{c["message"]}</td>
                <td>{c["event_name"]}</td>
                <td>{c["author"]}</td>
            </tr>
            """

        storage_type = "SQLite Database" if use_db else "In-Memory"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Object Versions Remote</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ padding: 20px; }}
                code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
                .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
                .stat {{ background: #f8f9fa; padding: 15px 25px; border-radius: 8px; text-align: center; }}
                .stat-value {{ font-size: 2em; font-weight: bold; color: #0d6efd; }}
                .stat-label {{ color: #6c757d; }}
                .badge-storage {{ background: #198754; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }}
            </style>
            <meta http-equiv="refresh" content="5">
        </head>
        <body>
            <div class="container">
                <h1>Object Versions Remote Server <span class="badge-storage">{storage_type}</span></h1>
                <p class="text-muted">Auto-refreshes every 5 seconds</p>

                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{stats["repos_count"]}</div>
                        <div class="stat-label">Repositories</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{stats["total_refs"]}</div>
                        <div class="stat-label">Total Refs</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{stats["total_commits"]}</div>
                        <div class="stat-label">Total Commits</div>
                    </div>
                </div>

                <h2>Repositories</h2>
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Alias</th>
                            <th>Description</th>
                            <th>Refs</th>
                            <th>Commits</th>
                            <th>Branches</th>
                        </tr>
                    </thead>
                    <tbody>
                        {repos_rows if repos_rows else '<tr><td colspan="6" class="text-muted">No repositories yet. Create one with POST /api/repos</td></tr>'}
                    </tbody>
                </table>

                <h2>Recent Commits</h2>
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Repo</th>
                            <th>ID</th>
                            <th>Message</th>
                            <th>Event</th>
                            <th>Author</th>
                        </tr>
                    </thead>
                    <tbody>
                        {commits_rows if commits_rows else '<tr><td colspan="5" class="text-muted">No commits yet</td></tr>'}
                    </tbody>
                </table>

                <hr>
                <h3>API Endpoints</h3>
                <ul>
                    <li><code>POST /api/repos</code> - Create new repository</li>
                    <li><code>GET /api/repos</code> - List repositories</li>
                    <li><code>GET /api/aliases/{{alias}}</code> - Resolve alias to repo_id</li>
                    <li><code>GET /api/repos/{{repo_id}}/refs</code> - List refs</li>
                    <li><code>GET /api/status</code> - Server status</li>
                </ul>
            </div>
        </body>
        </html>
        """
        return html

    # --- Object View UI ---

    @app.get("/repos/{repo_id}", response_class=HTMLResponse)
    def object_view_ui(repo_id: str, branch: str = "main"):
        """Interactive view for a repository's data with edit capabilities."""
        # Get repo info and storage
        storage = get_repo_storage(repo_id)
        if use_db:
            repo = db.get_repo(repo_id)
            alias = repo.alias if repo else None
        else:
            repo = repos.get(repo_id)
            alias = repo.alias if repo else None

        # Get current data using materialization
        if not storage.has_ref(branch):
            # No data yet
            rows = []
            metadata = {}
            commit_id = None
            columns = []
            events_replayed = 0
        else:
            ref = storage.get_ref(branch)
            commit_id = ref.commit_id
            store = materialize_at_commit(storage, commit_id)
            rows = store.entries
            metadata = store.meta

            # Check how many events were replayed
            _, _, events = storage.find_nearest_snapshot(commit_id)
            events_replayed = len(events)

            # Infer columns from data
            columns = []
            if rows:
                for row in rows:
                    for key in row.keys():
                        if key not in columns:
                            columns.append(key)

        # Get commit history
        commits_list = []
        if commit_id:
            current = commit_id
            for _ in range(10):  # Last 10 commits
                if not storage.has_commit(current):
                    break
                commit = storage.get_commit(current)
                commits_list.append(commit)
                if not commit.parents:
                    break
                current = commit.parents[0]

        # Build rows HTML
        rows_html = ""
        for i, row in enumerate(rows):
            cells = "".join(f"<td>{json.dumps(row.get(col, ''))}</td>" for col in columns)
            rows_html += f"""
            <tr data-index="{i}">
                <td>{i}</td>
                {cells}
                <td>
                    <button class="btn btn-sm btn-outline-primary edit-btn" data-index="{i}">Edit</button>
                    <button class="btn btn-sm btn-outline-danger delete-btn" data-index="{i}">Delete</button>
                </td>
            </tr>
            """

        # Build columns header
        columns_header = "".join(f"<th>{col}</th>" for col in columns)

        # Build commits HTML
        commits_html = ""
        for c in commits_list:
            # Format payload as collapsible JSON
            payload_json = json.dumps(c.event_payload, indent=2) if c.event_payload else "{}"
            payload_preview = json.dumps(c.event_payload)[:50] + "..." if len(json.dumps(c.event_payload)) > 50 else json.dumps(c.event_payload)
            commits_html += f"""
            <tr>
                <td>
                    <a href="#" class="time-travel-link" data-commit="{c.commit_id}" title="View data at this commit">
                        <code>{c.commit_id[:8]}</code>
                    </a>
                </td>
                <td>{c.message}</td>
                <td><span class="badge bg-secondary">{c.event_name}</span></td>
                <td>{c.author}</td>
                <td>
                    <button class="btn btn-sm btn-outline-secondary" type="button"
                            data-bs-toggle="collapse" data-bs-target="#payload-{c.commit_id[:8]}"
                            aria-expanded="false">
                        Show
                    </button>
                    <div class="collapse mt-2" id="payload-{c.commit_id[:8]}">
                        <pre class="bg-light p-2 rounded" style="font-size: 0.8em; max-height: 200px; overflow: auto;"><code>{payload_json}</code></pre>
                    </div>
                </td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{alias or repo_id[:12]} - Object View</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body {{ padding: 20px; }}
                code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
                .edit-btn, .delete-btn {{ margin-right: 5px; }}
                #addRowForm {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                .toast-container {{ position: fixed; top: 20px; right: 20px; z-index: 1050; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="toast-container" id="toastContainer"></div>

                <nav aria-label="breadcrumb">
                    <ol class="breadcrumb">
                        <li class="breadcrumb-item"><a href="/">Home</a></li>
                        <li class="breadcrumb-item active">{alias or repo_id[:12]}</li>
                    </ol>
                </nav>

                <h1>{alias or repo_id[:12]}</h1>
                <p class="text-muted" id="repoInfo">
                    ID: <code>{repo_id}</code> |
                    Branch: <strong>{branch}</strong> |
                    Rows: <strong id="rowCount">{len(rows)}</strong> |
                    Commit: <code id="currentCommit">{commit_id[:8] if commit_id else 'none'}</code>
                </p>
                <div id="timeTravelBanner" class="alert alert-warning d-none" role="alert">
                    <strong>Time Travel Mode:</strong> Viewing data at commit <code id="viewingCommit"></code>
                    <button class="btn btn-sm btn-outline-dark ms-3" onclick="returnToHead()">Return to HEAD</button>
                </div>

                <!-- Add Row Form -->
                <div id="addRowForm">
                    <h5>Add Row</h5>
                    <div class="row g-2 align-items-end">
                        <div class="col-md-8">
                            <label class="form-label">Row JSON</label>
                            <input type="text" class="form-control" id="newRowJson"
                                   placeholder='{{"key": "value", "another": 123}}'>
                        </div>
                        <div class="col-md-2">
                            <label class="form-label">Message</label>
                            <input type="text" class="form-control" id="commitMessage" placeholder="Added row">
                        </div>
                        <div class="col-md-2">
                            <button class="btn btn-primary w-100" onclick="addRow()">Add Row</button>
                        </div>
                    </div>
                </div>

                <!-- Metadata Section -->
                <div id="metaSection" class="mb-4">
                    <h3>Metadata <small class="text-muted">({len(metadata)} keys)</small></h3>
                    <div class="bg-light p-3 rounded" style="max-height: 300px; overflow: auto;">
                        <pre id="metaContent" style="margin: 0; font-size: 0.85em;"><code>{json.dumps(metadata, indent=2, default=str) if metadata else '{}'}</code></pre>
                    </div>
                </div>

                <!-- Data Table -->
                <h3>Data <small class="text-muted">({len(rows)} entries)</small></h3>
                <table class="table table-striped table-hover" id="dataTable">
                    <thead>
                        <tr>
                            <th>#</th>
                            {columns_header}
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html if rows_html else '<tr><td colspan="100" class="text-muted">No data yet</td></tr>'}
                    </tbody>
                </table>

                <!-- Commit History -->
                <h3>Recent Commits</h3>
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Message</th>
                            <th>Event</th>
                            <th>Author</th>
                            <th>Payload</th>
                        </tr>
                    </thead>
                    <tbody>
                        {commits_html if commits_html else '<tr><td colspan="5" class="text-muted">No commits yet</td></tr>'}
                    </tbody>
                </table>

                <!-- Clone Instructions -->
                <div class="mt-4 p-3 bg-light rounded">
                    <h5>Clone this data</h5>
                    <pre><code>from edsl.versioning import ObjectVersionsServer

server = ObjectVersionsServer("http://localhost:8766")
data = server.clone("{repo_id}")
print(data["entries"])  # List of entries
print(data["meta"])     # Metadata dict</code></pre>
                </div>
            </div>

            <!-- Edit Modal -->
            <div class="modal fade" id="editModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Row</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <input type="hidden" id="editIndex">
                            <div class="mb-3">
                                <label class="form-label">Row JSON</label>
                                <textarea class="form-control" id="editRowJson" rows="5"></textarea>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Commit Message</label>
                                <input type="text" class="form-control" id="editMessage" placeholder="Updated row">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="saveEdit()">Save</button>
                        </div>
                    </div>
                </div>
            </div>

            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
            <script>
                const REPO_ID = "{repo_id}";
                const BRANCH = "{branch}";
                const API_BASE = "/api/repos/" + REPO_ID;

                // Current data (for editing)
                const currentData = {json.dumps(rows)};

                function showToast(message, type = 'success') {{
                    const container = document.getElementById('toastContainer');
                    const toast = document.createElement('div');
                    toast.className = 'toast show align-items-center text-white bg-' + (type === 'success' ? 'success' : 'danger');
                    toast.innerHTML = `
                        <div class="d-flex">
                            <div class="toast-body">${{message}}</div>
                            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                        </div>
                    `;
                    container.appendChild(toast);
                    setTimeout(() => toast.remove(), 3000);
                }}

                async function applyEvent(eventName, eventPayload, message) {{
                    try {{
                        const response = await fetch(API_BASE + '/events', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{
                                event_name: eventName,
                                event_payload: eventPayload,
                                message: message || eventName,
                                author: 'web',
                                branch: BRANCH
                            }})
                        }});
                        if (!response.ok) {{
                            const err = await response.json();
                            throw new Error(err.detail || 'Failed to apply event');
                        }}
                        const result = await response.json();
                        showToast('Commit ' + result.commit_id.slice(0, 8) + ' created');
                        setTimeout(() => location.reload(), 500);
                        return result;
                    }} catch (err) {{
                        showToast(err.message, 'error');
                        throw err;
                    }}
                }}

                function addRow() {{
                    const jsonInput = document.getElementById('newRowJson').value;
                    const message = document.getElementById('commitMessage').value || 'Added row';
                    try {{
                        const row = JSON.parse(jsonInput);
                        applyEvent('append_row', {{ row: row }}, message);
                    }} catch (e) {{
                        showToast('Invalid JSON: ' + e.message, 'error');
                    }}
                }}

                function openEditModal(index) {{
                    document.getElementById('editIndex').value = index;
                    document.getElementById('editRowJson').value = JSON.stringify(currentData[index], null, 2);
                    document.getElementById('editMessage').value = 'Updated row ' + index;
                    new bootstrap.Modal(document.getElementById('editModal')).show();
                }}

                function saveEdit() {{
                    const index = parseInt(document.getElementById('editIndex').value);
                    const jsonInput = document.getElementById('editRowJson').value;
                    const message = document.getElementById('editMessage').value || 'Updated row';
                    try {{
                        const row = JSON.parse(jsonInput);
                        applyEvent('update_row', {{ index: index, row: row }}, message);
                        bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                    }} catch (e) {{
                        showToast('Invalid JSON: ' + e.message, 'error');
                    }}
                }}

                function deleteRow(index) {{
                    if (confirm('Delete row ' + index + '?')) {{
                        applyEvent('delete_row', {{ index: index }}, 'Deleted row ' + index);
                    }}
                }}

                // Wire up buttons
                document.querySelectorAll('.edit-btn').forEach(btn => {{
                    btn.addEventListener('click', () => openEditModal(parseInt(btn.dataset.index)));
                }});
                document.querySelectorAll('.delete-btn').forEach(btn => {{
                    btn.addEventListener('click', () => deleteRow(parseInt(btn.dataset.index)));
                }});

                // Time travel functionality
                const HEAD_COMMIT = "{commit_id or ''}";
                let isTimeTraveling = false;

                async function timeTravel(commitId) {{
                    try {{
                        const response = await fetch(API_BASE + '/commits/' + commitId + '/data');
                        if (!response.ok) {{
                            throw new Error('Failed to fetch data at commit');
                        }}
                        const data = await response.json();

                        // Update the table with historical data
                        updateDataTable(data.entries);

                        // Update metadata
                        updateMetadata(data.meta || {{}});

                        // Show time travel banner
                        document.getElementById('timeTravelBanner').classList.remove('d-none');
                        document.getElementById('viewingCommit').textContent = commitId.slice(0, 8);
                        document.getElementById('rowCount').textContent = data.entries.length;
                        document.getElementById('currentCommit').textContent = commitId.slice(0, 8);

                        // Disable editing in time travel mode
                        document.getElementById('addRowForm').style.opacity = '0.5';
                        document.getElementById('addRowForm').style.pointerEvents = 'none';

                        isTimeTraveling = true;
                        showToast('Viewing data at commit ' + commitId.slice(0, 8));
                    }} catch (err) {{
                        showToast(err.message, 'error');
                    }}
                }}

                function updateMetadata(meta) {{
                    const metaContent = document.getElementById('metaContent');
                    const metaKeys = Object.keys(meta).length;
                    document.querySelector('#metaSection h3').innerHTML = 'Metadata <small class="text-muted">(' + metaKeys + ' keys)</small>';
                    metaContent.innerHTML = '<code>' + JSON.stringify(meta, null, 2) + '</code>';
                }}

                function returnToHead() {{
                    location.reload();
                }}

                function updateDataTable(entries) {{
                    const tbody = document.querySelector('#dataTable tbody');

                    if (!entries || entries.length === 0) {{
                        tbody.innerHTML = '<tr><td colspan="100" class="text-muted">No data at this commit</td></tr>';
                        return;
                    }}

                    // Get all unique columns
                    const columns = [];
                    entries.forEach(row => {{
                        Object.keys(row).forEach(key => {{
                            if (!columns.includes(key)) columns.push(key);
                        }});
                    }});

                    // Update header
                    const thead = document.querySelector('#dataTable thead tr');
                    thead.innerHTML = '<th>#</th>' + columns.map(c => '<th>' + c + '</th>').join('') + '<th>Actions</th>';

                    // Update body
                    tbody.innerHTML = entries.map((row, i) => {{
                        const cells = columns.map(col => '<td>' + JSON.stringify(row[col] !== undefined ? row[col] : '') + '</td>').join('');
                        return `<tr data-index="${{i}}">
                            <td>${{i}}</td>
                            ${{cells}}
                            <td><em class="text-muted">read-only</em></td>
                        </tr>`;
                    }}).join('');
                }}

                // Wire up time travel links
                document.querySelectorAll('.time-travel-link').forEach(link => {{
                    link.addEventListener('click', (e) => {{
                        e.preventDefault();
                        const commitId = link.dataset.commit;
                        timeTravel(commitId);
                    }});
                }});
            </script>
        </body>
        </html>
        """
        return html

    return app


def run_server(host: str = "0.0.0.0", port: int = 8765, db_url: Optional[str] = None):
    """
    Run the FastAPI server.

    Args:
        host: Host to bind to
        port: Port to bind to
        db_url: SQLAlchemy database URL for persistent storage.
                If None, uses in-memory storage.
    """
    import uvicorn
    app = create_app(db_url=db_url)
    uvicorn.run(app, host=host, port=port)


# --- CLI ---

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Object Versions Remote Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind to")
    parser.add_argument("--db", default="sqlite:///object_versions.db",
                        help="Database URL (default: sqlite:///object_versions.db)")
    parser.add_argument("--memory", action="store_true",
                        help="Use in-memory storage instead of database")
    args = parser.parse_args()

    db_url = None if args.memory else args.db
    storage_type = "in-memory" if args.memory else args.db

    print(f"Starting Object Versions Remote Server at http://{args.host}:{args.port}")
    print(f"Storage: {storage_type}")
    print(f"Web UI: http://localhost:{args.port}/")
    print(f"API: http://localhost:{args.port}/api/status")
    run_server(host=args.host, port=args.port, db_url=db_url)
