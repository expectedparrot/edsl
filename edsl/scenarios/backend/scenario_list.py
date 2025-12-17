import sqlite3
from functools import wraps
from pathlib import Path

from .memory_backend import MemoryState
from .sqlite_backend import SQLiteState

from typing import List, Any, Dict, Optional, Iterator, Tuple, Callable

from .plan import (build_append_plan, build_rename_plan, build_drop_key_plan, build_add_values_plan)


def tracks_mutation(method: Callable) -> Callable:
    """Decorator that increments version and records mutation in backend history."""
    @wraps(method)
    def wrapper(self: "ScenarioList", *args, **kwargs):
        # Increment version before the mutation
        self.backend._increment_version()
        # Execute the mutation
        result = method(self, *args, **kwargs)
        # Record in backend history
        self.backend.append_history(method.__name__, args, kwargs)
        return result
    return wrapper


# Global connection for SQLite backend
conn = sqlite3.connect(":memory:")
_schema_path = Path(__file__).parent / "schema.sql"
with open(_schema_path, "r", encoding="utf-8") as f:
    conn.executescript(f.read())


from enum import Enum 
class Backend(Enum):
    MEMORY = "memory"
    SQLITE = "sqlite"


class ScenarioListView:
    """Read-only view of a ScenarioList at a specific version."""
    
    def __init__(self, backend, at_version: int):
        self._backend = backend
        self._at_version = at_version

    def get_scenario(self, position: int) -> Any:
        return self._backend.get_materialized_scenario(position, at_version=self._at_version)

    def __getitem__(self, position: int) -> Any:
        return self._backend.get_scenario(position, at_version=self._at_version)

    def __len__(self) -> int:
        return self._backend.get_length(at_version=self._at_version)

    def __iter__(self) -> Iterator[Any]:
        """Lazily stream materialised scenarios."""
        length = self._backend.get_length(at_version=self._at_version)
        for i in range(length):
            yield self._backend.get_materialized_scenario(i, at_version=self._at_version)

    def get_all_scenarios(self) -> List[Any]:
        return self._backend.get_all_materialized_scenarios(at_version=self._at_version)

    def __str__(self) -> str:
        return str(self.get_all_scenarios())

    def __repr__(self) -> str:
        return f"ScenarioListView(version={self._at_version}, data={self.get_all_scenarios()})"

    @property
    def version(self) -> int:
        return self._at_version

    def to_list(self, backend_type: "Backend" = Backend.MEMORY) -> "ScenarioList":
        """Convert this view to a new mutable ScenarioList."""
        data = self.get_all_scenarios()
        return ScenarioList(data, backend=backend_type)


class ScenarioList:
    _next_list_id: int = 0  # Class variable for unique SQLite list_ids

    def __init__(
        self,
        data: Optional[List[Any]] = None,
        backend: Backend = Backend.MEMORY,
    ):
        if data is None:
            data = []

        self._backend_type = backend

        if backend == Backend.MEMORY:
            self.backend = MemoryState()
        elif backend == Backend.SQLITE:
            list_id = ScenarioList._next_list_id
            ScenarioList._next_list_id += 1
            self.backend = SQLiteState(conn, list_id)
        else:
            raise ValueError(f"Invalid backend: {backend}")

        for entry in data:
            self.append(entry)

    def get_scenario(self, position: int) -> Any:
        return self.backend.get_materialized_scenario(position)

    def __getitem__(self, position: int) -> Any:
        return self.backend.get_scenario(position)

    def __len__(self) -> int:
        return self.backend.get_length()

    def __iter__(self) -> Iterator[Any]:
        """Lazily stream materialised scenarios instead of loading all at once."""
        for i in range(self.backend.get_length()):
            yield self.backend.get_materialized_scenario(i)

    def get_all_scenarios(self) -> List[Any]:
        return self.backend.get_all_materialized_scenarios()

    def __str__(self) -> str:
        return str(self.get_all_scenarios())

    def __repr__(self) -> str:
        return f"ScenarioList(data={self.get_all_scenarios()})"

    @tracks_mutation
    def append(self, entry: Any) -> None:
        plan = build_append_plan(entry)
        plan.execute(self.backend, {"payload": entry})
        return None

    @tracks_mutation
    def rename(self, old_key: str, new_key: str) -> None:
        plan = build_rename_plan(old_key, new_key)
        plan.execute(self.backend, {})
        return None

    @tracks_mutation
    def drop_key(self, key: str) -> None:
        plan = build_drop_key_plan(key)
        plan.execute(self.backend, {})
        return None

    @tracks_mutation
    def add_values(self, key: str, values: List[Any]) -> None:
        plan = build_add_values_plan(key, values)
        plan.execute(self.backend, {})
        return None

    @property
    def history(self) -> List[Tuple[int, str, tuple, dict]]:
        """Return the list of recorded mutations as (version, method_name, args, kwargs) tuples."""
        return self.backend.get_history()

    @property
    def version(self) -> int:
        """Return the current version number."""
        return self.backend.version

    def at_version(self, version: int) -> ScenarioListView:
        """Get a read-only view of this ScenarioList at a specific version.
        
        Args:
            version: The version number to view (0 = empty, 1 = after first mutation, etc.)
        
        Returns:
            A ScenarioListView - a read-only view at the requested version.
            Use .to_list() on the view to create a new mutable ScenarioList.
        """
        current_version = self.backend.version
        if version < 0 or version > current_version:
            raise ValueError(f"Version {version} out of range [0, {current_version}]")

        return ScenarioListView(self.backend, at_version=version)

    def snapshot(self) -> None:
        """Save a snapshot of the current state for faster future reconstruction.
        
        Only available for SQLite backend.
        """
        if hasattr(self.backend, 'save_snapshot'):
            self.backend.save_snapshot()

    def get_delta(self, from_version: int) -> Dict[str, Any]:
        """Get all changes since from_version for syncing to a remote."""
        return self.backend.get_delta(from_version)

    def apply_delta(self, delta: Dict[str, Any]) -> None:
        """Apply a delta from a remote to sync state."""
        self.backend.apply_delta(delta)

    # Remote sync methods (requires server to be running)
    def push(self, server_url: str, list_id: int, from_version: int) -> Dict[str, Any]:
        """
        Push local changes to a remote server.
        
        Args:
            server_url: Base URL of the server (e.g., "http://localhost:8000")
            list_id: The list ID on the remote server
            from_version: The remote's last known version
            
        Returns:
            Response dict with status and details
        """
        import requests
        
        delta = self.get_delta(from_version)
        response = requests.post(
            f"{server_url}/lists/{list_id}/push",
            json=delta
        )
        return response.json()

    def pull(self, server_url: str, list_id: int) -> Dict[str, Any]:
        """
        Pull changes from a remote server.
        
        Args:
            server_url: Base URL of the server (e.g., "http://localhost:8000")
            list_id: The list ID on the remote server
            
        Returns:
            Response dict with status and delta (if any changes)
        """
        import requests
        
        response = requests.get(
            f"{server_url}/lists/{list_id}/pull",
            params={"from_version": self.version}
        )
        result = response.json()
        
        if result.get("status") == "has_changes" and result.get("delta"):
            self.apply_delta(result["delta"])
        
        return result

    @classmethod
    def from_remote(cls, server_url: str, list_id: int, backend: "Backend" = None) -> "ScenarioList":
        """
        Create a ScenarioList by pulling from a remote server.
        
        Args:
            server_url: Base URL of the server
            list_id: The list ID to pull
            backend: Backend type for local storage (default: MEMORY)
            
        Returns:
            A new ScenarioList synced with the remote
        """
        import requests
        
        if backend is None:
            backend = Backend.MEMORY
        
        # Get current state from server
        response = requests.get(f"{server_url}/lists/{list_id}")
        response.raise_for_status()
        data = response.json()
        
        # Create local list from scenarios (stripping _digest as it will be recomputed)
        scenarios = [
            {k: v for k, v in s.items() if k != "_digest"}
            for s in data["scenarios"]
        ]
        
        return cls(scenarios, backend=backend)
