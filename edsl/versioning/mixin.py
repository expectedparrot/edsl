"""
GitMixin - Mixin to add git-like versioning to any class.

Provides the event decorator and GitMixin class.
"""

from __future__ import annotations

import difflib
import gzip
import json
import os
import re
import sys
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .models import Commit, MergePrepareResult, PushResult, Status
from .protocols import Remote
from .git_facade import ExpectedParrotGit, ObjectView, init_repo, clone_from_remote
from .storage import InMemoryRepo
from .exceptions import (
    InvalidAliasError,
    MergeConflictError,
    MissingAliasError,
    StagedChangesError,
    InvalidEPFileError,
)


# ----------------------------
# Helper functions
# ----------------------------


def _truncate(value: Any, max_len: int = 30) -> str:
    """Truncate a value for display purposes."""
    s = repr(value) if not isinstance(value, str) else value
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


# ----------------------------
# Alias validation
# ----------------------------


def validate_alias(alias: str) -> str:
    """Validate and normalize alias for URL safety.

    Rules:
    - Lowercase only
    - No spaces (use dashes)
    - No underscores (use dashes)
    - Alphanumeric and dashes only
    - No leading/trailing dashes

    Args:
        alias: The alias to validate (can be "name" or "owner/name")

    Returns:
        Normalized lowercase alias

    Raises:
        InvalidAliasError: If the alias format is invalid
    """
    if "/" in alias:
        parts = alias.split("/")
        if len(parts) != 2:
            raise InvalidAliasError("Alias can only have one '/' for owner/name format")
        owner, name = parts
        return f"{_validate_alias_part(owner)}/{_validate_alias_part(name)}"
    return _validate_alias_part(alias)


def _validate_alias_part(part: str) -> str:
    """Validate a single part (owner or name) of an alias.

    Strict validation - rejects invalid format rather than normalizing.
    """
    if not part:
        raise InvalidAliasError("Alias cannot be empty")
    if " " in part:
        raise InvalidAliasError("Alias cannot contain spaces (use dashes instead)")
    if "_" in part:
        raise InvalidAliasError("Alias cannot contain underscores (use dashes instead)")
    if part != part.lower():
        raise InvalidAliasError("Alias must be lowercase")
    if "--" in part:
        raise InvalidAliasError("Alias cannot contain consecutive dashes")
    if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", part):
        raise InvalidAliasError(
            "Alias must be lowercase alphanumeric with dashes, no leading/trailing dashes"
        )
    return part


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

    Optional overrides for composite objects:
    - _get_related_objects(): Returns list of (name, object) tuples for objects
      that should be pushed/pulled together with this object.
    - _resolve_related_objects(refs): Resolves refs back to objects after pull.
    """

    _git: ExpectedParrotGit

    def __init__(self):
        self._git = None
        self._needs_git_init = True

    def _ensure_git_init(self) -> None:
        if getattr(self, "_needs_git_init", False):
            if not hasattr(self.__class__, "_versioned"):
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
            event_handler = getattr(self.__class__, "_event_handler", None)
            if event_handler is None:
                raise ValueError(
                    f"Event handler not found for class {self.__class__.__name__}"
                )

            # Copy the store before applying the event to preserve immutability
            # apply_event mutates in-place, so we need a fresh copy
            store_class = getattr(self.__class__, "_store_class", dict)
            if store_class is dict:
                store_copy = dict(current_store)
            elif hasattr(current_store, "copy"):
                # Fast path: use Store.copy() which avoids deep copy
                store_copy = current_store.copy()
            else:
                store_copy = store_class.from_dict(current_store.to_dict())

            new_store = event_handler(event_obj, store_copy)

            new_git = self._git.apply_event(
                event_obj.name, getattr(event_obj, "payload", {})
            )

            # Fast path: if we have _from_store, use it to avoid dict round-trip
            if hasattr(self.__class__, "_from_store") and not isinstance(
                new_store, dict
            ):
                new_instance = self.__class__._from_store(new_store)
            else:
                # Fallback: serialize to dict for _from_state
                if isinstance(new_store, dict):
                    new_state = dict(new_store)
                else:
                    new_state = new_store.to_dict()
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
        store_class = getattr(cls, "_store_class", dict)
        if store_class is dict:
            store = dict(state)
        else:
            store = store_class.from_dict(state)
        setattr(instance, cls._versioned, store)
        instance._git = None
        instance._needs_git_init = False
        return instance

    def _evolve(
        self, new_git: ExpectedParrotGit, *, from_git: bool = False
    ) -> "GitMixin":
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

    def _mutate(
        self, new_git: ExpectedParrotGit, *, from_git: bool = False
    ) -> "GitMixin":
        """Update this instance in place and return self for chaining.

        When from_git=True, preserves _info (alias, description) across branches,
        since this is repository-level metadata (like git remote URLs).
        """
        if from_git:
            # Preserve _info before loading new state (it's repo-level, not branch-level)
            current_state = self._to_state()
            current_info = current_state.get("meta", {}).get("_info", {})

            # Update internal data from git state
            rows = new_git.view.get_base_state()
            state = rows[0] if rows else {}

            # Merge preserved _info into new state
            if current_info:
                if "meta" not in state:
                    state["meta"] = {}
                # Merge: keep existing _info, but allow new state to override specific fields
                new_info = state.get("meta", {}).get("_info", {})
                merged_info = {**current_info, **new_info}
                state["meta"]["_info"] = merged_info

            self._update_from_state(state)
        self._git = new_git
        return self

    def _update_from_state(self, state: Dict[str, Any]) -> None:
        """Update internal data from a state dict."""
        store_class = getattr(self.__class__, "_store_class", dict)
        if store_class is dict:
            store = dict(state)
        else:
            store = store_class.from_dict(state)
        setattr(self, self.__class__._versioned, store)

    # --- Related objects (for composite objects like Jobs) ---

    def _get_related_objects(self) -> List[Tuple[str, "GitMixin"]]:
        """Return list of (name, object) tuples for related objects.

        Override this method in classes that compose other GitMixin objects
        (like Jobs which contains Survey, AgentList, ModelList, ScenarioList).
        Related objects will be automatically pushed before this object.

        Returns:
            List of (name, object) tuples. Name is used for auto-generating aliases.
        """
        return []

    def _resolve_related_objects(self, refs: Dict[str, str]) -> Dict[str, "GitMixin"]:
        """Resolve refs to related objects after pull.

        Override this method to resolve component refs back to live objects.
        Called after git_pull to reconstruct related objects from refs.

        Args:
            refs: Dictionary mapping ref names to commit_hashes.

        Returns:
            Dictionary mapping names to resolved objects.
        """
        return {}

    def _resolve_related_objects_after_pull(self) -> None:
        """Hook called after git_pull to resolve related objects.

        Override this method in composite classes to pull and resolve
        related objects after the main object has been pulled.

        Default implementation does nothing.
        """
        pass

    def _store_related_aliases(self, aliases: Dict[str, str]) -> None:
        """Store aliases of pushed related objects in store.meta.

        Override this method in composite classes to store component aliases
        for later resolution during pull.

        Args:
            aliases: Dictionary mapping object names to their aliases.
        """
        pass

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

    # --- Info methods ---

    def git_set_info(self, alias: str = None, description: str = None) -> "GitMixin":
        """Store alias, description, and class name in meta['_info'] for use by git_push.

        This creates a staged change that should be committed before pushing.
        The EDSL class name is automatically included.
        """
        self._ensure_git_init()
        state = self._to_state()

        # Get or create _info dict inside meta
        if "meta" not in state:
            state["meta"] = {}
        if "_info" not in state["meta"]:
            state["meta"]["_info"] = {}

        # Always include the EDSL class name
        state["meta"]["_info"]["edsl_class_name"] = self.__class__.__name__

        if alias is not None:
            state["meta"]["_info"]["alias"] = alias
        if description is not None:
            state["meta"]["_info"]["description"] = description

        # Update the store with new state
        self._update_from_state(state)

        # Stage the change
        new_git = self._git.apply_event(
            "set_info",
            {
                "alias": alias,
                "description": description,
                "edsl_class_name": self.__class__.__name__,
            },
        )
        self._git = new_git

        return self

    def git_get_info(self) -> Dict[str, Any]:
        """Get stored _info from meta, or empty dict if not set."""
        self._ensure_git_init()
        state = self._to_state()
        meta = state.get("meta", {})
        return meta.get("_info", {})

    # --- Git operations (git_ prefix) ---

    def git_commit(
        self, message: str, *, author: str = "unknown", force: bool = False
    ) -> None:
        """Commit pending events. Mutates in place.

        Args:
            message: Commit message
            author: Author name (default: "unknown")
            force: Force commit even if behind (default: False)
        """
        self._ensure_git_init()
        current_state = [self._to_state()]
        new_git = self._git.commit(
            message, author=author, force=force, state=current_state
        )
        self._mutate(new_git)

        # Print git-style status
        branch = new_git.view.head_ref or "HEAD"
        commit_id = new_git.view.commit_hash[:8]
        print(f"[{branch} {commit_id}] {message}")

    def git_discard(self) -> None:
        """Discard all pending events and restore to base state. Mutates in place."""
        self._ensure_git_init()
        pending_count = len(self._git.view.pending_events)
        new_git = self._git.discard()
        self._mutate(new_git, from_git=True)

        # Print git-style status
        if pending_count > 0:
            print(f"Discarded {pending_count} pending change(s)")
        else:
            print("Nothing to discard (working tree clean)")

    def replace_with(
        self,
        new_data: Any,
        *,
        operation: str = "service",
        params: Optional[Dict[str, Any]] = None,
    ) -> "GitMixin":
        """Create a new instance with new data as a staged change.

        This is used by versioned services to create a new version
        while preserving git history. The original object is NOT modified.
        The change is staged but NOT committed - call git_commit() to commit.

        Args:
            new_data: The new data to use. Can be:
                - A dict (will be used to create new instance)
                - An instance of the same type (data will be extracted)
                - A list of entries (for list-based objects)
            operation: Name of the operation that produced this data
            params: Parameters used in the operation (for audit trail)

        Returns:
            A new instance with staged changes (original unchanged)
        """
        self._ensure_git_init()

        # Preserve original meta (contains _info with alias, codebook, etc.)
        original_state = self._to_state()
        original_meta = original_state.get("meta", {})

        # Extract state from new_data
        if isinstance(new_data, type(self)):
            # Same type - extract its state
            new_state = new_data._to_state()
        elif isinstance(new_data, dict):
            # Dict - assume it's a valid state dict
            if "entries" in new_data and "meta" in new_data:
                new_state = new_data
            else:
                # Wrap as entries if it looks like a single entry
                new_state = {"entries": [new_data], "meta": {}}
        elif isinstance(new_data, list):
            # List of entries
            new_state = {"entries": new_data, "meta": {}}
        else:
            raise TypeError(
                f"replace_with() expects dict, list, or {type(self).__name__}, "
                f"got {type(new_data).__name__}"
            )

        # Merge metadata: preserve original _info (alias, etc.) while allowing
        # new meta to override other fields
        merged_meta = dict(original_meta)
        new_meta = new_state.get("meta", {})
        for key, value in new_meta.items():
            if key != "_info":  # Never overwrite _info from new data
                merged_meta[key] = value
        new_state["meta"] = merged_meta

        # Create a NEW instance from the new state
        new_instance = self._from_state(new_state)

        # Copy the git state to the new instance
        new_instance._git = self._git
        new_instance._needs_git_init = False

        # Stage the change (don't commit - user can review and commit)
        event_payload = {
            "operation": operation,
            "params": params or {},
            "entries_count": len(new_state.get("entries", [])),
        }
        new_instance._git = new_instance._git.apply_event("replace", event_payload)

        return new_instance

    def git_branch(self, name: Optional[str] = None) -> None:
        """List branches or create a new branch.

        When called with no arguments, lists all branches with the current
        branch highlighted (like `git branch`).

        When called with a name, creates and checks out a new branch
        (like `git checkout -b`).

        Args:
            name: Name of new branch to create. If None, lists all branches.
        """
        self._ensure_git_init()

        if name is None:
            # List all branches (like `git branch` with no args)
            repo = self._git.view.repo
            refs = repo.list_refs()
            current_ref = self._git.view.head_ref

            # ANSI color codes
            use_color = sys.stdout.isatty()
            GREEN = "\033[32m" if use_color else ""
            RESET = "\033[0m" if use_color else ""

            branches = [ref for ref in refs if ref.kind == "branch"]
            if not branches:
                print("No branches found.")
                return

            for ref in sorted(branches, key=lambda r: r.name):
                if ref.name == current_ref:
                    print(f"{GREEN}* {ref.name}{RESET}")
                else:
                    print(f"  {ref.name}")
            return

        # Create new branch
        new_git = self._git.branch(name)
        self._mutate(new_git)
        print(f"Switched to a new branch '{name}'")

    def git_delete_branch(self, name: str) -> None:
        """Delete a branch. Mutates in place.

        Args:
            name: Name of the branch to delete
        """
        self._ensure_git_init()
        new_git = self._git.delete_branch(name)
        self._mutate(new_git)

        # Print git-style status
        print(f"Deleted branch {name}")

    def git_checkout(self, rev: Optional[str] = None, *, force: bool = False) -> None:
        """Checkout a branch or commit. Mutates in place.

        Args:
            rev: Branch name or commit hash. If not provided, shows available options.
            force: Force checkout even with uncommitted changes (default: False)
        """
        self._ensure_git_init()

        if rev is None:
            # Show available options instead of failing
            repo = self._git.view.repo
            refs = repo.list_refs()
            current_ref = self._git.view.head_ref
            current_commit = self._git.view.commit_hash

            lines = ["No revision specified. Available options:\n"]

            # Show current HEAD state
            if current_ref is None:
                lines.append(f"HEAD is detached at {current_commit[:8]}")
                lines.append("")

            # Show branches
            branches = [r for r in refs if r.kind == "branch"]
            if branches:
                lines.append("Branches:")
                for ref in branches:
                    marker = "* " if ref.name == current_ref else "  "
                    lines.append(f"  {marker}{ref.name}")
                lines.append("")

            # Show tags
            tags = [r for r in refs if r.kind == "tag"]
            if tags:
                lines.append("Tags:")
                for ref in tags:
                    lines.append(f"    {ref.name}")
                lines.append("")

            # Show recent commits
            commits = self._git.log(limit=5)
            if commits:
                lines.append("Recent commits:")
                for c in commits:
                    short_hash = c.commit_id[:8]
                    msg = c.message[:40] + ("..." if len(c.message) > 40 else "")
                    lines.append(f"    {short_hash}  {msg}")

            raise ValueError("\n".join(lines))

        new_git = self._git.checkout(rev, force=force)
        self._mutate(new_git, from_git=True)

        # Print git-style status
        if new_git.view.head_ref is not None:
            print(f"Switched to branch '{new_git.view.head_ref}'")
        else:
            # Detached HEAD state
            print(f"HEAD is now at {new_git.view.commit_hash[:8]}")
            print(
                "You are in 'detached HEAD' state. Create a branch with git_branch('name') to keep changes."
            )

    def git_add_remote(
        self, name: str = "origin", url: Union[Remote, str] = None
    ) -> "GitMixin":
        """Add a remote repository. Optional - git_push creates 'origin' automatically.

        Args:
            name: Remote name (default: "origin")
            url: URL string or Remote object. Defaults to EDSL_GIT_SERVER from config.
        """
        self._ensure_git_init()
        if url is None:
            from edsl.config import CONFIG

            url = CONFIG.get("EDSL_GIT_SERVER")
        new_git = self._git.add_remote(name, url)
        return self._mutate(new_git)

    def git_remove_remote(self, name: str) -> "GitMixin":
        """Remove a remote repository. Mutates in place and returns self."""
        self._ensure_git_init()
        new_git = self._git.remove_remote(name)
        return self._mutate(new_git)

    def git_push(
        self,
        remote_name: str = "origin",
        ref_name: Optional[str] = None,
        *,
        force: bool = False,
        alias: str = None,
        description: str = None,
        username: str = None,
    ) -> None:
        """Push to remote. Handles remote creation and _info automatically.

        On first push:
        - If no remote exists, creates "origin" using EDSL_GIT_SERVER from config
        - If _info empty, populates from kwargs and commits
        - Creates repo on server, then pushes

        _info is source of truth once set (kwargs ignored after first push).
        To change _info, use git_set_info() explicitly.

        Prints git-style output showing the push result and view URL.

        For composite objects (like Jobs), automatically pushes related objects
        first by calling _get_related_objects().

        Args:
            remote_name: Name of remote (default: "origin")
            ref_name: Branch to push (default: current branch)
            force: Force push even if not fast-forward
            alias: Alias for the repo (required on first push if not in _info)
            description: Description for the repo (optional)
            username: Username namespace (e.g., "john"). If not provided and alias
                     doesn't contain "/", will try to get from Coop profile.
        """
        self._ensure_git_init()

        # Push related objects first (for composite objects like Jobs)
        related_objects = self._get_related_objects()
        pushed_aliases = {}  # Track aliases of pushed objects
        if related_objects:
            for name, obj in related_objects:
                if obj is not None and hasattr(obj, "git_push"):
                    # Check if object already has an alias set
                    obj_info = (
                        obj.git_get_info() if hasattr(obj, "git_get_info") else {}
                    )
                    if not obj_info.get("alias"):
                        # Auto-generate alias based on parent alias
                        if alias:
                            obj_alias = f"{alias}-{name.lower()}"
                            print(f"Pushing {name} as '{obj_alias}'...")
                            try:
                                obj.git_push(
                                    remote_name=remote_name,
                                    force=force,
                                    alias=obj_alias,
                                    username=username,
                                )
                                # Capture the resolved alias after push
                                pushed_info = obj.git_get_info()
                                if pushed_info.get("alias"):
                                    pushed_aliases[name] = pushed_info["alias"]
                            except Exception as e:
                                print(f"Warning: Could not push {name}: {e}")
                    else:
                        # Object already has alias, just push
                        print(f"Pushing {name} ('{obj_info.get('alias')}')...")
                        try:
                            obj.git_push(remote_name=remote_name, force=force)
                            pushed_aliases[name] = obj_info["alias"]
                        except Exception as e:
                            print(f"Warning: Could not push {name}: {e}")

            # Store pushed aliases in store.meta for later resolution
            if pushed_aliases:
                self._store_related_aliases(pushed_aliases)

        # Create remote if doesn't exist
        remote = self._git._remotes.get(remote_name)
        server_url = None  # Track server URL for view URL
        if remote is None:
            from edsl.config import CONFIG

            server_url = CONFIG.get("EDSL_GIT_SERVER")
            self._git = self._git.add_remote(remote_name, server_url)
            remote = server_url

        # Handle _info - it's the source of truth once set
        info = self.git_get_info()
        if info.get("alias"):
            # _info is source of truth - use stored values
            resolved_alias = info["alias"]
            resolved_description = info.get("description")
        elif alias is not None:
            # First push with kwargs - validate and resolve alias
            resolved_alias = validate_alias(alias)
            if "/" not in resolved_alias:
                # Prepend username namespace
                if username is not None:
                    resolved_alias = f"{validate_alias(username)}/{resolved_alias}"
                else:
                    # Try to get from Coop profile
                    try:
                        from edsl.coop import Coop

                        profile = Coop().get_profile()
                        resolved_alias = f"{profile['username']}/{resolved_alias}"
                    except Exception:
                        raise MissingAliasError(
                            "Alias requires a username namespace. Either provide a fully-qualified "
                            "alias (e.g., 'john/my-survey') or pass username='john'."
                        )
            resolved_description = description
            # Populate _info and commit
            self.git_set_info(alias=resolved_alias, description=resolved_description)
            self.git_commit(f"Set info: {resolved_alias}")
        else:
            raise MissingAliasError()

        # Create repo on server if remote is URL string
        if isinstance(remote, str):
            server_url = remote  # Track before conversion
            from edsl.versioning.http_remote import HTTPRemote

            real_remote = HTTPRemote.create_repo(
                url=remote, alias=resolved_alias, description=resolved_description
            )
            self._git = self._git.remove_remote(remote_name).add_remote(
                remote_name, real_remote
            )
        elif server_url is None:
            # Remote is HTTPRemote object - try to get URL from it
            from edsl.versioning.http_remote import HTTPRemote

            if isinstance(remote, HTTPRemote):
                server_url = remote.url

        self._last_push_result = self._git.push(remote_name, ref_name, force=force)

        # Build view URL
        view_url = f"{server_url.rstrip('/')}/{resolved_alias}" if server_url else None

        # Print git-style output
        result = self._last_push_result
        old = result.old_commit[:7] if result.old_commit else "0000000"
        new = result.new_commit[:7]
        print(f"To {remote_name}")
        print(f"   {old}..{new}  {result.ref_name} -> {result.ref_name}")
        if result.commits_pushed > 0:
            print(
                f"   ({result.commits_pushed} commit{'s' if result.commits_pushed != 1 else ''} pushed)"
            )
        if view_url:
            print(f"View at: {view_url}")

    @property
    def last_push_result(self) -> Optional[PushResult]:
        """Result of the last git_push() call."""
        return getattr(self, "_last_push_result", None)

    def git_pull(
        self, remote_name: str = "origin", ref_name: Optional[str] = None
    ) -> None:
        """Pull from remote. Mutates in place.

        For composite objects (like Jobs), automatically resolves related objects
        after pulling by calling _resolve_related_objects().
        """
        self._ensure_git_init()
        new_git, pull_result = self._git.pull(remote_name, ref_name)

        # Print pull summary
        if pull_result.commits_fetched == 0:
            print("Already up to date.")
        else:
            commit_word = "commit" if pull_result.commits_fetched == 1 else "commits"
            print(
                f"Pulled {pull_result.commits_fetched} {commit_word} from {remote_name}/{pull_result.ref_name}"
            )

        self._mutate(new_git, from_git=True)

        # Resolve related objects (for composite objects like Jobs)
        # Get refs from the store and resolve them to live objects
        self._resolve_related_objects_after_pull()

    def git_fetch(self, remote_name: str = "origin") -> Dict[str, int]:
        """Fetch from remote without merging."""
        self._ensure_git_init()
        return self._git.fetch(remote_name)

    @classmethod
    def git_clone(
        cls, alias: str, url: str = None, ref_name: str = "main", username: str = None
    ) -> "GitMixin":
        """Clone from a remote repository by alias.

        Args:
            alias: Repository alias. Can be:
                - Short: "my-survey" → resolves to "<username>/my-survey"
                - Fully qualified: "john/my-survey" → uses as-is
            url: Server URL. Defaults to EDSL_GIT_SERVER from config.
            ref_name: Branch to clone (default: "main")
            username: Username namespace for short aliases. If not provided and alias
                     doesn't contain "/", will try to get from Coop profile.

        Returns:
            New instance cloned from the remote repository.
        """
        # Get URL from config if not provided
        if url is None:
            from edsl.config import CONFIG

            url = CONFIG.get("EDSL_GIT_SERVER")

        # Resolve short alias to fully qualified
        resolved_alias = alias
        if "/" not in alias:
            if username is not None:
                resolved_alias = f"{username}/{alias}"
            else:
                try:
                    from edsl.coop import Coop

                    profile = Coop().get_profile()
                    resolved_alias = f"{profile['username']}/{alias}"
                except Exception:
                    raise MissingAliasError(
                        "Short alias requires a username namespace. Either provide a fully-qualified "
                        "alias (e.g., 'john/my-survey') or pass username='john'."
                    )

        # Create remote from URL and alias
        from edsl.versioning.http_remote import HTTPRemote

        remote = HTTPRemote.from_alias(url=url, alias=resolved_alias)

        view = clone_from_remote(remote, ref_name)
        git = ExpectedParrotGit(view)
        git = git.add_remote("origin", remote)
        rows = git.view.get_base_state()
        state = rows[0] if rows else {}
        instance = cls._from_state(state)
        instance._git = git
        return instance

    def git_log(
        self, limit: int = 20, *, porcelain: bool = False, color: bool = True
    ) -> Optional[List[Commit]]:
        """Display commit history in git-style format.

        Args:
            limit: Maximum number of commits to show (default: 20)
            porcelain: If True, return list of Commit objects instead of printing
            color: Enable ANSI color output (default: True, auto-disabled if not TTY)

        Returns:
            List of Commit objects if porcelain=True, otherwise None
        """
        self._ensure_git_init()
        commits = self._git.log(limit=limit)

        if porcelain:
            return commits

        # Build map of commit_id -> list of refs for decorations
        repo = self._git.view.repo
        refs = repo.list_refs()
        head_ref = self._git.view.head_ref
        head_commit = self._git.view.commit_hash

        commit_to_refs: Dict[str, List[str]] = {}
        for ref in refs:
            if ref.commit_id not in commit_to_refs:
                commit_to_refs[ref.commit_id] = []
            commit_to_refs[ref.commit_id].append(ref.name)

        # ANSI color codes
        use_color = color and sys.stdout.isatty()
        YELLOW = "\033[33m" if use_color else ""
        GREEN = "\033[32m" if use_color else ""
        CYAN = "\033[36m" if use_color else ""
        RESET = "\033[0m" if use_color else ""
        BOLD = "\033[1m" if use_color else ""

        # Print git-style log output with decorations
        for i, commit in enumerate(commits):
            if i > 0:
                print()  # Blank line between commits

            # Build decoration string like "(HEAD -> main, origin/main)"
            decorations = []
            if commit.commit_id == head_commit and head_ref:
                decorations.append(f"{BOLD}{CYAN}HEAD -> {GREEN}{head_ref}{RESET}")
            elif commit.commit_id in commit_to_refs:
                for ref_name in sorted(commit_to_refs[commit.commit_id]):
                    if ref_name != head_ref:  # Don't duplicate if already shown with HEAD
                        decorations.append(f"{GREEN}{ref_name}{RESET}")
                    elif commit.commit_id != head_commit:
                        # Show branch name without HEAD -> prefix
                        decorations.append(f"{GREEN}{ref_name}{RESET}")

            # Add any other refs for this commit (not the head ref)
            if commit.commit_id in commit_to_refs:
                for ref_name in sorted(commit_to_refs[commit.commit_id]):
                    ref_str = f"{GREEN}{ref_name}{RESET}"
                    # Avoid duplicates
                    if ref_str not in decorations and f"{BOLD}{CYAN}HEAD -> {GREEN}{ref_name}{RESET}" not in decorations:
                        decorations.append(ref_str)

            # Format commit line
            decoration_str = ""
            if decorations:
                decoration_str = f" {CYAN}({RESET}{', '.join(decorations)}{CYAN}){RESET}"

            print(f"{YELLOW}commit {commit.commit_id}{RESET}{decoration_str}")
            print(f"Author: {commit.author}")

            # Format timestamp like git
            ts_str = commit.timestamp.strftime("%a %b %d %H:%M:%S %Y %z")
            print(f"Date:   {ts_str}")
            print()

            # Indent message like git does
            for msg_line in commit.message.split("\n"):
                print(f"    {msg_line}")

        return None

    def git_status(self) -> Status:
        """Get current status."""
        self._ensure_git_init()
        base_status = self._git.status()

        # Detect stale state: data diverged from git state due to shared mutation
        # This happens when another reference modified the shared Store
        is_stale = False
        if not base_status.has_staged:
            # Only check if we don't have staged changes (otherwise data is expected to differ)
            committed_state = self._git.view.get_base_state()
            current_state = [self._to_state()]
            if committed_state != current_state:
                is_stale = True

        if is_stale:
            # Return a new Status with is_stale set
            return Status(
                repo_id=base_status.repo_id,
                head_commit=base_status.head_commit,
                head_ref=base_status.head_ref,
                is_detached=base_status.is_detached,
                has_staged=base_status.has_staged,
                staged_events=base_status.staged_events,
                is_behind=base_status.is_behind,
                is_stale=True,
            )
        return base_status

    def git_diff(
        self,
        *,
        color: bool = True,
        context: int = 3,
        porcelain: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Show diff between staged changes and committed version.

        Displays a git-style unified diff showing what would change if the
        current staged changes were committed. The diff is shown as JSON
        to properly represent the Store object structure.

        Args:
            color: Enable ANSI color output (default: True, auto-disabled if not TTY)
            context: Number of context lines around changes (default: 3)
            porcelain: If True, return dict with diff data instead of printing

        Returns:
            If porcelain=True, returns dict with:
                - 'has_changes': bool - whether there are staged changes
                - 'pending_events': list of (event_name, payload) tuples
                - 'diff_lines': list of diff lines (without color codes)
                - 'base_state': the committed state
                - 'current_state': the state with staged changes
            Otherwise returns None and prints colorized diff to stdout.

        Example:
            >>> sl = ScenarioList([Scenario({"a": 1})])
            >>> sl.git_commit("initial")
            >>> sl = sl.add(Scenario({"b": 2}))
            >>> sl.git_diff()  # Shows colorized diff
        """
        self._ensure_git_init()

        # Check if there are staged changes
        if not self._git.view.has_staged:
            if porcelain:
                return {
                    "has_changes": False,
                    "pending_events": [],
                    "diff_lines": [],
                    "base_state": None,
                    "current_state": None,
                }
            print("No staged changes (working tree clean)")
            return None

        # Get base (committed) state and current (with pending) state
        base_state_list = self._git.view.get_base_state()
        base_state = base_state_list[0] if base_state_list else {}
        current_state = self._to_state()

        # Get pending events for summary
        pending_events = list(self._git.view.pending_events)

        # Format states as JSON for diff
        def format_json(obj: Dict[str, Any]) -> List[str]:
            """Format object as pretty-printed JSON lines."""
            return json.dumps(obj, indent=2, sort_keys=True, default=str).splitlines()

        base_lines = format_json(base_state)
        current_lines = format_json(current_state)

        # Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                base_lines,
                current_lines,
                fromfile="committed",
                tofile="staged",
                lineterm="",
                n=context,
            )
        )

        if porcelain:
            return {
                "has_changes": True,
                "pending_events": pending_events,
                "diff_lines": diff_lines,
                "base_state": base_state,
                "current_state": current_state,
            }

        # Print colorized output
        use_color = color and sys.stdout.isatty()

        # ANSI color codes
        RED = "\033[31m" if use_color else ""
        GREEN = "\033[32m" if use_color else ""
        CYAN = "\033[36m" if use_color else ""
        YELLOW = "\033[33m" if use_color else ""
        RESET = "\033[0m" if use_color else ""
        BOLD = "\033[1m" if use_color else ""

        # Print pending events summary
        print(f"{BOLD}Staged changes:{RESET}")
        for event_name, payload in pending_events:
            # Show compact payload summary
            if payload:
                payload_summary = ", ".join(
                    f"{k}={_truncate(v, 30)}" for k, v in list(payload.items())[:3]
                )
                if len(payload) > 3:
                    payload_summary += ", ..."
                print(f"  {YELLOW}{event_name}{RESET}: {payload_summary}")
            else:
                print(f"  {YELLOW}{event_name}{RESET}")
        print()

        # Print diff
        print(f"{BOLD}Diff (committed → staged):{RESET}")
        for line in diff_lines:
            if line.startswith("+++") or line.startswith("---"):
                print(f"{BOLD}{line}{RESET}")
            elif line.startswith("@@"):
                print(f"{CYAN}{line}{RESET}")
            elif line.startswith("+"):
                print(f"{GREEN}{line}{RESET}")
            elif line.startswith("-"):
                print(f"{RED}{line}{RESET}")
            else:
                print(line)

        return None

    def git_merge(
        self,
        source_branch: str,
        *,
        message: Optional[str] = None,
        author: str = "unknown",
    ) -> None:
        """Merge source branch into current branch. Mutates in place.

        Uses a commutativity test on **materialized EDSL objects**:
        1. Get events from merge-base to current branch
        2. Get events from merge-base to source branch
        3. Apply events in order: current→source, materialize object, get hash
        4. Apply events in order: source→current, materialize object, get hash
        5. If hashes match, operations commute and merge succeeds
        6. If hashes differ, raise MergeConflictError

        This ensures semantic equality of the final EDSL objects, not just
        internal state representations.

        Args:
            source_branch: Name of branch to merge into current branch
            message: Custom merge commit message (default: auto-generated)
            author: Author of the merge commit

        Raises:
            StagedChangesError: If there are uncommitted changes
            DetachedHeadError: If in detached HEAD state
            RefNotFoundError: If source_branch doesn't exist
            NoMergeBaseError: If branches have no common ancestor
            MergeConflictError: If operations don't commute

        Example:
            >>> sl = ScenarioList([Scenario({"a": 1})])
            >>> sl.git_branch("feature")
            >>> sl = sl.append(Scenario({"b": 2}))
            >>> sl.git_commit("feature work")
            >>> sl.git_checkout("main")
            >>> sl = sl.append(Scenario({"c": 3}))
            >>> sl.git_commit("main work")
            >>> sl.git_merge("feature")
            Merge made by 'commutativity' strategy.
        """
        self._ensure_git_init()

        # Get merge info from git layer
        prep = self._git.prepare_merge(source_branch)

        # Handle already up to date case
        if prep.already_up_to_date:
            print("Already up to date.")
            return

        # Handle fast-forward case
        if prep.is_fast_forward:
            old_commit = self.commit_hash
            new_git = self._git.finalize_merge(prep, [], message=message, author=author)
            new_commit = new_git.view.commit_hash
            self._mutate(new_git, from_git=True)
            print(f"Updating {old_commit[:8]}..{new_commit[:8]}")
            print("Fast-forward")
            return

        # Three-way merge - perform commutativity test on EDSL objects
        from edsl.store import Store, create_event, apply_event

        def apply_events_to_state(
            base_state: Tuple[Dict[str, Any], ...],
            events: Tuple[Tuple[str, Dict[str, Any]], ...],
        ) -> Dict[str, Any]:
            """Apply events to state and return the final state dict."""
            state_dict = base_state[0] if base_state else {}
            store = Store(
                entries=list(state_dict.get("entries", [])),
                meta=dict(state_dict.get("meta", {})),
            )

            for event_name, event_payload in events:
                if event_name == "batch":
                    sub_events = event_payload.get("events", [])
                    for sub in sub_events:
                        sub_event = create_event(
                            sub["event_name"], sub["event_payload"]
                        )
                        apply_event(sub_event, store)
                else:
                    event = create_event(event_name, event_payload)
                    apply_event(event, store)

            return {"entries": store.entries, "meta": store.meta}

        # Test 1: current events then source events
        state1 = apply_events_to_state(
            prep.base_state, prep.current_events + prep.source_events
        )
        obj1 = self._from_state(state1)
        hash1 = hash(obj1)

        # Test 2: source events then current events
        state2 = apply_events_to_state(
            prep.base_state, prep.source_events + prep.current_events
        )
        obj2 = self._from_state(state2)
        hash2 = hash(obj2)

        # Check commutativity
        if hash1 != hash2:
            raise MergeConflictError(
                current_branch=prep.current_branch,
                source_branch=prep.source_branch,
                merge_base=prep.merge_base_id,
                hash_current_then_source=hash1,
                hash_source_then_current=hash2,
                current_events=list(prep.current_events),
                source_events=list(prep.source_events),
            )

        # Hashes match - finalize merge using obj1's state (either would work)
        final_state = [obj1._to_state()]
        new_git = self._git.finalize_merge(
            prep, final_state, message=message, author=author
        )
        self._mutate(new_git, from_git=True)
        print("Merge made by 'commutativity' strategy.")

    def git_branches(self) -> List[str]:
        """List all branches. Current branch is marked with '*'.

        Returns:
            List of branch names, with current branch prefixed by '* '
        """
        self._ensure_git_init()
        repo = self._git.view.repo
        refs = repo.list_refs()
        current_ref = self._git.view.head_ref

        branches = []
        for ref in refs:
            if ref.kind == "branch":
                if ref.name == current_ref:
                    branches.append(f"* {ref.name}")
                else:
                    branches.append(f"  {ref.name}")

        return branches

    def git_pending(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get pending events."""
        self._ensure_git_init()
        return list(self._git.view.pending_events)

    # --- Disk persistence (.ep format) ---

    def to_ep(self, path: str) -> None:
        """Save object with full git history to disk in .ep format.

        Creates a .ep file (compressed JSON) containing the complete git repository,
        including all commits, branches, and state snapshots. This allows round-trip
        serialization that preserves full history.

        Args:
            path: File path (will add .ep extension if not present)

        Raises:
            StagedChangesError: If there are uncommitted changes. Commit first.

        Example:
            >>> sl = ScenarioList([Scenario({"a": 1})])
            >>> sl.git_commit("initial")
            >>> sl.to_ep("/tmp/mydata")  # Creates /tmp/mydata.ep
        """
        self._ensure_git_init()

        # Require clean working state
        if self._git.view.has_staged:
            raise StagedChangesError("to_disk (commit changes first)")

        # Ensure .ep extension
        if not path.endswith(".ep"):
            path = path + ".ep"

        # Import version here to avoid circular imports
        from edsl import __version__

        data = {
            "edsl_class_name": self.__class__.__name__,
            "edsl_version": __version__,
            "git": {
                "repo": self._git.view.repo.to_dict(),
                "head_ref": self._git.view.head_ref,
                "base_commit": self._git.view.base_commit,
            },
        }

        # Write compressed JSON
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f)

        print(f"Saved to {path}")

    @classmethod
    def from_ep(cls, path: str, ref: str = "main") -> "GitMixin":
        """Load object with full git history from disk in .ep format.

        Loads a .ep file and reconstructs the object at the specified ref (branch,
        tag, or commit). The full git history is preserved, allowing checkout to
        any point in history.

        Args:
            path: File path (.ep extension auto-added if missing)
            ref: Branch, tag, or commit hash to checkout (default: "main")

        Returns:
            Instance at the specified ref with full history preserved.

        Raises:
            FileNotFoundError: If the file does not exist.
            InvalidEPFileError: If the file is not a valid .ep file.

        Example:
            >>> sl = ScenarioList.from_ep("/tmp/mydata")  # Loads at main
            >>> sl = ScenarioList.from_ep("/tmp/mydata", ref="feature")  # Loads at feature branch
            >>> sl = ScenarioList.from_ep("/tmp/mydata", ref="abc123")  # Loads at specific commit
        """
        # Try with .ep extension if not present and file doesn't exist
        if not path.endswith(".ep") and not os.path.exists(path):
            path = path + ".ep"

        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise  # Re-raise FileNotFoundError as-is
        except gzip.BadGzipFile:
            raise InvalidEPFileError(path, "not a valid gzip file")
        except json.JSONDecodeError as e:
            raise InvalidEPFileError(path, f"invalid JSON: {e}")
        except Exception as e:
            raise InvalidEPFileError(path, str(e))

        # Validate required structure
        if "git" not in data:
            raise InvalidEPFileError(path, "missing 'git' key")
        if "repo" not in data["git"]:
            raise InvalidEPFileError(path, "missing 'git.repo' key")

        # Reconstruct repo
        try:
            repo = InMemoryRepo.from_dict(data["git"]["repo"])
        except Exception as e:
            raise InvalidEPFileError(path, f"invalid repo data: {e}")

        # Reconstruct view at specified ref
        if repo.has_ref(ref):
            head_ref = ref
            base_commit = repo.get_ref(ref).commit_id
        else:
            # Try as commit hash
            head_ref = None
            if repo.has_commit(ref):
                base_commit = ref
            else:
                # Fall back to saved base_commit
                base_commit = data["git"]["base_commit"]

        view = ObjectView(repo=repo, head_ref=head_ref, base_commit=base_commit)

        # Create instance from current state
        state = view.get_base_state()
        instance = cls._from_state(state[0] if state else {})
        instance._git = ExpectedParrotGit(view)
        instance._needs_git_init = False

        return instance
