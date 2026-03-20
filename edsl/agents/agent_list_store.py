"""AgentList persistent store — provides .store accessor for CAS operations."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_list import AgentList
    from ..object_store import ObjectStore


class _StoreDescriptor:
    """Descriptor that returns AgentListStore class on class access,
    and a bound AgentListStore instance on instance access."""

    def __get__(self, obj, objtype=None):
        if obj is None:
            # Class-level access: AgentList.store.load(...), etc.
            return AgentListStore
        return obj._agent_list_store


class AgentListStore:
    """Versioned persistence for an AgentList via content-addressable storage.

    Accessed as ``al.store`` on instances or ``AgentList.store`` on the class.

    Instance methods (require an AgentList):
        - ``al.store.save(message="...")`` — commit to the store, returns UUID

    Class/static methods (no instance needed):
        - ``AgentList.store.load(uuid)`` — load by UUID
        - ``AgentList.store.list()`` — list all stored objects
        - ``AgentList.store.log(uuid)`` — commit history
        - ``AgentList.store.delete(uuid)`` — remove from store

    Examples:
        >>> import tempfile
        >>> from edsl import Agent, AgentList
        >>> root = tempfile.mkdtemp()
        >>> al = AgentList([Agent(traits={"age": 22})])
        >>> info = al.store.save(message="first", root=root)
        >>> info['status']
        'ok'
        >>> uid = info['uuid']
        >>> al2 = AgentList.store.load(uid, root=root)
        >>> al == al2
        True
        >>> len(AgentList.store.list(root=root))
        1
        >>> len(AgentList.store.log(uid, root=root))
        1
        >>> AgentList.store.delete(uid, root=root)
        >>> list(AgentList.store.list(root=root))
        []
    """

    def __init__(self, agent_list: "AgentList") -> None:
        self._agent_list = agent_list

    def save(self, message: str = "", store: Optional[ObjectStore] = None) -> str:
        """Save the AgentList to the object store. Returns its UUID.

        Auto-assigns a UUID on first save, reuses on subsequent saves.
        """
        from ..object_store import ObjectStore
        s = store or ObjectStore()
        return s.new_save(self._agent_list, message=message)

    @staticmethod
    def load(uuid: str, commit: Optional[str] = None, store: Optional[ObjectStore] = None) -> AgentList:
        """Load an AgentList from the object store by UUID.

        Args:
            uuid: The UUID of the stored AgentList.
            commit: Optional commit hash. Defaults to HEAD.
            store: Optional ObjectStore instance (defaults to global store).
        """
        from ..object_store import ObjectStore
        s = store or ObjectStore()
        return s.new_load(uuid, commit=commit)

    @staticmethod
    def list(store=None) -> list[dict]:
        """List all objects in the store.

        Returns a list of dicts with keys: uuid, type, description,
        created, last_modified.
        """
        from ..object_store import ObjectStore
        s = store or ObjectStore()
        return s.list()

    @staticmethod
    def log(uuid: str, store=None) -> list[dict]:
        """Commit history for a stored object (newest first)."""
        from ..object_store import ObjectStore
        s = store or ObjectStore()
        return s.log(uuid)

    @staticmethod
    def delete(uuid: str, store=None) -> None:
        """Remove an object and its history from the store."""
        from ..object_store import ObjectStore
        s = store or ObjectStore()
        return s.delete(uuid)
