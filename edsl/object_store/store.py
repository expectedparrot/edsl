"""Global CAS object store at ~/.edsl_objects/.

Uses :class:`CASRepository` for versioning.  Domain objects only need
``to_jsonl()`` / ``from_jsonl()`` — they don't know about CAS internals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Optional

from .cas_repository import CASRepository
from .fs_backend import FileSystemBackend
from .sqlite_metadata_index import SQLiteMetadataIndex


# Map type-name strings (stored in metadata index) to the class that can
# deserialize the JSONL content.  Lazy — entries are callables that
# return the class.
_CLASS_REGISTRY: dict[str, callable] = {
    "AgentList": lambda: _lazy_import("edsl.agents.agent_list", "AgentList"),
    "ScenarioList": lambda: _lazy_import("edsl.scenarios.scenario_list", "ScenarioList"),
    "ModelList": lambda: _lazy_import("edsl.language_models.model_list", "ModelList"),
    "Survey": lambda: _lazy_import("edsl.surveys.survey", "Survey"),
}


def _lazy_import(module_path: str, class_name: str):
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


class ObjectStore:
    """Manages a collection of CAS-versioned objects, each identified by UUID.

    Accepts pluggable *backend_factory* and *metadata_index* for storage
    and indexing respectively, defaulting to filesystem + SQLite.

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
        >>> al2, meta = store.load(uid)
        >>> al == al2
        True
        >>> meta['uuid'] == uid
        True
        >>> meta['commit'] == info['commit']
        True
        >>> meta['branch']
        'main'
        >>> len(store.list()) == 1
        True
        >>> len(store.log(uid)) == 1
        True
        >>> store.delete(uid)
        >>> store.list()
        []
    """

    DEFAULT_ROOT = Path.home() / ".edsl_objects"

    def __init__(
        self,
        root: Optional[str | Path] = None,
        backend_factory=None,
        metadata_index=None,
    ):
        self.root = Path(root) if root else self.DEFAULT_ROOT
        self.root.mkdir(parents=True, exist_ok=True)

        self._backend_factory = backend_factory or self._default_backend_factory
        self._index = metadata_index or SQLiteMetadataIndex(
            self.root / "index.db"
        )

        # One-time migration from meta.json files to SQLite
        if isinstance(self._index, SQLiteMetadataIndex):
            self._index.migrate_from_directory(self.root)

    def _default_backend_factory(self, uuid: str):
        """Create a FileSystemBackend for the given object UUID."""
        return FileSystemBackend(self.root / uuid)

    def _repo(self, uuid: str) -> CASRepository:
        """Return the CASRepository for the given UUID."""
        backend = self._backend_factory(uuid)
        # Check existence via backend (HEAD must exist for a valid repo)
        if not backend.exists("HEAD"):
            raise FileNotFoundError(f"No object with UUID {uuid} in store")
        return CASRepository(self.root / uuid, backend=backend)

    # ------------------------------------------------------------------
    # core operations
    # ------------------------------------------------------------------

    def save(
        self,
        obj,
        message: str = "",
        branch: Optional[str] = None,
        uuid: Optional[str] = None,
        expected_parent: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> dict:
        """Save an object to CAS.

        Returns a dict with ``uuid``, ``commit``, ``tree``, ``branch``,
        ``parent``, ``timestamp``, and ``message``.

        Args:
            obj: The object to save.  Must provide ``to_jsonl() -> str``.
            message: Commit message.
            branch: Target branch (default: current HEAD branch).
            uuid: Existing UUID to reuse, or *None* to auto-assign.
            expected_parent: If given, the branch tip must still point at
                this commit (compare-and-swap).  Otherwise
                :class:`StaleBranchError` is raised.
        """
        uuid = uuid or str(uuid4())
        backend = self._backend_factory(uuid)
        repo = CASRepository(self.root / uuid, backend=backend)

        info = repo.save(
            obj.to_jsonl(),
            message=message,
            branch=branch,
            expected_parent=expected_parent,
        )

        # Update metadata index
        type_name = type(obj).__name__
        self._update_meta(uuid, type_name, message, owner=owner)

        # Index the commit
        self._index.put_commit(uuid, info["commit"], {
            "parent": info["parent"],
            "tree": info["tree"],
            "timestamp": info["timestamp"],
            "message": info["message"],
            "branch": info["branch"],
        })

        return {"uuid": uuid, **info}

    def load(self, uuid: str, commit: Optional[str] = None, branch: Optional[str] = None):
        """Load an object by UUID. Defaults to HEAD.

        Returns a tuple ``(obj, meta)`` where *meta* is a dict with
        ``uuid``, ``commit``, and ``branch`` so the caller can track
        CAS state however it likes.
        """
        repo = self._repo(uuid)
        content = repo.load(commit=commit, branch=branch)
        cls = self._resolve_class(uuid)
        obj = cls.from_jsonl(content)

        meta = {
            "uuid": uuid,
            "commit": repo.resolve(commit, branch),
            "branch": repo.head_branch(),
        }
        return obj, meta

    def log(self, uuid: str, commit: Optional[str] = None, branch: Optional[str] = None) -> list[dict]:
        """Commit history for an object.

        Tries the metadata index first (fast), falls back to walking
        the commit chain in the CAS repository.
        """
        indexed = self._index.log(uuid, branch=branch)
        if indexed:
            return indexed
        # Fallback for objects not yet indexed
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
        """List all objects in the store."""
        return self._index.list_all()

    def delete(self, uuid: str) -> None:
        """Remove an object and its history from the store."""
        self._index.delete(uuid)
        backend = self._backend_factory(uuid)
        backend.delete_tree("")

    # ------------------------------------------------------------------
    # sync / push / pull
    # ------------------------------------------------------------------

    @staticmethod
    def sync(source, dest, branch: Optional[str] = None) -> dict:
        """Copy CAS objects from *source* backend to *dest* backend.

        Walks the commit chain on *branch* (or HEAD) and copies any
        blobs, trees, and commits that *dest* is missing.  Updates the
        ref and HEAD in *dest*.

        Both *source* and *dest* must satisfy the :class:`StorageBackend`
        protocol.

        Returns a dict with counts of objects copied and the final
        commit hash.

        Examples:
            >>> import tempfile
            >>> from edsl import Agent, AgentList
            >>> from edsl.object_store import ObjectStore
            >>> from edsl.object_store.fs_backend import FileSystemBackend
            >>> from edsl.object_store.cas_repository import CASRepository
            >>> src_dir = tempfile.mkdtemp()
            >>> src = FileSystemBackend(src_dir)
            >>> repo = CASRepository(src_dir, backend=src)
            >>> _ = repo.save("hello\\n", message="first")
            >>> dst_dir = tempfile.mkdtemp()
            >>> dst = FileSystemBackend(dst_dir)
            >>> result = ObjectStore.sync(src, dst)
            >>> result['commits']
            1
            >>> CASRepository(dst_dir, backend=dst).load() == "hello\\n"
            True
        """
        import json

        # Resolve the starting commit
        if branch is not None:
            ref_key = f"refs/{branch}"
            if not source.exists(ref_key):
                raise FileNotFoundError(f"Branch '{branch}' does not exist on source")
            tip = source.read(ref_key).strip()
        else:
            if not source.exists("HEAD"):
                raise FileNotFoundError("No HEAD on source — nothing to sync")
            head_branch = source.read("HEAD").strip()
            branch = head_branch
            tip = source.read(f"refs/{branch}").strip()

        # Walk commit chain, collect missing objects
        copied = {"blobs": 0, "trees": 0, "commits": 0}
        commit_hash = tip
        while commit_hash:
            commit_key = f"commits/{commit_hash}.json"
            if dest.exists(commit_key):
                # Already have this commit and all its ancestors
                break

            commit_content = source.read(commit_key)
            commit_obj = json.loads(commit_content)

            # Copy tree
            tree_key = f"trees/{commit_obj['tree']}.json"
            if not dest.exists(tree_key):
                dest.write(tree_key, source.read(tree_key))
                copied["trees"] += 1

            # Copy blob(s) referenced by the tree
            tree_obj = json.loads(source.read(tree_key))
            blob_key = f"blobs/{tree_obj['blob']}.json"
            if not dest.exists(blob_key):
                dest.write(blob_key, source.read(blob_key))
                copied["blobs"] += 1

            # Copy commit
            dest.write(commit_key, commit_content)
            copied["commits"] += 1

            commit_hash = commit_obj.get("parent")

        # Update ref and HEAD
        dest.write(f"refs/{branch}", tip + "\n")
        dest.write("HEAD", branch + "\n")

        # Update current.jsonl snapshot
        tip_commit = json.loads(dest.read(f"commits/{tip}.json"))
        tip_tree = json.loads(dest.read(f"trees/{tip_commit['tree']}.json"))
        dest.write("current.jsonl", dest.read(f"blobs/{tip_tree['blob']}.json"))

        return {"commit": tip, "branch": branch, **copied}

    def push(self, uuid: str, remote_url: str, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
        """Push a local object to a remote CAS service.

        Args:
            uuid: The local object UUID to push.
            remote_url: Base URL of the remote CAS service.
            branch: Branch to push (default: HEAD branch).
            token: Bearer token for authentication.

        Returns:
            A dict with sync results.
        """
        from .http_backend import HttpBackend

        local_backend = self._backend_factory(uuid)
        if not local_backend.exists("HEAD"):
            raise FileNotFoundError(f"No object with UUID {uuid} in local store")

        # Include metadata so the remote can create the index entry
        # before indexing commits (FK constraint).
        meta = self._index.get(uuid)
        remote_backend = HttpBackend(remote_url, uuid, token=token)
        if meta:
            remote_backend._pending_meta = {
                "type": meta["type"],
                "description": meta.get("description", ""),
            }

        return self.sync(local_backend, remote_backend, branch=branch)

    def pull(self, uuid: str, remote_url: str, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
        """Pull a remote object to the local store.

        Args:
            uuid: The remote object UUID to pull.
            remote_url: Base URL of the remote CAS service.
            branch: Branch to pull (default: HEAD branch).
            token: Bearer token for authentication.

        Returns:
            A dict with sync results.
        """
        from .http_backend import HttpBackend

        remote_backend = HttpBackend(remote_url, uuid, token=token)
        local_backend = self._backend_factory(uuid)

        result = self.sync(remote_backend, local_backend, branch=branch)

        # Sync metadata from remote
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        try:
            meta_url = f"{remote_url.rstrip('/')}/api/objects/{uuid}/meta"
            req = Request(meta_url, headers={"Accept": "application/json"})
            with urlopen(req) as resp:
                remote_meta = json.loads(resp.read().decode())
            self._update_meta(uuid, remote_meta.get("type", ""), remote_meta.get("description", ""))
        except HTTPError:
            pass

        return result

    # ------------------------------------------------------------------
    # class resolution
    # ------------------------------------------------------------------

    def _resolve_class(self, uuid: str):
        """Determine the object type from the metadata index and return its class."""
        meta = self._index.get(uuid)
        if meta is None:
            raise FileNotFoundError(f"No metadata for UUID {uuid}")
        type_name = meta.get("type")
        if type_name not in _CLASS_REGISTRY:
            raise ValueError(
                f"Unknown object type '{type_name}' for UUID {uuid}. "
                f"Known types: {sorted(_CLASS_REGISTRY)}"
            )
        return _CLASS_REGISTRY[type_name]()

    # ------------------------------------------------------------------
    # metadata helpers
    # ------------------------------------------------------------------

    def _update_meta(self, uuid: str, type_name: str, message: str, owner: Optional[str] = None) -> None:
        """Update the metadata index for an object."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self._index.get(uuid)
        if existing:
            meta = {**existing}
            meta.pop("owner", None)  # owner is passed separately
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
        self._index.put(uuid, meta, owner=owner)
