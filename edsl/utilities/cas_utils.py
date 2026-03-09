"""Utilities for inspecting CAS (content-addressable storage) repositories."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Union


def cas_tree(directory: Union[str, Path]) -> str:
    """Return an ASCII tree representation of a CAS directory.

    >>> import tempfile
    >>> from edsl import Agent, AgentList
    >>> al = AgentList([Agent(traits={'age': 22})])
    >>> d = al.to_cas(tempfile.mkdtemp(), message="test")
    >>> print(cas_tree(d))  # doctest: +ELLIPSIS
    agent_repo/...
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

    Each dict has keys ``hash`` (short) and ``traits``.

    >>> import tempfile
    >>> from edsl import Agent, AgentList
    >>> al = AgentList([Agent(traits={'age': 22})])
    >>> d = al.to_cas(tempfile.mkdtemp(), message="test")
    >>> blobs = cas_blobs(d)
    >>> len(blobs)
    1
    >>> 'age' in blobs[0]['traits']
    True
    """
    directory = Path(directory)
    blobs_dir = directory / "blobs"
    result = []
    for f in sorted(os.listdir(blobs_dir)):
        data = json.loads((blobs_dir / f).read_text())
        result.append({
            "hash": f.replace(".json", "")[:16],
            "traits": data.get("traits", {}),
        })
    return result


def cas_status(directory: Union[str, Path]) -> dict:
    """Return a summary dict of the current CAS repo state.

    Keys: ``head``, ``num_commits``, ``num_blobs``, ``num_trees``.

    >>> import tempfile
    >>> from edsl import Agent, AgentList
    >>> al = AgentList([Agent(traits={'age': 22})])
    >>> d = al.to_cas(tempfile.mkdtemp(), message="test")
    >>> s = cas_status(d)
    >>> s['num_commits']
    1
    >>> s['num_blobs']
    1
    """
    directory = Path(directory)
    head = (directory / "HEAD").read_text().strip()
    return {
        "head": head[:16],
        "num_commits": len(os.listdir(directory / "commits")),
        "num_blobs": len(os.listdir(directory / "blobs")),
        "num_trees": len(os.listdir(directory / "trees")),
    }


def cas_diff(
    directory: Union[str, Path],
    commit_a: Optional[str] = None,
    commit_b: Optional[str] = None,
) -> dict:
    """Compare two commits and return added/removed/unchanged blob hashes.

    Defaults: *commit_a* is the parent of HEAD, *commit_b* is HEAD.
    Returns a dict with keys ``added``, ``removed``, ``unchanged``,
    each a list of short hashes.

    >>> import tempfile
    >>> from edsl import Agent, AgentList
    >>> al = AgentList([Agent(traits={'age': 22})])
    >>> d = tempfile.mkdtemp()
    >>> al.to_cas(d, message="v1")  # doctest: +ELLIPSIS
    '...'
    >>> al2 = AgentList([Agent(traits={'age': 22}), Agent(traits={'age': 30})])
    >>> al2.to_cas(d, message="v2")  # doctest: +ELLIPSIS
    '...'
    >>> diff = cas_diff(d)
    >>> len(diff['added'])
    1
    >>> len(diff['unchanged'])
    1
    """
    directory = Path(directory)

    if commit_b is None:
        commit_b = (directory / "HEAD").read_text().strip()
    if commit_a is None:
        commit_obj = json.loads(
            (directory / "commits" / f"{commit_b}.json").read_text()
        )
        commit_a = commit_obj.get("parent")

    def _get_blob_set(commit_hash):
        if commit_hash is None:
            return set()
        commit_obj = json.loads(
            (directory / "commits" / f"{commit_hash}.json").read_text()
        )
        tree_obj = json.loads(
            (directory / "trees" / f"{commit_obj['tree']}.json").read_text()
        )
        return set(tree_obj["hashes"])

    blobs_a = _get_blob_set(commit_a)
    blobs_b = _get_blob_set(commit_b)

    return {
        "added": [h[:16] for h in sorted(blobs_b - blobs_a)],
        "removed": [h[:16] for h in sorted(blobs_a - blobs_b)],
        "unchanged": [h[:16] for h in sorted(blobs_a & blobs_b)],
    }


def cas_summary(directory: Union[str, Path]) -> str:
    """Return a human-readable summary of the CAS repo.

    Combines status, log, and blob listing into one string suitable
    for display or printing.

    >>> import tempfile
    >>> from edsl import Agent, AgentList
    >>> al = AgentList([Agent(traits={'age': 22})])
    >>> d = al.to_cas(tempfile.mkdtemp(), message="first commit")
    >>> print(cas_summary(d))  # doctest: +ELLIPSIS
    CAS Repository...
    """
    from edsl.agents.agent_list_serializer import AgentListSerializer

    directory = Path(directory)
    status = cas_status(directory)
    log = AgentListSerializer.cas_log(directory)
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
        lines.append(f"  {b['hash']}...  {b['traits']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
