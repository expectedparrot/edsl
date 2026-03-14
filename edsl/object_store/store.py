"""Global CAS object store."""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Callable, Optional, Type

import platformdirs

from .cas_repository import CASRepository
from .exceptions import AmbiguousUUIDError
from .fs_backend import FileSystemBackend
from .sqlite_metadata_index import SQLiteMetadataIndex

_MIN_PREFIX_LENGTH = 4

# ---------------------------------------------------------------------------
# Storable class registry
# ---------------------------------------------------------------------------

# Map type-name strings (stored in metadata index) to the class that can
# deserialize the JSONL content.  Lazy — entries are callables that
# return the class.
_CLASS_REGISTRY: dict[str, Callable[[], Type]] = {
    "AgentList": lambda: _lazy_import("edsl.agents.agent_list", "AgentList"),
    "Cache": lambda: _lazy_import("edsl.caching.cache", "Cache"),
    "ScenarioList": lambda: _lazy_import("edsl.scenarios.scenario_list", "ScenarioList"),
    "ModelList": lambda: _lazy_import("edsl.language_models.model_list", "ModelList"),
    "Survey": lambda: _lazy_import("edsl.surveys.survey", "Survey"),
    "Jobs": lambda: _lazy_import("edsl.jobs.jobs", "Jobs"),
    "Results": lambda: _lazy_import("edsl.results.results", "Results"),
    "QuestionBase": lambda: _lazy_import("edsl.questions.question_base", "QuestionBase"),
    "Agent": lambda: _lazy_import("edsl.agents.agent", "Agent"),
    "Scenario": lambda: _lazy_import("edsl.scenarios.scenario", "Scenario"),
    "Instruction": lambda: _lazy_import("edsl.instructions.instruction", "Instruction"),
    "Study": lambda: _lazy_import("edsl.study.study", "Study"),
}


def _lazy_import(module_path: str, class_name: str):
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def register_storable(type_name: str, module_path: str, class_name: str) -> None:
    """Register an additional storable class at runtime.

    Example::

        register_storable("MyList", "mypackage.mymodule", "MyList")
    """
    _CLASS_REGISTRY[type_name] = lambda: _lazy_import(module_path, class_name)


# ---------------------------------------------------------------------------
# Blob reference discovery for sync
# ---------------------------------------------------------------------------

def _discover_blob_refs(content: str) -> list[str]:
    """Return blob hashes referenced in JSONL content via FileStore offloading.

    Inspects the ``__header__`` line for a ``has_blobs`` flag, then scans
    data rows for ``__cas_blob__`` sentinel values.  Returns an empty list
    if there are no blob references.
    """
    hashes: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        if row.get("__header__"):
            if not row.get("has_blobs"):
                return []  # header says no blobs — short-circuit
            continue
        for val in row.values():
            if (
                isinstance(val, dict)
                and val.get("base64_string") == "__cas_blob__"
                and "__blob_hash__" in val
            ):
                hashes.append(val["__blob_hash__"])
    return hashes


# ---------------------------------------------------------------------------
# Sync helpers
# ---------------------------------------------------------------------------

def _resolve_sync_branch(source, branch: Optional[str]) -> tuple[str, str]:
    """Resolve the branch name and tip commit hash from the source backend.

    Returns ``(branch_name, tip_commit_hash)``.
    """
    if branch is not None:
        ref_key = f"refs/{branch}"
        if not source.exists(ref_key):
            raise FileNotFoundError(f"Branch '{branch}' does not exist on source")
        tip = source.read(ref_key).strip()
        return branch, tip

    if not source.exists("HEAD"):
        raise FileNotFoundError("No HEAD on source — nothing to sync")
    head_branch = source.read("HEAD").strip()
    tip = source.read(f"refs/{head_branch}").strip()
    return head_branch, tip

def _sync_commit(source, dest, commit_hash: str) -> dict:
    """Copy a single commit and its tree/blob from source to dest.

    Returns a dict with counts of copied objects (``blobs``, ``trees``,
    ``commits``) and the list of file-blob hashes referenced in the content.
    """
    copied = {"blobs": 0, "trees": 0, "commits": 0}

    commit_key = f"commits/{commit_hash}.json"
    commit_content = source.read(commit_key)
    commit_obj = json.loads(commit_content)

    # Copy tree
    tree_key = f"trees/{commit_obj['tree']}.json"
    if not dest.exists(tree_key):
        dest.write(tree_key, source.read(tree_key))
        copied["trees"] += 1

    # Copy all row blobs referenced by the tree
    tree_obj = json.loads(source.read(tree_key))
    rows = []
    for blob_hash in tree_obj["blobs"]:
        blob_key = f"blobs/{blob_hash}.json"
        row = source.read(blob_key)
        rows.append(row)
        if not dest.exists(blob_key):
            dest.write(blob_key, row)
            copied["blobs"] += 1

    # Discover FileStore blob references embedded in row content
    content = "\n".join(rows) + "\n"
    blob_refs = _discover_blob_refs(content)

    # Copy referenced file blobs
    for blob_hash in blob_refs:
        fb_key = f"blobs/{blob_hash}.json"
        if not dest.exists(fb_key):
            dest.write(fb_key, source.read(fb_key))
            copied["blobs"] += 1

    # Copy commit itself
    dest.write(commit_key, commit_content)
    copied["commits"] += 1

    return {**copied, "parent": commit_obj.get("parent")}


def _update_dest_refs(dest, branch: str, tip: str) -> None:
    """Update ref, HEAD, and current.jsonl snapshot on the destination."""
    dest.write(f"refs/{branch}", tip + "\n")
    dest.write("HEAD", branch + "\n")

    # Reconstruct current.jsonl from the tip commit
    tip_commit = json.loads(dest.read(f"commits/{tip}.json"))
    tip_tree = json.loads(dest.read(f"trees/{tip_commit['tree']}.json"))
    rows = [dest.read(f"blobs/{h}.json") for h in tip_tree["blobs"]]
    dest.write("current.jsonl", "\n".join(rows) + "\n")


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

    DEFAULT_ROOT = Path(platformdirs.user_data_dir("edsl")) / "objects"

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

    def resolve_uuid(self, prefix: str) -> str:
        """Resolve a UUID prefix **or alias** to a full UUID.

        Accepts full UUIDs (returned as-is), unique prefixes of at
        least ``_MIN_PREFIX_LENGTH`` characters, or an alias string.
        Raises :class:`AmbiguousUUIDError` when the prefix matches more
        than one object, and :class:`FileNotFoundError` when it matches
        none.
        """
        # Full UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx) -- skip query
        if len(prefix) == 36 and prefix.count("-") == 4:
            return prefix

        # Try alias lookup first (aliases can be shorter than _MIN_PREFIX_LENGTH)
        alias_uuid = self._index.resolve_alias(prefix)
        if alias_uuid is not None:
            return alias_uuid

        if len(prefix) < _MIN_PREFIX_LENGTH:
            raise ValueError(
                f"UUID prefix must be at least {_MIN_PREFIX_LENGTH} characters "
                f"(got {len(prefix)})"
            )
        matches = self._index.resolve_prefix(prefix)
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise FileNotFoundError(
                f"No object with UUID prefix or alias '{prefix}' in store"
            )
        raise AmbiguousUUIDError(prefix, matches)

    # ------------------------------------------------------------------
    # core operations
    # ------------------------------------------------------------------

    def save(
        self,
        obj,
        message: str = "",
        branch: Optional[str] = None,
        uuid: Optional[str] = None,
        expected_tip: Optional[str] = None,
        owner: Optional[str] = None,
        title: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """Save an object to CAS.

        Returns a dict with ``uuid``, ``commit``, ``tree``, ``branch``,
        ``parent``, ``timestamp``, and ``message``.

        Args:
            obj: The object to save.  Must provide ``to_jsonl() -> str``.
            message: Commit message.
            branch: Target branch (default: current HEAD branch).
            uuid: Existing UUID to reuse, or *None* to auto-assign.
            expected_tip: If given, the branch tip must still point at
                this commit (compare-and-swap).  Otherwise
                :class:`StaleBranchError` is raised.
        """
        uuid = uuid or str(uuid4())
        backend = self._backend_factory(uuid)
        repo = CASRepository(self.root / uuid, backend=backend)

        # Create a blob_writer that stores FileStore blobs directly
        # into the CAS backend's blobs/ namespace for deduplication.
        def blob_writer(base64_content: str) -> str:
            h = hashlib.sha256(base64_content.encode()).hexdigest()
            key = f"blobs/{h}.json"
            if not backend.exists(key):
                backend.write(key, base64_content)
            return h

        rows = list(obj.to_jsonl_rows(blob_writer=blob_writer))

        info = repo.save(
            rows,
            message=message,
            branch=branch,
            expected_tip=expected_tip,
        )

        # Update metadata index
        type_name = getattr(obj, "_store_class_name", None) or type(obj).__name__
        self._update_meta(
            uuid, type_name, description or message, owner=owner,
            title=title, alias=alias, visibility=visibility,
        )

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
        """Load an object by UUID (or unique prefix). Defaults to HEAD.

        Returns a tuple ``(obj, meta)`` where *meta* is a dict with
        ``uuid``, ``commit``, and ``branch`` so the caller can track
        CAS state however it likes.
        """
        uuid = self.resolve_uuid(uuid)
        repo = self._repo(uuid)
        content = repo.load(commit=commit, branch=branch)
        cls = self._resolve_class(uuid)
        backend = repo._backend

        # Create a blob_reader that resolves FileStore blob references
        # from the CAS backend's blobs/ namespace.
        def blob_reader(hash_hex: str) -> str:
            return backend.read(f"blobs/{hash_hex}.json")

        obj = cls.from_jsonl(content, blob_reader=blob_reader)

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
        uuid = self.resolve_uuid(uuid)
        indexed = self._index.log(uuid, branch=branch)
        if indexed:
            return indexed
        # Fallback for objects not yet indexed
        return self._repo(uuid).log(commit=commit, branch=branch)

    def diff(
        self,
        uuid: str,
        ref_a: str = None,
        ref_b: str = None,
        branch: Optional[str] = None,
        context: int = 3,
    ):
        """Compute a unified diff between two versions of an object.

        Follows git conventions:

        - ``diff()``                   — HEAD~1 → HEAD (last change)
        - ``diff("HEAD~2")``           — HEAD~2 → HEAD (two commits back)
        - ``diff("abc123")``           — abc123 → HEAD
        - ``diff("abc123", "def456")`` — abc123 → def456

        Returns a :class:`StoreDiffInfo` (a ``str`` subclass with ANSI
        colour in ``__repr__`` and HTML in ``_repr_html_``).
        """
        from .store_info import StoreDiffInfo

        uuid = self.resolve_uuid(uuid)
        history = self.log(uuid, branch=branch)   # newest-first
        if not history:
            raise ValueError(f"No commit history for UUID {uuid}")

        def _resolve_ref(ref):
            """Resolve a ref spec to a concrete commit hash."""
            if ref is None or ref == "HEAD":
                return history[0]["hash"]
            if isinstance(ref, str) and ref.upper().startswith("HEAD~"):
                try:
                    n = int(ref.split("~", 1)[1])
                except ValueError:
                    raise ValueError(f"Invalid HEAD~N ref: {ref!r}")
                if n >= len(history):
                    raise IndexError(
                        f"{ref} does not exist; history has {len(history)} "
                        f"commit(s)"
                    )
                return history[n]["hash"]
            # Treat as a commit-hash prefix
            candidates = [e["hash"] for e in history if e["hash"].startswith(ref)]
            if not candidates:
                raise FileNotFoundError(f"No commit with prefix {ref!r} in history")
            if len(candidates) > 1:
                raise ValueError(f"Ambiguous commit prefix {ref!r}: {candidates}")
            return candidates[0]

        # Follow git conventions:
        #   diff()           → HEAD~1 (old) → HEAD (new)
        #   diff("HEAD~2")   → HEAD~2 (old) → HEAD (new)
        #   diff("abc", "def") → abc (old) → def (new)
        if ref_a is None and ref_b is None:
            commit_old = _resolve_ref("HEAD~1")
            commit_new = _resolve_ref(None)       # HEAD
        elif ref_b is None:
            commit_old = _resolve_ref(ref_a)      # first arg = old
            commit_new = _resolve_ref(None)       # HEAD
        else:
            commit_old = _resolve_ref(ref_a)      # first arg = old
            commit_new = _resolve_ref(ref_b)      # second arg = new

        obj_old, _ = self.load(uuid, commit=commit_old)
        obj_new, _ = self.load(uuid, commit=commit_new)

        yaml_old = obj_old.to_yaml().splitlines(keepends=True)
        yaml_new = obj_new.to_yaml().splitlines(keepends=True)

        import difflib
        diff_lines = list(difflib.unified_diff(
            yaml_old,
            yaml_new,
            fromfile=f"commit {commit_old[:12]}",
            tofile=f"commit {commit_new[:12]}",
            n=context,
        ))
        diff_text = "".join(diff_lines) or "(no differences)\n"

        return StoreDiffInfo(diff_text, commit_a=commit_new, commit_b=commit_old)

    def branches(self, uuid: str) -> list[str]:
        """List branches for an object."""
        uuid = self.resolve_uuid(uuid)
        return self._repo(uuid).branches()

    def branch(self, uuid: str, name: str, from_branch: Optional[str] = None) -> None:
        """Create a new branch for an object."""
        uuid = self.resolve_uuid(uuid)
        self._repo(uuid).branch(name, from_branch=from_branch)

    def checkout(self, uuid: str, branch: str) -> None:
        """Switch an object's HEAD to the given branch."""
        uuid = self.resolve_uuid(uuid)
        self._repo(uuid).checkout(branch)
        
    def list(self) -> list[dict]:
        """List all objects in the store."""
        return self._index.list_all()

    def delete(self, uuid: str) -> None:
        """Remove an object and its history from the store."""
        uuid = self.resolve_uuid(uuid)
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
        branch, tip = _resolve_sync_branch(source, branch)

        totals = {"blobs": 0, "trees": 0, "commits": 0}
        commit_hash = tip
        while commit_hash:
            commit_key = f"commits/{commit_hash}.json"
            if dest.exists(commit_key):
                break  # already have this commit and all ancestors

            result = _sync_commit(source, dest, commit_hash)
            for k in ("blobs", "trees", "commits"):
                totals[k] += result[k]
            commit_hash = result["parent"]

        _update_dest_refs(dest, branch, tip)

        return {"commit": tip, "branch": branch, **totals}

    def push(self, uuid: str, remote_url: str, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
        """Push a local object to a remote CAS service.

        Args:
            uuid: The local object UUID (or unique prefix) to push.
            remote_url: Base URL of the remote CAS service.
            branch: Branch to push (default: HEAD branch).
            token: Bearer token for authentication.

        Returns:
            A dict with sync results.
        """
        from .http_backend import HttpBackend

        uuid = self.resolve_uuid(uuid)
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
                "title": meta.get("title", ""),
                "alias": meta.get("alias"),
                "visibility": meta.get("visibility", "private"),
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
        try:
            remote_meta = remote_backend.get_metadata()
            self._update_meta(
                uuid,
                remote_meta.get("type", ""),
                remote_meta.get("description", ""),
                title=remote_meta.get("title"),
                alias=remote_meta.get("alias"),
                visibility=remote_meta.get("visibility"),
            )
        except (KeyError, OSError):
            pass  # remote may not support metadata endpoint

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

    def _update_meta(
        self,
        uuid: str,
        type_name: str,
        message: str,
        owner: Optional[str] = None,
        title: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = None,
    ) -> None:
        """Update the metadata index for an object."""
        now = datetime.now(timezone.utc).isoformat()
        existing = self._index.get(uuid)
        if existing:
            meta = {**existing}
            meta.pop("owner", None)  # owner is passed separately
            meta["last_modified"] = now
            if message:
                meta["description"] = message
            if title is not None:
                meta["title"] = title
            if alias is not None:
                meta["alias"] = alias
            if visibility is not None:
                meta["visibility"] = visibility
        else:
            meta = {
                "type": type_name,
                "description": message,
                "created": now,
                "last_modified": now,
                "title": title or "",
                "alias": alias,
                "visibility": visibility or "private",
            }
        self._index.put(uuid, meta, owner=owner)

    def update_metadata(self, uuid: str, **kwargs) -> None:
        """Update metadata fields without creating a commit."""
        uuid = self.resolve_uuid(uuid)
        self._index.update_metadata(uuid, **kwargs)

    def get_by_alias(self, owner: str, alias: str):
        """Look up and load an object by owner/alias."""
        meta = self._index.get_by_alias(owner, alias)
        if meta is None:
            raise FileNotFoundError(f"No object with alias '{owner}/{alias}'")
        return self.load(meta["uuid"])
