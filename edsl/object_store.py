"""Global CAS object store at ~/.edsl_objects/."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Optional


class ObjectStore:
    """Manages a directory of CAS-versioned objects, each identified by UUID.

    Each object gets its own subdirectory under the store root, containing
    the full CAS repository (blobs/, trees/, commits/, HEAD).  An index.json
    at the root tracks all objects.

    Currently supports AgentList only.

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> store = ObjectStore(tempfile.mkdtemp())
        >>> al = AgentList([Agent(traits={"age": 22})])
        >>> uid = store.new_save(al, message="first")
        >>> len(uid) == 36  # UUID format
        True
        >>> al._cas_uuid == uid
        True
        >>> al2 = store.new_load(uid)
        >>> al == al2
        True
        >>> al2._cas_uuid == uid
        True
        >>> len(store.list()) == 1
        True
        >>> len(store.log(uid)) == 1
        True
        >>> store.delete(uid)
        >>> store.list()
        []
    """

    DEFAULT_ROOT = Path.home() / ".edsl_objects"

    def __init__(self, root: Optional[str | Path] = None):
        self.root = Path(root) if root else self.DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

    def _index_path(self) -> Path:
        return self.root / "index.json"

    def _read_index(self) -> dict:
        p = self._index_path()
        if p.exists():
            return json.loads(p.read_text())
        return {}

    def _write_index(self, index: dict) -> None:
        self._index_path().write_text(json.dumps(index, indent=2))

    def _update_index(self, uuid: str, type_name: str, message: str) -> None:
        index = self._read_index()
        now = datetime.now(timezone.utc).isoformat()
        if uuid in index:
            index[uuid]["last_modified"] = now
            if message:
                index[uuid]["description"] = message
        else:
            index[uuid] = {
                "type": type_name,
                "description": message,
                "created": now,
                "last_modified": now,
            }
        self._write_index(index)

    def new_save(self, obj, message: str = "") -> str:
        """Save an object to CAS. Returns its UUID.

        Auto-assigns a UUID on first save, reuses on subsequent saves.
        """
        uuid = getattr(obj, "_cas_uuid", None) or str(uuid4())
        obj._cas_uuid = uuid
        obj_dir = self.root / uuid
        obj.to_cas(obj_dir, message=message)
        self._update_index(uuid, type(obj).__name__, message)
        return uuid

    def new_load(self, uuid: str, commit: Optional[str] = None):
        """Load an object by UUID. Defaults to HEAD."""
        from edsl.agents.agent_list import AgentList

        obj_dir = self.root / uuid
        if not obj_dir.exists():
            raise FileNotFoundError(f"No object with UUID {uuid} in store")
        obj = AgentList.from_cas(obj_dir, commit=commit)
        obj._cas_uuid = uuid
        return obj

    def list(self) -> list[dict]:
        """List all objects in the store.

        Returns a list of dicts with keys: uuid, type, description,
        created, last_modified.
        """
        index = self._read_index()
        return [
            {"uuid": uid, **info}
            for uid, info in index.items()
        ]

    def log(self, uuid: str) -> list[dict]:
        """Commit history for an object."""
        from edsl.agents.agent_list import AgentList

        obj_dir = self.root / uuid
        if not obj_dir.exists():
            raise FileNotFoundError(f"No object with UUID {uuid} in store")
        return AgentList.cas_log(obj_dir)

    def delete(self, uuid: str) -> None:
        """Remove an object and its history from the store."""
        obj_dir = self.root / uuid
        if obj_dir.exists():
            shutil.rmtree(obj_dir)
        index = self._read_index()
        index.pop(uuid, None)
        self._write_index(index)
