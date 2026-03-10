"""Global CAS object store at ~/.edsl_objects/.

Uses :class:`CASRepository` for versioning.  Domain objects only need
``to_jsonl()`` / ``from_jsonl()`` — they don't know about CAS internals.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Optional

from .cas_repository import CASRepository


# Map type-name strings (stored in meta.json) to the class that can
# deserialize the JSONL content.  Lazy — entries are callables that
# return the class.
_CLASS_REGISTRY: dict[str, callable] = {
    "AgentList": lambda: _import_agent_list(),
}


def _import_agent_list():
    from edsl.agents.agent_list import AgentList
    return AgentList


class ObjectStore:
    """Manages a directory of CAS-versioned objects, each identified by UUID.

    Each object gets its own subdirectory containing the full CAS
    repository (blobs/, trees/, commits/, HEAD) plus a ``meta.json``
    with type and description info.  No shared index file — listing
    the store just scans subdirectories.

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> store = ObjectStore(tempfile.mkdtemp())
        >>> al = AgentList([Agent(traits={"age": 22})])
        >>> info = store.save(al, message="first")
        >>> uid = info['uuid']
        >>> info['branch']
        'main'
        >>> len(info['commit']) == 64
        True
        >>> al._cas_uuid == uid
        True
        >>> al._cas_commit == info['commit']
        True
        >>> al._cas_branch == 'main'
        True
        >>> al2 = store.load(uid)
        >>> al == al2
        True
        >>> al2._cas_uuid == uid
        True
        >>> al2._cas_commit == info['commit']
        True
        >>> al2._cas_branch == 'main'
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

    def _repo(self, uuid: str) -> CASRepository:
        """Return the CASRepository for the given UUID, checking existence."""
        obj_dir = self.root / uuid
        if not obj_dir.exists():
            raise FileNotFoundError(f"No object with UUID {uuid} in store")
        return CASRepository(obj_dir)

    # ------------------------------------------------------------------
    # core operations
    # ------------------------------------------------------------------

    def save(self, obj, message: str = "", branch: Optional[str] = None) -> dict:
        """Save an object to CAS.

        Returns a dict with ``uuid``, ``commit``, ``branch``, ``parent``,
        ``timestamp``, and ``message``.

        Auto-assigns a UUID on first save, reuses on subsequent saves.
        The object must provide ``to_jsonl() -> str``.

        Uses compare-and-swap: if the object carries a ``_cas_commit``
        from a previous save/load, the branch tip must still point at
        that commit.  Otherwise :class:`StaleBranchError` is raised.
        """
        uuid = getattr(obj, "_cas_uuid", None) or str(uuid4())
        obj._cas_uuid = uuid
        obj_dir = self.root / uuid
        repo = CASRepository(obj_dir)

        expected_parent = getattr(obj, "_cas_commit", None)
        info = repo.save(
            obj.to_jsonl(),
            message=message,
            branch=branch,
            expected_parent=expected_parent,
        )
        self._write_meta(obj_dir, type(obj).__name__, message)

        # Track commit and branch on the object
        obj._cas_commit = info["commit"]
        obj._cas_branch = info["branch"]

        return {"uuid": uuid, **info}

    def load(self, uuid: str, commit: Optional[str] = None, branch: Optional[str] = None):
        """Load an object by UUID. Defaults to HEAD."""
        repo = self._repo(uuid)
        content = repo.load(commit=commit, branch=branch)
        cls = self._resolve_class(uuid)
        obj = cls.from_jsonl(content)
        obj._cas_uuid = uuid

        # Track commit and branch on the loaded object
        obj._cas_commit = repo.resolve(commit, branch)
        obj._cas_branch = repo.head_branch()

        return obj

    def log(self, uuid: str, commit: Optional[str] = None, branch: Optional[str] = None) -> list[dict]:
        """Commit history for an object."""
        return self._repo(uuid).log(commit=commit, branch=branch)

    def branches(self, uuid: str) -> list[str]:
        """List branches for an object."""
        return self._repo(uuid).branches()

    def branch(self, uuid: str, name: str, from_branch: Optional[str] = None) -> None:
        """Create a new branch for an object."""
        self._repo(uuid).branch(name, from_branch=from_branch)

    def checkout(self, uuid: str, branch: str) -> None:
        """Switch an object's HEAD to the given branch."""
        self._repo(uuid).checkout(branch)

    def list(self) -> list[dict]:
        """List all objects in the store.

        Scans subdirectories for meta.json files. No shared index.
        """
        results = []
        for meta_path in self.root.glob("*/meta.json"):
            meta = json.loads(meta_path.read_text())
            meta["uuid"] = meta_path.parent.name
            results.append(meta)
        return results

    def delete(self, uuid: str) -> None:
        """Remove an object and its history from the store."""
        obj_dir = self.root / uuid
        if obj_dir.exists():
            shutil.rmtree(obj_dir)

    # ------------------------------------------------------------------
    # class resolution
    # ------------------------------------------------------------------

    def _resolve_class(self, uuid: str):
        """Read meta.json to determine the object type and return its class."""
        meta_path = self.root / uuid / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"No meta.json for UUID {uuid}")
        meta = json.loads(meta_path.read_text())
        type_name = meta.get("type")
        if type_name not in _CLASS_REGISTRY:
            raise ValueError(
                f"Unknown object type '{type_name}' for UUID {uuid}. "
                f"Known types: {sorted(_CLASS_REGISTRY)}"
            )
        return _CLASS_REGISTRY[type_name]()

    # ------------------------------------------------------------------
    # per-object metadata
    # ------------------------------------------------------------------

    @staticmethod
    def _write_meta(obj_dir: Path, type_name: str, message: str) -> None:
        meta_path = obj_dir / "meta.json"
        now = datetime.now(timezone.utc).isoformat()
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            meta["last_modified"] = now
            if message:
                meta["description"] = message
        else:
            meta = {
                "type": type_name,
                "description": message,
                "created": now,
                "last_modified": now,
            }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
