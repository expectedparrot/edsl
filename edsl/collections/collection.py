"""Metadata-only collections that organize objects stored on Coop."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from edsl.base import Base
from .collection_git import CollectionGitDescriptor


SUPPORTED_OBJECT_TYPES = frozenset(
    {
        "agent", "agent_list", "cache", "collection", "composite_macro",
        "macro", "model", "model_list", "notebook", "prompt", "question",
        "results", "scenario", "scenario_list", "survey",
    }
)


@dataclass(frozen=True)
class CollectionItem:
    """A typed reference to a Coop object; the object's content is not embedded."""

    object_type: str
    object_uuid: str
    added_at: Optional[str] = None
    version_at_add: Optional[str] = None

    def __post_init__(self) -> None:
        if self.object_type not in SUPPORTED_OBJECT_TYPES:
            raise ValueError(f"Unsupported Coop object type: {self.object_type!r}")
        try:
            normalized_uuid = str(UUID(str(self.object_uuid)))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"Invalid Coop object UUID: {self.object_uuid!r}") from exc
        object.__setattr__(self, "object_uuid", normalized_uuid)
        if self.added_at is None:
            object.__setattr__(self, "added_at", datetime.now(timezone.utc).isoformat())
        elif not isinstance(self.added_at, str) or not self.added_at:
            raise ValueError("added_at must be a non-empty ISO timestamp string")
        if self.version_at_add is not None and not isinstance(self.version_at_add, str):
            raise TypeError("version_at_add must be a string or None")

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_type": self.object_type,
            "object_uuid": self.object_uuid,
            "added_at": self.added_at,
            "version_at_add": self.version_at_add,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollectionItem":
        return cls(**data)


class Collection(Base):
    """An ordered set of typed Coop object references plus collection metadata.

    Member descriptions, aliases, and content are intentionally not copied.
    Resolve the UUIDs against Coop when displaying current object details.
    """

    git = CollectionGitDescriptor()

    def __init__(
        self,
        name: str,
        purpose: str = "",
        items: Optional[list[CollectionItem | dict[str, Any]]] = None,
        *,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Collection name must be a non-empty string")
        if not isinstance(purpose, str):
            raise TypeError("purpose must be a string")
        if tags is not None and any(not isinstance(tag, str) for tag in tags):
            raise TypeError("tags must contain only strings")
        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("metadata must be a dictionary")
        self.name = name.strip()
        self.purpose = purpose
        self.tags = list(tags or [])
        self.metadata = dict(metadata or {})
        self.items: list[CollectionItem] = []
        for item in items or []:
            self._append_item(item)

    def _append_item(self, item: CollectionItem | dict[str, Any]) -> None:
        if isinstance(item, dict):
            item = CollectionItem.from_dict(item)
        if not isinstance(item, CollectionItem):
            raise TypeError("items must be CollectionItem objects or dictionaries")
        key = (item.object_type, item.object_uuid)
        if any((old.object_type, old.object_uuid) == key for old in self.items):
            raise ValueError(f"Object is already in this collection: {key}")
        self.items.append(item)

    def add(
        self,
        object_type: str,
        object_uuid: str,
        *,
        version_at_add: Optional[str] = None,
        added_at: Optional[str] = None,
    ) -> "Collection":
        self._append_item(
            CollectionItem(object_type, object_uuid, added_at, version_at_add)
        )
        return self

    def remove(self, object_uuid: str, object_type: Optional[str] = None) -> "Collection":
        normalized_uuid = str(UUID(str(object_uuid)))
        matches = [
            item for item in self.items
            if item.object_uuid == normalized_uuid
            and (object_type is None or item.object_type == object_type)
        ]
        if not matches:
            raise KeyError(object_uuid)
        if len(matches) > 1:
            raise ValueError("UUID matches multiple member types; provide object_type")
        self.items.remove(matches[0])
        return self

    def fetch(self, *, expected_parrot_url: Optional[str] = None) -> list[Any]:
        """Fetch every referenced object as an EDSL instance, in collection order.

        This downloads and deserializes each member. Use fetch_metadata() when
        only Coop's object metadata is needed.
        """
        from edsl.coop import Coop

        coop = Coop(url=expected_parrot_url)
        return [
            coop.get(item.object_uuid, expected_object_type=item.object_type)
            for item in self.items
        ]

    def fetch_metadata(
        self, *, expected_parrot_url: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Fetch Coop metadata for each member without downloading its content.

        Results preserve collection order and include fields such as object type,
        UUID, alias, owner, visibility, and version.
        """
        from edsl.coop import Coop

        coop = Coop(url=expected_parrot_url)
        metadata = []
        for item in self.items:
            item_metadata = coop.get_metadata(item.object_uuid)
            actual_type = item_metadata.get("object_type")
            if actual_type and actual_type != item.object_type:
                raise ValueError(
                    f"Collection records {item.object_uuid} as {item.object_type!r}, "
                    f"but Coop reports {actual_type!r}"
                )
            metadata.append(item_metadata)
        return metadata

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def to_dict(self, add_edsl_version: bool = True) -> dict[str, Any]:
        data = {
            "name": self.name,
            "purpose": self.purpose,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "items": [item.to_dict() for item in self.items],
        }
        if add_edsl_version:
            from edsl import __version__
            data["edsl_version"] = __version__
            data["edsl_class_name"] = "Collection"
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Collection":
        return cls(
            name=data["name"],
            purpose=data.get("purpose", ""),
            items=data.get("items", []),
            tags=data.get("tags"),
            metadata=data.get("metadata"),
        )

    @classmethod
    def example(cls) -> "Collection":
        return cls(
            name="Marketing operations playbooks",
            purpose="Reusable research workflows for marketing operations.",
            tags=["marketing", "operations", "playbook"],
        )

    def code(self) -> str:
        return f"Collection.from_dict({self.to_dict(add_edsl_version=False)!r})"

    def _eval_repr_(self) -> str:
        return self.code()

    def _summary_repr(self) -> str:
        return f"Collection({self.name!r}, {len(self.items)} items)"

    def __repr__(self) -> str:
        return self._summary_repr()
