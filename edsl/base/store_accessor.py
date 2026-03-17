"""Store accessor descriptor — works on both instances and the class.

This is a general-purpose descriptor that any list-like EDSL object
(AgentList, ScenarioList, ModelList, Survey, Cache) can use to get
CAS-backed versioning via :class:`~edsl.object_store.ObjectStore`.

CAS tracking state (uuid, commit, current_branch) lives on the
:class:`InstanceStoreAccessor`, not on the domain object itself.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_REMOTE_URL = "http://localhost:8000"


def _default_token() -> Optional[str]:
    """Read the bearer token from the environment, or None."""
    return os.environ.get("EXPECTED_PARROT_API_KEY")


class StoreDescriptor:
    """Descriptor that returns the right accessor for instance vs class access.

    - ``MyList.store`` → ClassStoreAccessor (load, list, delete)
    - ``obj.store``    → InstanceStoreAccessor (save, log, plus load, list, delete)

    The InstanceStoreAccessor is cached on the instance so that CAS
    tracking attributes persist across accesses.
    """

    def __get__(self, obj, objtype=None):
        if obj is None:
            return ClassStoreAccessor()
        # Cache the accessor so CAS state survives across accesses
        accessor = obj.__dict__.get("_store_accessor")
        if accessor is None:
            accessor = InstanceStoreAccessor(obj)
            obj.__dict__["_store_accessor"] = accessor
        return accessor


class ClassStoreAccessor:
    """Class-level store operations (no instance needed).

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> root = tempfile.mkdtemp()
        >>> al = AgentList([Agent(traits={'age': 22})])
        >>> info = al.store.save(message="test", root=root)
        >>> info['status']
        'ok'
        >>> uid = info['uuid']
        >>> al2 = AgentList.store.load(uid, root=root)
        >>> al == al2
        True
        >>> AgentList.store.delete(uid, root=root)
    """

    def load(self, uuid: str, commit=None, branch=None, root=None):
        """Load an object by UUID from the store."""
        from ..object_store import ObjectStore

        obj, meta = ObjectStore(root).load(uuid, commit=commit, branch=branch)
        # Set CAS tracking on the loaded object's store accessor
        obj.store.uuid = meta["uuid"]
        obj.store.commit = meta["commit"]
        obj.store.current_branch = meta["branch"]
        return obj

    def log(self, uuid: str, commit=None, branch=None, root=None):
        """Commit history for an object in the store."""
        from ..object_store import ObjectStore
        from ..object_store.store_info import StoreLogInfo

        return StoreLogInfo(ObjectStore(root).log(uuid, commit=commit, branch=branch))

    def list(self, root=None):
        """List all objects in the store."""
        from ..object_store import ObjectStore
        from ..object_store.store_info import StoreListInfo

        return StoreListInfo(ObjectStore(root).list())

    def delete(self, uuid: str, root=None) -> None:
        """Delete an object from the store."""
        from ..object_store import ObjectStore

        ObjectStore(root).delete(uuid)

    def branches(self, uuid: str, root=None) -> list[str]:
        """List branches for an object in the store."""
        from ..object_store import ObjectStore

        return ObjectStore(root).branches(uuid)

    def diff(self, uuid: str, ref_a: str = None, ref_b: str = None, branch=None, context: int = 3, root=None):
        """Diff two versions of an object identified by *uuid*.

        Follows git conventions:

        - ``diff(uuid)``                       — HEAD vs HEAD~1
        - ``diff(uuid, "HEAD~2")``             — HEAD vs two commits back
        - ``diff(uuid, "abc123")``             — HEAD vs that commit hash/prefix
        - ``diff(uuid, "abc123", "def456")``   — explicit old → new

        Returns a :class:`~edsl.object_store.store_info.StoreDiffInfo`
        (a coloured unified-diff string).
        """
        from ..object_store import ObjectStore

        return ObjectStore(root).diff(uuid, ref_a=ref_a, ref_b=ref_b, branch=branch, context=context)

    def pull(self, uuid: str, remote_url: str = DEFAULT_REMOTE_URL, branch=None, root=None, token=None):
        """Pull a remote object to the local store by UUID.

        Returns the loaded object with CAS tracking set.
        """
        from ..object_store import ObjectStore

        token = token or _default_token()
        ObjectStore(root).pull(uuid, remote_url, branch=branch, token=token)
        return self.load(uuid, root=root)


class InstanceStoreAccessor(ClassStoreAccessor):
    """Instance-level store operations, inheriting class-level ones.

    CAS tracking state is stored here rather than on the domain object:

    - ``uuid``           — the object's UUID in the store (None if never saved)
    - ``commit``         — the last-known commit hash
    - ``current_branch`` — the last-known branch name

    Metadata fields can be set as attributes and are persisted on the
    next ``save()``: ``title``, ``alias``, ``visibility``, ``description``.

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> root = tempfile.mkdtemp()
        >>> al = AgentList([Agent(traits={'age': 22})])
        >>> info = al.store.save(message="first", root=root)
        >>> info['status']
        'ok'
        >>> al.store.uuid == info['uuid']
        True
        >>> al.store.current_branch
        'main'
    """

    _ALLOWED_ATTRS = frozenset({
        "_instance", "uuid", "commit", "current_branch",
        "_title", "_alias", "_visibility", "_description",
        "title", "alias", "visibility", "description",
    })

    def __init__(self, instance) -> None:
        self._instance = instance
        self.uuid: Optional[str] = None
        self.commit: Optional[str] = None
        self.current_branch: Optional[str] = None
        self._title: Optional[str] = None
        self._alias: Optional[str] = None
        self._visibility: Optional[str] = None
        self._description: Optional[str] = None

    def __setattr__(self, name: str, value) -> None:
        if name not in self._ALLOWED_ATTRS:
            raise AttributeError(
                f"Cannot set attribute {name!r} on {type(self).__name__}. "
                f"Settable metadata attributes: title, alias, visibility, description"
            )
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        if self.uuid is None:
            return "Store(not saved)"
        obj_type = type(self._instance).__name__
        branch = self.current_branch or "?"
        return f"Store({obj_type} uuid={self.uuid} branch={branch})"

    @property
    def title(self) -> Optional[str]:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = value

    @property
    def alias(self) -> Optional[str]:
        return self._alias

    @alias.setter
    def alias(self, value: str) -> None:
        self._alias = value

    @property
    def visibility(self) -> Optional[str]:
        return self._visibility

    @visibility.setter
    def visibility(self, value: str) -> None:
        self._visibility = value

    @property
    def description(self) -> Optional[str]:
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = value

    def save(
        self,
        message: str = "",
        branch=None,
        root=None,
        title: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Save this object to the store.

        Returns a :class:`~edsl.object_store.store_info.StoreSaveInfo`
        (a dict subclass) with ``status``, ``uuid``, ``branch``,
        ``commit`` (short hash), and a human-readable ``message``.

        Metadata fields (``title``, ``alias``, ``visibility``,
        ``description``) can be passed as keyword arguments or set as
        attributes before calling ``save()``.
        """
        from ..object_store import ObjectStore
        from ..object_store.store_info import StoreSaveInfo

        title = title if title is not None else self._title
        alias = alias if alias is not None else self._alias
        visibility = visibility if visibility is not None else self._visibility
        description = description if description is not None else self._description

        is_new = self.uuid is None

        info = ObjectStore(root).save(
            self._instance,
            message=message,
            branch=branch,
            uuid=self.uuid,
            expected_tip=self.commit,
            title=title,
            alias=alias,
            visibility=visibility,
            description=description,
        )
        self.uuid = info["uuid"]
        self.commit = info["commit"]
        self.current_branch = info["branch"]
        self._title = self._alias = self._visibility = self._description = None

        parts = []
        if is_new:
            parts.append(f"created {info['uuid'][:8]}")
        else:
            parts.append(f"committed to {info['branch']}")
        if alias:
            parts.append(f"alias set to '{alias}'")
        if title:
            parts.append(f"title set to '{title}'")
        if visibility:
            parts.append(f"visibility set to '{visibility}'")

        return StoreSaveInfo(
            status="ok",
            uuid=info["uuid"],
            branch=info["branch"],
            commit=info["commit"][:12],
            message="; ".join(parts),
        )

    def update_metadata(self, root=None, **kwargs) -> None:
        """Update metadata (title, alias, visibility, description) without a new commit."""
        from ..object_store import ObjectStore

        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        ObjectStore(root).update_metadata(self.uuid, **kwargs)

    def load(self, uuid: str = None, commit=None, branch=None, root=None):
        """Load an object by UUID, or reload this object from its last-known UUID."""
        if uuid is not None:
            return super().load(uuid, commit=commit, branch=branch, root=root)
        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        return super().load(self.uuid, commit=commit, branch=branch, root=root)

    def log(self, root=None):
        """Commit history for this object in the store."""
        from ..object_store import ObjectStore
        from ..scenarios import Scenario, ScenarioList

        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        entries = ObjectStore(root).log(self.uuid)
        return ScenarioList([Scenario(e) for e in entries])

    def diff(self, ref_a: str = None, ref_b: str = None, branch=None, context: int = 3, root=None):
        """Diff two saved versions of this object.

        Follows git conventions:

        - ``diff()``                   — HEAD vs HEAD~1 (last change)
        - ``diff("HEAD~2")``           — HEAD vs two commits back
        - ``diff("abc123")``           — HEAD vs that commit hash/prefix
        - ``diff("abc123", "def456")`` — explicit old → new

        Returns a :class:`~edsl.object_store.store_info.StoreDiffInfo`
        (a coloured unified-diff string).
        """
        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        return super().diff(self.uuid, ref_a=ref_a, ref_b=ref_b, branch=branch, context=context, root=root)

    def branches(self, root=None) -> list[str]:
        """List branches for this object in the store."""
        from ..object_store import ObjectStore

        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        return ObjectStore(root).branches(self.uuid)

    def branch(self, name: str, from_branch=None, root=None) -> None:
        """Create a new branch for this object in the store."""
        from ..object_store import ObjectStore

        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        ObjectStore(root).branch(self.uuid, name, from_branch=from_branch)

    def checkout(self, branch: str, root=None) -> None:
        """Switch this object's HEAD to the given branch in the store."""
        from ..object_store import ObjectStore

        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        ObjectStore(root).checkout(self.uuid, branch)

    def push(self, remote_url: str = DEFAULT_REMOTE_URL, branch=None, root=None, token=None) -> dict:
        """Push this object to a remote CAS service.

        Saves locally first if not already saved. Defaults to
        ``http://localhost:8000``. Uses ``EXPECTED_PARROT_API_KEY``
        from the environment if no token is given.
        """
        from ..object_store import ObjectStore

        token = token or _default_token()
        if self.uuid is None:
            self.save(root=root)
        return ObjectStore(root).push(self.uuid, remote_url, branch=branch, token=token)

    def pull(self, remote_url: str = DEFAULT_REMOTE_URL, branch=None, root=None, token=None) -> dict:
        """Pull this object from a remote CAS service.

        The object must have a UUID (from a previous save or pull).
        Uses ``EXPECTED_PARROT_API_KEY`` from the environment if
        no token is given.

        After pulling, the in-memory object is updated to reflect the
        latest version from the remote store.
        """
        from ..object_store import ObjectStore

        token = token or _default_token()
        if self.uuid is None:
            raise ValueError("This object has no UUID. Save it first or use ObjectStore.pull() with an explicit UUID.")
        result = ObjectStore(root).pull(self.uuid, remote_url, branch=branch, token=token)

        # Reload from local store and update the in-memory object
        updated, meta = ObjectStore(root).load(self.uuid, branch=branch)
        # Preserve the store accessor itself while replacing domain state
        old_accessor = self._instance.__dict__.get("_store_accessor")
        self._instance.__dict__.update(updated.__dict__)
        if old_accessor is not None:
            self._instance.__dict__["_store_accessor"] = old_accessor
        self.commit = meta["commit"]
        self.current_branch = meta["branch"]

        return result


if __name__ == "__main__":
    import doctest

    doctest.testmod()
