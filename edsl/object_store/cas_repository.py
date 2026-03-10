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


class CASRepository:
    """Git-like content-addressable storage for a single directory.

    Layout::

        <dir>/blobs/<hash>.json
        <dir>/trees/<hash>.json
        <dir>/commits/<hash>.json
        <dir>/refs/<branch>
        <dir>/HEAD
        <dir>/current.jsonl

    Examples:
        >>> import tempfile
        >>> repo = CASRepository(tempfile.mkdtemp())
        >>> info1 = repo.save("hello\\nworld\\n", message="first")
        >>> info1['branch']
        'main'
        >>> repo.load() == "hello\\nworld\\n"
        True
        >>> info2 = repo.save("updated\\n", message="second")
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
        >>> info3 = repo.save("experiment data\\n", message="on branch")
        >>> info3['branch']
        'experiment'
        >>> repo.load(branch="main") == "updated\\n"
        True
        >>> repo.load(branch="experiment") == "experiment data\\n"
        True
        >>> sorted(repo.branches())
        ['experiment', 'main']
    """

    def __init__(self, directory: Union[str, Path]) -> None:
        self.directory = Path(directory)

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def save(
        self,
        content: str,
        message: str = "",
        branch: Optional[str] = None,
        expected_parent: Optional[str] = None,
    ) -> dict:
        """Store *content* as a new commit.

        If *expected_parent* is set the branch tip must match it exactly,
        otherwise :class:`StaleBranchError` is raised.  This gives
        compare-and-swap semantics at the repository level.

        Returns:
            A dict with ``commit``, ``branch``, ``parent``, ``timestamp``,
            and ``message``.
        """
        directory = self.directory
        head_path = directory / "HEAD"

        # Determine which branch to commit to
        if head_path.exists():
            current_branch = self.head_branch()
            if branch is not None and branch != current_branch:
                self._write(head_path, branch + "\n")
                current_branch = branch
        else:
            current_branch = branch or "main"

        # blob
        blob_hash = self._hash(content)
        blob_path = directory / "blobs" / f"{blob_hash}.json"
        if not blob_path.exists():
            self._write(blob_path, content)

        # tree — single-blob reference
        tree_obj = {"blob": blob_hash}
        tree_content = json.dumps(tree_obj, sort_keys=True)
        tree_hash = self._hash(tree_content)
        tree_path = directory / "trees" / f"{tree_hash}.json"
        if not tree_path.exists():
            self._write(tree_path, tree_content)

        # commit
        parent: Optional[str] = None
        ref_path = directory / "refs" / current_branch
        if ref_path.exists():
            parent = ref_path.read_text().strip() or None

        # Compare-and-swap: reject if branch tip moved since caller last read
        if expected_parent is not None and parent != expected_parent:
            raise StaleBranchError(
                branch=current_branch,
                expected=expected_parent,
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
        self._write(directory / "commits" / f"{commit_hash}.json", commit_content)

        # update branch ref and HEAD
        self._write(ref_path, commit_hash + "\n")
        self._write(head_path, current_branch + "\n")

        # overwrite readable snapshot
        self._write(directory / "current.jsonl", content)

        return {
            "commit": commit_hash,
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
        commit_hash = self.resolve(commit, branch)
        commit_obj = json.loads(
            (self.directory / "commits" / f"{commit_hash}.json").read_text()
        )
        tree_obj = json.loads(
            (self.directory / "trees" / f"{commit_obj['tree']}.json").read_text()
        )
        blob_hash = tree_obj["blob"]
        return (self.directory / "blobs" / f"{blob_hash}.json").read_text()

    def log(
        self,
        commit: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> List[dict]:
        """Walk the commit chain and return the history (newest first)."""
        current: Optional[str] = self.resolve(commit, branch)
        history: list[dict] = []
        while current:
            commit_obj = json.loads(
                (self.directory / "commits" / f"{current}.json").read_text()
            )
            history.append({"hash": current, **commit_obj})
            current = commit_obj.get("parent")
        return history

    def branches(self) -> List[str]:
        """List all branch names."""
        refs_dir = self.directory / "refs"
        if not refs_dir.exists():
            return []
        return sorted(f.name for f in refs_dir.iterdir() if f.is_file())

    def branch(self, name: str, from_branch: Optional[str] = None) -> None:
        """Create a new branch pointing at the same commit as *from_branch*.

        Does NOT switch HEAD.
        """
        ref_path = self.directory / "refs" / name
        if ref_path.exists():
            raise ValueError(f"Branch '{name}' already exists")

        if from_branch is not None:
            source_ref = self.directory / "refs" / from_branch
            if not source_ref.exists():
                raise FileNotFoundError(
                    f"Source branch '{from_branch}' does not exist"
                )
            commit_hash = source_ref.read_text().strip()
        else:
            commit_hash = self._resolve_head()

        self._write(ref_path, commit_hash + "\n")

    def checkout(self, branch: str) -> None:
        """Switch HEAD to the given branch and update current.jsonl."""
        ref_path = self.directory / "refs" / branch
        if not ref_path.exists():
            raise FileNotFoundError(f"Branch '{branch}' does not exist")

        self._write(self.directory / "HEAD", branch + "\n")

        # Update current.jsonl to reflect the branch tip
        content = self.load(branch=branch)
        self._write(self.directory / "current.jsonl", content)

    # ------------------------------------------------------------------
    # public helpers (formerly private)
    # ------------------------------------------------------------------

    def head_branch(self) -> Optional[str]:
        """Return the current branch name, or None if HEAD doesn't exist."""
        head_path = self.directory / "HEAD"
        if not head_path.exists():
            return None
        return head_path.read_text().strip() or None

    def resolve(
        self,
        commit: Optional[str],
        branch: Optional[str] = None,
    ) -> str:
        """Resolve a commit/branch specification to a concrete commit hash."""
        if commit is not None:
            return commit
        if branch is not None:
            ref_path = self.directory / "refs" / branch
            if not ref_path.exists():
                raise FileNotFoundError(
                    f"Branch '{branch}' does not exist: {ref_path}"
                )
            return ref_path.read_text().strip()
        return self._resolve_head()

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash(content: str) -> str:
        """SHA-256 hex digest of a string."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _write(path: Path, content: str) -> None:
        """Write *content* to *path*, creating parent dirs as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _resolve_head(self) -> str:
        """Resolve HEAD → commit hash via refs/."""
        head_path = self.directory / "HEAD"
        if not head_path.exists():
            raise FileNotFoundError(
                f"No HEAD in CAS directory: {self.directory}"
            )
        branch = head_path.read_text().strip()
        if not branch:
            raise FileNotFoundError(
                f"HEAD is empty in CAS directory: {self.directory}"
            )
        ref_path = self.directory / "refs" / branch
        if not ref_path.exists():
            raise FileNotFoundError(
                f"Branch '{branch}' referenced by HEAD does not exist: {ref_path}"
            )
        return ref_path.read_text().strip()

    # Keep old names as aliases for backward compatibility within the package
    _head_branch = head_branch
    _resolve = resolve


if __name__ == "__main__":
    import doctest

    doctest.testmod()
