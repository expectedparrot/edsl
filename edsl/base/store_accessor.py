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
        >>> uid = info['uuid']
        >>> 'commit' in info and 'branch' in info
        True
        >>> al2 = AgentList.store.load(uid, root=root)
        >>> al == al2
        True
        >>> len(AgentList.store.list(root=root))
        1
        >>> AgentList.store.delete(uid, root=root)
        >>> AgentList.store.list(root=root)
        []
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

    def log(self, uuid: str, commit=None, branch=None, root=None) -> list[dict]:
        """Commit history for an object in the store."""
        from ..object_store import ObjectStore

        return ObjectStore(root).log(uuid, commit=commit, branch=branch)

    def list(self, root=None) -> list:
        """List all objects in the store."""
        from ..object_store import ObjectStore

        return ObjectStore(root).list()

    def delete(self, uuid: str, root=None) -> None:
        """Delete an object from the store."""
        from ..object_store import ObjectStore

        ObjectStore(root).delete(uuid)

    def branches(self, uuid: str, root=None) -> list[str]:
        """List branches for an object in the store."""
        from ..object_store import ObjectStore

        return ObjectStore(root).branches(uuid)

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

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> root = tempfile.mkdtemp()
        >>> al = AgentList([Agent(traits={'age': 22})])
        >>> info = al.store.save(message="first", root=root)
        >>> info['branch']
        'main'
        >>> al.store.uuid == info['uuid']
        True
        >>> al.store.current_branch
        'main'
        >>> al.store.log(root=root)[0]['message']
        'first'
    """

    def __init__(self, instance) -> None:
        self._instance = instance
        self.uuid: Optional[str] = None
        self.commit: Optional[str] = None
        self.current_branch: Optional[str] = None

    def save(
        self,
        message: str = "",
        branch=None,
        root=None,
        title: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """Save this object to the store.

        Returns a dict with ``uuid``, ``commit``, ``branch``, ``parent``,
        ``timestamp``, and ``message``.
        """
        from ..object_store import ObjectStore

        info = ObjectStore(root).save(
            self._instance,
            message=message,
            branch=branch,
            uuid=self.uuid,
            expected_parent=self.commit,
            title=title,
            alias=alias,
            visibility=visibility,
            description=description,
        )
        self.uuid = info["uuid"]
        self.commit = info["commit"]
        self.current_branch = info["branch"]
        return info

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

    def log(self, root=None) -> list[dict]:
        """Commit history for this object in the store."""
        from ..object_store import ObjectStore

        if self.uuid is None:
            raise ValueError("This object has not been saved to a store yet.")
        return ObjectStore(root).log(self.uuid)

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
        """
        from ..object_store import ObjectStore

        token = token or _default_token()
        if self.uuid is None:
            raise ValueError("This object has no UUID. Save it first or use ObjectStore.pull() with an explicit UUID.")
        return ObjectStore(root).pull(self.uuid, remote_url, branch=branch, token=token)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
