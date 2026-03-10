"""Store accessor descriptor for AgentList — works on both instances and the class."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_list import AgentList


class StoreDescriptor:
    """Descriptor that returns the right accessor for instance vs class access.

    - ``AgentList.store`` → ClassStoreAccessor (load, list, delete)
    - ``al.store`` → InstanceStoreAccessor (save, log, plus load, list, delete)
    """

    def __get__(self, obj, objtype=None):
        if obj is None:
            return ClassStoreAccessor()
        return InstanceStoreAccessor(obj)


class ClassStoreAccessor:
    """Class-level store operations (no instance needed).

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> root = tempfile.mkdtemp()
        >>> al = AgentList([Agent(traits={'age': 22})])
        >>> uid = al.store.save(message="test", root=root)
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
        """Load an AgentList by UUID from the store."""
        from ..object_store import ObjectStore
        return ObjectStore(root).load(uuid, commit=commit, branch=branch)

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


class InstanceStoreAccessor(ClassStoreAccessor):
    """Instance-level store operations, inheriting class-level ones.

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> root = tempfile.mkdtemp()
        >>> al = AgentList([Agent(traits={'age': 22})])
        >>> uid = al.store.save(message="first", root=root)
        >>> al._cas_uuid == uid
        True
        >>> al.store.log(root=root)[0]['message']
        'first'
    """

    def __init__(self, agent_list: "AgentList") -> None:
        self._agent_list = agent_list

    def save(self, message: str = "", branch=None, root=None) -> str:
        """Save this AgentList to the store. Returns its UUID."""
        from ..object_store import ObjectStore
        return ObjectStore(root).save(self._agent_list, message=message, branch=branch)

    def log(self, root=None) -> list[dict]:
        """Commit history for this AgentList in the store."""
        from ..object_store import ObjectStore

        uuid = self._agent_list._cas_uuid
        if uuid is None:
            raise ValueError("This AgentList has not been saved to a store yet.")
        return ObjectStore(root).log(uuid)

    def branches(self, root=None) -> list[str]:
        """List branches for this AgentList in the store."""
        from ..object_store import ObjectStore

        uuid = self._agent_list._cas_uuid
        if uuid is None:
            raise ValueError("This AgentList has not been saved to a store yet.")
        return ObjectStore(root).branches(uuid)

    def branch(self, name: str, from_branch=None, root=None) -> None:
        """Create a new branch for this AgentList in the store."""
        from ..object_store import ObjectStore

        uuid = self._agent_list._cas_uuid
        if uuid is None:
            raise ValueError("This AgentList has not been saved to a store yet.")
        ObjectStore(root).branch(uuid, name, from_branch=from_branch)

    def checkout(self, branch: str, root=None) -> None:
        """Switch this AgentList's HEAD to the given branch in the store."""
        from ..object_store import ObjectStore

        uuid = self._agent_list._cas_uuid
        if uuid is None:
            raise ValueError("This AgentList has not been saved to a store yet.")
        ObjectStore(root).checkout(uuid, branch)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
