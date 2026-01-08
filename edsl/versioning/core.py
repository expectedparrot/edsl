"""
Object versioning core infrastructure.

This module re-exports from the split submodules for convenience.
See individual modules for implementation details:
- utils.py: Utility functions
- models.py: Data classes (Event, Commit, Ref, Status, etc.)
- protocols.py: Repo and Remote protocols
- storage.py: BaseObjectStore, InMemoryRepo, InMemoryRemote
- git_facade.py: ObjectView, ExpectedParrotGit, bootstrapping functions
- mixin.py: GitMixin, event decorator
"""

# Utilities
from .utils import _utcnow, _sha256, _stable_dumps

# Models
from .models import (
    Event,
    Commit,
    Ref,
    PushResult,
    PullResult,
    Status,
)

# Protocols
from .protocols import Repo, Remote

# Storage
from .storage import BaseObjectStore, InMemoryRepo, InMemoryRemote

# Git facade
from .git_facade import (
    ObjectView,
    ExpectedParrotGit,
    clone_from_remote,
    init_repo,
)

# Mixin
from .mixin import GitMixin, event

__all__ = [
    # Utilities
    '_utcnow',
    '_sha256',
    '_stable_dumps',
    # Models
    'Event',
    'Commit',
    'Ref',
    'PushResult',
    'PullResult',
    'Status',
    # Protocols
    'Repo',
    'Remote',
    # Storage
    'BaseObjectStore',
    'InMemoryRepo',
    'InMemoryRemote',
    # Git facade
    'ObjectView',
    'ExpectedParrotGit',
    'clone_from_remote',
    'init_repo',
    # Mixin
    'GitMixin',
    'event',
]
