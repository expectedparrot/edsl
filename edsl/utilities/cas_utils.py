"""Utilities for inspecting CAS (content-addressable storage) repositories."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Union


def cas_tree(directory: Union[str, Path]) -> str:
    """Return an ASCII tree representation of a CAS directory.

    >>> import tempfile
    >>> from edsl.object_store import CASRepository
    >>> d = tempfile.mkdtemp()
    >>> repo = CASRepository(d)
    >>> _ = repo.save("hello\\n", message="test")
    >>> len(cas_tree(d)) > 0
    True
    """
    directory = Path(directory)

    def _walk(path, prefix=""):
        lines = []
        entries = sorted(os.listdir(path))
        for i, entry in enumerate(entries):
            full = path / entry
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            if full.is_dir():
                count = len(os.listdir(full))
                lines.append(f"{prefix}{connector}{entry}/ ({count} files)")
                extension = "    " if is_last else "│   "
                lines.extend(_walk(full, prefix + extension))
            else:
                lines.append(f"{prefix}{connector}{entry}")
        return lines

    name = directory.name
    lines = [f"{name}/"] + _walk(directory)
    return "\n".join(lines)


def cas_blobs(directory: Union[str, Path]) -> list[dict]:
    """Return a list of blob summaries from a CAS directory.

    Each dict has keys ``hash`` (short) and ``size`` (character count).

    >>> import tempfile
    >>> from edsl.object_store import CASRepository
    >>> d = tempfile.mkdtemp()
    >>> repo = CASRepository(d)
    >>> _ = repo.save("hello\\n", message="test")
    >>> blobs = cas_blobs(d)
    >>> len(blobs)
    1
    """
    directory = Path(directory)
    blobs_dir = directory / "blobs"
    if not blobs_dir.exists():
        return []
    result = []
    for f in sorted(os.listdir(blobs_dir)):
        content = (blobs_dir / f).read_text()
        result.append({
            "hash": f.replace(".json", "")[:16],
            "size": len(content),
        })
    return result


def cas_status(directory: Union[str, Path]) -> dict:
    """Return a summary dict of the current CAS repo state.

    Keys: ``head``, ``num_commits``, ``num_blobs``, ``num_trees``.

    >>> import tempfile
    >>> from edsl.object_store import CASRepository
    >>> d = tempfile.mkdtemp()
    >>> repo = CASRepository(d)
    >>> _ = repo.save("hello\\n", message="test")
    >>> s = cas_status(d)
    >>> s['num_commits']
    1
    >>> s['num_blobs']
    1
    """
    directory = Path(directory)
    head_branch = (directory / "HEAD").read_text().strip()
    ref_path = directory / "refs" / head_branch
    commit_hash = ref_path.read_text().strip() if ref_path.exists() else head_branch
    return {
        "head": commit_hash[:16],
        "num_commits": len(os.listdir(directory / "commits")),
        "num_blobs": len(os.listdir(directory / "blobs")),
        "num_trees": len(os.listdir(directory / "trees")),
    }


def cas_diff(
    directory: Union[str, Path],
    commit_a: Optional[str] = None,
    commit_b: Optional[str] = None,
) -> dict:
    """Compare two commits and return whether the blob changed.

    Defaults: *commit_a* is the parent of HEAD, *commit_b* is HEAD.
    Returns a dict with keys ``changed`` (bool) and ``blob_a``, ``blob_b``
    (short hashes).

    >>> import tempfile
    >>> from edsl.object_store import CASRepository
    >>> d = tempfile.mkdtemp()
    >>> repo = CASRepository(d)
    >>> _ = repo.save("v1\\n", message="v1")
    >>> _ = repo.save("v2\\n", message="v2")
    >>> diff = cas_diff(d)
    >>> diff['changed']
    True
    """
    from edsl.object_store import CASRepository

    directory = Path(directory)
    repo = CASRepository(directory)

    if commit_b is None:
        commit_b = repo.resolve(None)
    if commit_a is None:
        commit_obj = json.loads(
            (directory / "commits" / f"{commit_b}.json").read_text()
        )
        commit_a = commit_obj.get("parent")

    def _get_blob(commit_hash):
        if commit_hash is None:
            return None
        commit_obj = json.loads(
            (directory / "commits" / f"{commit_hash}.json").read_text()
        )
        tree_obj = json.loads(
            (directory / "trees" / f"{commit_obj['tree']}.json").read_text()
        )
        return tree_obj["blob"]

    blob_a = _get_blob(commit_a)
    blob_b = _get_blob(commit_b)

    return {
        "changed": blob_a != blob_b,
        "blob_a": blob_a[:16] if blob_a else None,
        "blob_b": blob_b[:16] if blob_b else None,
    }


def cas_summary(directory: Union[str, Path]) -> str:
    """Return a human-readable summary of the CAS repo.

    Combines status, log, and blob listing into one string suitable
    for display or printing.

    >>> import tempfile
    >>> from edsl.object_store import CASRepository
    >>> d = tempfile.mkdtemp()
    >>> repo = CASRepository(d)
    >>> _ = repo.save("hello\\n", message="first commit")
    >>> print(cas_summary(d))  # doctest: +ELLIPSIS
    CAS Repository...
    """
    from edsl.object_store import CASRepository

    directory = Path(directory)
    status = cas_status(directory)
    log = CASRepository(directory).log()
    blobs = cas_blobs(directory)

    lines = [
        f"CAS Repository: {directory}",
        f"HEAD: {status['head']}...",
        f"Commits: {status['num_commits']}  Blobs: {status['num_blobs']}  Trees: {status['num_trees']}",
        "",
        "Log:",
    ]
    for entry in log:
        parent = entry["parent"]
        parent_str = parent[:12] + "..." if parent else "(root)"
        lines.append(
            f"  {entry['hash'][:12]}...  parent={parent_str}  {entry['message']}"
        )

    lines.append("")
    lines.append("Blobs:")
    for b in blobs:
        lines.append(f"  {b['hash']}...  size={b['size']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
