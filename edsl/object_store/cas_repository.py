"""Generic content-addressable storage repository (git-like).

No imports from agents/ or any other EDSL domain module — this is pure
infrastructure that any serializable class can use.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

from .exceptions import StaleBranchError


def _reconstruct_content(b, tree_obj: dict) -> str:
    """Reconstruct the full JSONL string from a tree object."""
    parts = [b.read(f"blobs/{h}.json") for h in tree_obj["blobs"]]
    return "\n".join(parts) + "\n"


class CASRepository:
    """Git-like content-addressable storage for a single directory.

    Layout::

        <dir>/blobs/<hash>.json
        <dir>/trees/<hash>.json
        <dir>/commits/<hash>.json
        <dir>/refs/<branch>
        <dir>/HEAD
        <dir>/current.jsonl

    Accepts an optional *backend* (:class:`StorageBackend` protocol) to
    abstract file I/O.  Defaults to :class:`FileSystemBackend` rooted at
    *directory*.

    Examples:
        >>> import tempfile
        >>> repo = CASRepository(tempfile.mkdtemp())
        >>> info1 = repo.save(["hello", "world"], message="first")
        >>> info1['branch']
        'main'
        >>> 'tree' in info1
        True
        >>> repo.load() == "hello\\nworld\\n"
        True
        >>> info2 = repo.save(["updated"], message="second")
        >>> info2['parent'] == info1['commit']
        True
        >>> repo.load() == "updated\\n"
        True
        >>> repo.load(commit=info1['commit']) == "hello\\nworld\\n"
        True
        >>> len(repo.log()) == 2
        True
        >>> repo.branch("experiment")
        >>> repo.checkout("experiment")
        >>> info3 = repo.save(["experiment data"], message="on branch")
        >>> info3['branch']
        'experiment'
        >>> repo.load(branch="main") == "updated\\n"
        True
        >>> repo.load(branch="experiment") == "experiment data\\n"
        True
        >>> sorted(repo.branches())
        ['experiment', 'main']
    """

    def __init__(self, directory: Union[str, Path], backend=None) -> None:
        self.directory = Path(directory)
        if backend is not None:
            self._backend = backend
        else:
            from .fs_backend import FileSystemBackend

            self._backend = FileSystemBackend(self.directory)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def save(
        self,
        rows: List[str],
        message: str = "",
        branch: Optional[str] = None,
        expected_tip: Optional[str] = None,
    ) -> dict:
        """Store *rows* (one string per JSONL row) as a new commit.

        Each row is stored as its own content-addressed blob.  The tree
        object records the ordered list of blob hashes so the full JSONL
        can be reconstructed on load.

        If *expected_tip* is set the branch tip must match it exactly,
        otherwise :class:`StaleBranchError` is raised.  This gives
        compare-and-swap semantics at the repository level.

        Returns:
            A dict with ``commit``, ``tree``, ``branch``, ``parent``,
            ``timestamp``, and ``message``.
        """
        b = self._backend

        # Determine which branch to commit to
        if b.exists("HEAD"):
            current_branch = self.head_branch()
            if branch is not None and branch != current_branch:
                b.write("HEAD", branch + "\n")
                current_branch = branch
        else:
            current_branch = branch or "main"

        # One blob per row — deduplicated by content hash
        blob_hashes = []
        for row in rows:
            h = self._hash(row)
            key = f"blobs/{h}.json"
            if not b.exists(key):
                b.write(key, row)
            blob_hashes.append(h)

        # tree — ordered list of blob hashes
        tree_obj = {"blobs": blob_hashes}
        tree_content = json.dumps(tree_obj, sort_keys=True)
        tree_hash = self._hash(tree_content)
        tree_key = f"trees/{tree_hash}.json"
        if not b.exists(tree_key):
            b.write(tree_key, tree_content)

        # commit
        parent: Optional[str] = None
        ref_key = f"refs/{current_branch}"
        if b.exists(ref_key):
            parent = b.read(ref_key).strip() or None

        # Compare-and-swap: reject if branch tip moved since caller last read
        if expected_tip is not None and parent != expected_tip:
            raise StaleBranchError(
                branch=current_branch,
                expected=expected_tip,
                actual=parent or "(no commits)",
            )

        timestamp = datetime.now(timezone.utc).isoformat()
        commit_obj = {
            "tree": tree_hash,
            "parent": parent,
            "timestamp": timestamp,
            "message": message,
        }
        commit_content = json.dumps(commit_obj, sort_keys=True)
        commit_hash = self._hash(commit_content)
        b.write(f"commits/{commit_hash}.json", commit_content)

        # update branch ref and HEAD
        b.write(ref_key, commit_hash + "\n")
        b.write("HEAD", current_branch + "\n")

        # overwrite readable snapshot
        b.write("current.jsonl", _reconstruct_content(b, tree_obj))

        return {
            "commit": commit_hash,
            "tree": tree_hash,
            "branch": current_branch,
            "parent": parent,
            "timestamp": timestamp,
            "message": message,
        }

    def load(
        self,
        commit: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> str:
        """Load content string from a commit. Defaults to HEAD."""
        b = self._backend
        commit_hash = self.resolve(commit, branch)
        commit_obj = json.loads(b.read(f"commits/{commit_hash}.json"))
        tree_obj = json.loads(b.read(f"trees/{commit_obj['tree']}.json"))
        return _reconstruct_content(b, tree_obj)

    def log(
        self,
        commit: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> List[dict]:
        """Walk the commit chain and return the history (newest first)."""
        b = self._backend
        current: Optional[str] = self.resolve(commit, branch)
        history: list[dict] = []
        while current:
            commit_obj = json.loads(b.read(f"commits/{current}.json"))
            history.append({"hash": current, **commit_obj})
            current = commit_obj.get("parent")
        return history

    def branches(self) -> List[str]:
        """List all branch names."""
        return sorted(
            key.split("/", 1)[1]
            for key in self._backend.list_prefix("refs/")
        )

    def branch(self, name: str, from_branch: Optional[str] = None) -> None:
        """Create a new branch pointing at the same commit as *from_branch*.

        Does NOT switch HEAD.
        """
        b = self._backend
        ref_key = f"refs/{name}"
        if b.exists(ref_key):
            raise ValueError(f"Branch '{name}' already exists")

        if from_branch is not None:
            source_key = f"refs/{from_branch}"
            if not b.exists(source_key):
                raise FileNotFoundError(
                    f"Source branch '{from_branch}' does not exist"
                )
            commit_hash = b.read(source_key).strip()
        else:
            commit_hash = self._resolve_head()

        b.write(ref_key, commit_hash + "\n")

    def checkout(self, branch: str) -> None:
        """Switch HEAD to the given branch and update current.jsonl."""
        b = self._backend
        if not b.exists(f"refs/{branch}"):
            raise FileNotFoundError(f"Branch '{branch}' does not exist")

        b.write("HEAD", branch + "\n")

        # Update current.jsonl to reflect the branch tip
        content = self.load(branch=branch)
        b.write("current.jsonl", content)

    # ------------------------------------------------------------------
    # public helpers (formerly private)
    # ------------------------------------------------------------------

    def head_branch(self) -> Optional[str]:
        """Return the current branch name, or None if HEAD doesn't exist."""
        b = self._backend
        if not b.exists("HEAD"):
            return None
        return b.read("HEAD").strip() or None

    def resolve(
        self,
        commit: Optional[str],
        branch: Optional[str] = None,
    ) -> str:
        """Resolve a commit/branch specification to a concrete commit hash."""
        if commit is not None:
            return commit
        if branch is not None:
            ref_key = f"refs/{branch}"
            if not self._backend.exists(ref_key):
                raise FileNotFoundError(
                    f"Branch '{branch}' does not exist"
                )
            return self._backend.read(ref_key).strip()
        return self._resolve_head()

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(content: str) -> str:
        """SHA-256 hex digest of a string."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _resolve_head(self) -> str:
        """Resolve HEAD -> commit hash via refs/."""
        b = self._backend
        if not b.exists("HEAD"):
            raise FileNotFoundError(
                f"No HEAD in CAS directory: {self.directory}"
            )
        branch = b.read("HEAD").strip()
        if not branch:
            raise FileNotFoundError(
                f"HEAD is empty in CAS directory: {self.directory}"
            )
        ref_key = f"refs/{branch}"
        if not b.exists(ref_key):
            raise FileNotFoundError(
                f"Branch '{branch}' referenced by HEAD does not exist"
            )
        return b.read(ref_key).strip()


if __name__ == "__main__":
    import doctest

    doctest.testmod()
