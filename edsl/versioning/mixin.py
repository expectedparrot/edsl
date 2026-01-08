"""
GitMixin - Mixin to add git-like versioning to any class.

Provides the event decorator and GitMixin class.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import Commit, PushResult, Status
from .protocols import Remote
from .git_facade import ExpectedParrotGit, ObjectView, init_repo, clone_from_remote


# ----------------------------
# Event decorator
# ----------------------------

def event(method: Callable) -> Callable:
    """
    Decorator that marks a method as returning an Event.

    When called on a class with GitMixin:
    1. The method is called, returning an Event
    2. The Event is applied via event.execute(store)
    3. A new instance is returned with updated state + pending event
    """
    method._returns_event = True
    return method


# ----------------------------
# GitMixin
# ----------------------------

class GitMixin:
    """
    Mixin that adds git-like versioning to your class.

    Git operations use git_ prefix to avoid conflicts with existing methods.

    Required class attributes:
    - _versioned: str - Name of the store attribute
    - _store_class: type - The store class (optional, defaults to dict)

    Store requirements:
    - to_dict() -> dict
    - from_dict(data: dict) -> Store (classmethod)
    """

    _git: ExpectedParrotGit

    def __init__(self):
        self._git = None
        self._needs_git_init = True

    def _ensure_git_init(self) -> None:
        if getattr(self, "_needs_git_init", False):
            if not hasattr(self.__class__, '_versioned'):
                raise TypeError(
                    f"GitMixin subclass '{self.__class__.__name__}' must define _versioned."
                )
            rows = [self._to_state()]
            view = init_repo(rows)
            self._git = ExpectedParrotGit(view)
            self._needs_git_init = False

    def __getattribute__(self, name: str) -> Any:
        attr = super().__getattribute__(name)
        if callable(attr) and getattr(attr, "_returns_event", False):
            return self._wrap_event_method(attr)
        return attr

    def _wrap_event_method(self, method: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            self._ensure_git_init()
            event_obj = method(*args, **kwargs)
            current_store = getattr(self, self.__class__._versioned, None)
            if current_store is None:
                raise ValueError(f"Store not found for class {self.__class__.__name__}")
            event_handler = getattr(self.__class__, '_event_handler', None)
            if event_handler is None:
                raise ValueError(f"Event handler not found for class {self.__class__.__name__}")

            new_store = event_handler(event_obj, current_store)
            
            if isinstance(new_store, dict):
                new_state = dict(new_store)
            else:
                new_state = new_store.to_dict()
            new_git = self._git.apply_event(event_obj.name, getattr(event_obj, 'payload', {}))
            new_instance = self._from_state(new_state)
            new_instance._git = new_git
            new_instance._needs_git_init = False
            return new_instance
        return wrapper

    def _to_state(self) -> Dict[str, Any]:
        store = getattr(self, self.__class__._versioned)
        if isinstance(store, dict):
            return dict(store)
        return store.to_dict()

    @classmethod
    def _from_state(cls, state: Dict[str, Any]) -> "GitMixin":
        instance = object.__new__(cls)
        store_class = getattr(cls, '_store_class', dict)
        if store_class is dict:
            store = dict(state)
        else:
            store = store_class.from_dict(state)
        setattr(instance, cls._versioned, store)
        instance._git = None
        instance._needs_git_init = False
        return instance

    def _evolve(self, new_git: ExpectedParrotGit, *, from_git: bool = False) -> "GitMixin":
        """Legacy method - creates new instance. Use _mutate for in-place updates."""
        if from_git:
            rows = new_git.view.get_base_state()
            state = rows[0] if rows else {}
            new_instance = self._from_state(state)
        else:
            current_state = self._to_state()
            new_instance = self._from_state(current_state)
        new_instance._git = new_git
        return new_instance

    def _mutate(self, new_git: ExpectedParrotGit, *, from_git: bool = False) -> "GitMixin":
        """Update this instance in place and return self for chaining."""
        if from_git:
            # Update internal data from git state
            rows = new_git.view.get_base_state()
            state = rows[0] if rows else {}
            self._update_from_state(state)
        self._git = new_git
        return self

    def _update_from_state(self, state: Dict[str, Any]) -> None:
        """Update internal data from a state dict."""
        store_class = getattr(self.__class__, '_store_class', dict)
        if store_class is dict:
            store = dict(state)
        else:
            store = store_class.from_dict(state)
        setattr(self, self.__class__._versioned, store)

    # --- Properties ---

    @property
    def has_staged(self) -> bool:
        self._ensure_git_init()
        return self._git.view.has_staged

    @property
    def commit_hash(self) -> str:
        self._ensure_git_init()
        return self._git.view.commit_hash

    @property
    def branch_name(self) -> Optional[str]:
        self._ensure_git_init()
        return self._git.view.head_ref

    @property
    def is_behind(self) -> bool:
        self._ensure_git_init()
        return self._git.view.is_behind()

    # --- Git operations (git_ prefix) ---

    def git_commit(self, message: str, *, author: str = "unknown", force: bool = False) -> "GitMixin":
        """Commit pending events. Mutates in place and returns self for chaining."""
        self._ensure_git_init()
        current_state = [self._to_state()]
        new_git = self._git.commit(message, author=author, force=force, state=current_state)
        return self._mutate(new_git)

    def git_discard(self) -> "GitMixin":
        """Discard all pending events and restore to base state. Mutates in place."""
        self._ensure_git_init()
        new_git = self._git.discard()
        return self._mutate(new_git, from_git=True)

    def git_branch(self, name: str) -> "GitMixin":
        """Create and checkout a new branch. Mutates in place and returns self."""
        self._ensure_git_init()
        new_git = self._git.branch(name)
        return self._mutate(new_git)

    def git_delete_branch(self, name: str) -> "GitMixin":
        """Delete a branch. Mutates in place and returns self."""
        self._ensure_git_init()
        new_git = self._git.delete_branch(name)
        return self._mutate(new_git)

    def git_checkout(self, rev: str, *, force: bool = False) -> "GitMixin":
        """Checkout a branch or commit. Mutates in place and returns self."""
        self._ensure_git_init()
        new_git = self._git.checkout(rev, force=force)
        return self._mutate(new_git, from_git=True)

    def git_add_remote(self, name: str, remote: Remote) -> "GitMixin":
        """Add a remote repository. Mutates in place and returns self."""
        self._ensure_git_init()
        new_git = self._git.add_remote(name, remote)
        return self._mutate(new_git)

    def git_remove_remote(self, name: str) -> "GitMixin":
        """Remove a remote repository. Mutates in place and returns self."""
        self._ensure_git_init()
        new_git = self._git.remove_remote(name)
        return self._mutate(new_git)

    def git_push(self, remote_name: str = "origin", ref_name: Optional[str] = None,
                 *, force: bool = False) -> "GitMixin":
        """Push to remote. Returns self for chaining. Result stored in last_push_result."""
        self._ensure_git_init()
        self._last_push_result = self._git.push(remote_name, ref_name, force=force)
        return self

    @property
    def last_push_result(self) -> Optional[PushResult]:
        """Result of the last git_push() call."""
        return getattr(self, '_last_push_result', None)

    def git_pull(self, remote_name: str = "origin", ref_name: Optional[str] = None) -> "GitMixin":
        """Pull from remote. Mutates in place and returns self for chaining."""
        self._ensure_git_init()
        new_git = self._git.pull(remote_name, ref_name)
        return self._mutate(new_git, from_git=True)

    def git_fetch(self, remote_name: str = "origin") -> Dict[str, int]:
        """Fetch from remote without merging."""
        self._ensure_git_init()
        return self._git.fetch(remote_name)

    @classmethod
    def git_clone(cls, remote: Remote, ref_name: str = "main") -> "GitMixin":
        """Clone from a remote repository."""
        view = clone_from_remote(remote, ref_name)
        git = ExpectedParrotGit(view)
        git = git.add_remote("origin", remote)
        rows = git.view.get_base_state()
        state = rows[0] if rows else {}
        instance = cls._from_state(state)
        instance._git = git
        return instance

    def git_log(self, limit: int = 20) -> List[Commit]:
        """Get commit history."""
        self._ensure_git_init()
        return self._git.log(limit=limit)

    def git_status(self) -> Status:
        """Get current status."""
        self._ensure_git_init()
        return self._git.status()

    def git_pending(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get pending events."""
        self._ensure_git_init()
        return list(self._git.view.pending_events)
