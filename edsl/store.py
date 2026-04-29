"""High-level interface to the local EDSL object store.

Usage::

    from edsl import store
    store.list()          # Dataset of all stored objects
    store.save(my_agent)  # save an object
    store.load("abc123")  # load by UUID / prefix / alias
    store.info()          # store location & stats
"""

from __future__ import annotations

import builtins
from typing import Optional

from edsl.object_store.store import ObjectStore

_LIST_COLUMNS = [
    "uuid", "type", "title", "description",
    "created", "last_modified", "alias", "visibility",
]


def _default_store() -> ObjectStore:
    return ObjectStore()


def _rows_to_dataset(rows: list[dict], columns: list[str] | None = None) -> "Dataset":
    """Convert a list of dicts to a column-oriented Dataset."""
    from edsl.dataset import Dataset

    if not rows:
        return Dataset([])

    if columns:
        keys = columns + [k for k in rows[0] if k not in columns]
    else:
        keys = builtins.list(rows[0].keys())
    return Dataset([{k: [r.get(k) for r in rows]} for k in keys])


# ------------------------------------------------------------------
# Discovery
# ------------------------------------------------------------------

def info() -> "Dataset":
    """Return store location and basic stats as a Dataset."""
    from edsl.dataset import Dataset
    from collections import Counter

    s = _default_store()
    rows = s.list()
    type_counts = Counter(r.get("type") for r in rows)

    data = [{"key": [], "value": []}]
    entries = [
        ("path", str(s.root)),
        ("total_objects", len(rows)),
    ] + [(f"type.{t}", n) for t, n in sorted(type_counts.items())]

    data = [
        {"key": [e[0] for e in entries]},
        {"value": [e[1] for e in entries]},
    ]
    return Dataset(data)


def list(type: Optional[str] = None, query: Optional[str] = None) -> "Dataset":
    """Return a Dataset of metadata for all objects in the local store.

    Args:
        type: Filter by object type (e.g. "AgentList", "Survey").
        query: Text search across descriptions and titles.
    """
    s = _default_store()
    if type or query:
        rows = s._index.search(type_name=type, query=query)
    else:
        rows = s.list()
    return _rows_to_dataset(rows, _LIST_COLUMNS)


# ------------------------------------------------------------------
# Core CRUD
# ------------------------------------------------------------------

def save(
    obj,
    message: str = "",
    title: Optional[str] = None,
    alias: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
) -> dict:
    """Save an object to the store. Returns a dict with uuid, commit, etc."""
    return _default_store().save(
        obj, message=message, title=title, alias=alias,
        description=description, visibility=visibility,
    )


def load(uuid: str, commit: Optional[str] = None, branch: Optional[str] = None):
    """Load an object by UUID, prefix, or alias. Returns the object."""
    obj, _meta = _default_store().load(uuid, commit=commit, branch=branch)
    return obj


def delete(uuid: str) -> None:
    """Delete an object from the store."""
    _default_store().delete(uuid)


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

def log(uuid: str, branch: Optional[str] = None) -> "Dataset":
    """Return commit history for an object as a Dataset."""
    rows = _default_store().log(uuid, branch=branch)
    return _rows_to_dataset(rows)


def diff(uuid: str, ref_a: str = None, ref_b: str = None, branch: Optional[str] = None):
    """Show diff between two versions of an object."""
    return _default_store().diff(uuid, ref_a=ref_a, ref_b=ref_b, branch=branch)


# ------------------------------------------------------------------
# Remote
# ------------------------------------------------------------------

def push(uuid: str, remote_url: str, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
    """Push a local object to a remote CAS service."""
    return _default_store().push(uuid, remote_url, branch=branch, token=token)


def pull(uuid: str, remote_url: str, branch: Optional[str] = None, token: Optional[str] = None) -> dict:
    """Pull a remote object to the local store."""
    return _default_store().pull(uuid, remote_url, branch=branch, token=token)
