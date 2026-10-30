"""Metadata-only collections of EDSL objects."""

from .collection import Collection, CollectionItem
from .collection_git import (
    CollectionGitDescriptor,
    CollectionGitError,
    CollectionGitPackage,
)

__all__ = ["Collection", "CollectionItem", "CollectionGitDescriptor", "CollectionGitError", "CollectionGitPackage"]
