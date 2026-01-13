"""
GitMixin - Mixin to add git-like versioning to any class.

Provides the event decorator and GitMixin class.
"""

from __future__ import annotations

import re
import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .models import Commit, PushResult, Status
from .protocols import Remote
from .git_facade import ExpectedParrotGit, ObjectView, init_repo, clone_from_remote
from .exceptions import InvalidAliasError, MissingAliasError


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
        author: str = "service",
    ) -> "GitMixin":
        """Create a new instance with new data and commit.

        This is used by versioned services to create a new version
        while preserving git history. The original object is NOT modified.

        Args:
            new_data: The new data to use. Can be:
                - A dict (will be used to create new instance)
                - An instance of the same type (data will be extracted)
                - A list of entries (for list-based objects)
            operation: Name of the operation that produced this data
            params: Parameters used in the operation (for audit trail)
            author: Author of the change

        Returns:
            A new instance with the changes committed (original unchanged)
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

        # Build commit message
        param_str = ""
        if params:
            param_items = [f"{k}={repr(v)[:50]}" for k, v in list(params.items())[:3]]
            param_str = f" ({', '.join(param_items)})"
        message = f"{operation}{param_str}"

        # Add a synthetic event so commit() has something to commit
        # This records the service operation in the event history
        event_payload = {
            "operation": operation,
            "params": params or {},
            "entries_count": len(new_state.get("entries", [])),
        }
        new_instance._git = new_instance._git.apply_event("replace", event_payload)

        # Commit the change on the new instance
        current_state = [new_instance._to_state()]
        new_git = new_instance._git.commit(
            message, author=author, force=False, state=current_state
        )
        new_instance._git = new_git

        return new_instance

    def git_branch(self, name: str) -> None:
        """Create and checkout a new branch. Mutates in place.

        Args:
            name: Name of the new branch to create
        """
        self._ensure_git_init()
        old_branch = self._git.view.head_ref or "HEAD"
        new_git = self._git.branch(name)
        self._mutate(new_git)

        # Print git-style status
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
        """Pull from remote. Mutates in place."""
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

    def git_log(self, limit: int = 20) -> List[Commit]:
        """Get commit history."""
        self._ensure_git_init()
        return self._git.log(limit=limit)

    def git_status(self) -> Status:
        """Get current status."""
        self._ensure_git_init()
        return self._git.status()

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
