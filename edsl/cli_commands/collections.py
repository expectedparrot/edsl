"""Local Collection package commands."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_REMOTE,
    EXIT_USAGE,
    error,
    load_git_object,
    output,
)


def register(collections_group: click.Group) -> None:
    @collections_group.command("create")
    @click.option("--name", required=True, help="Collection name.")
    @click.option("--purpose", default="", help="What this collection is for.")
    @click.option("--tag", "tags", multiple=True, help="Collection tag. Repeat for multiple tags.")
    @click.option("--output", "output_path", required=True, help="Destination .ep package.")
    def create_collection(name: str, purpose: str, tags: tuple[str, ...], output_path: str) -> None:
        """Create an empty local Collection package.

        Examples:
          ep collections create --name "Marketing playbooks" --purpose "Research workflows" --tag marketing --output marketing.ep
        """
        try:
            from edsl.collections import Collection

            collection = Collection(name=name, purpose=purpose, tags=list(tags))
            saved = _save_collection(collection, output_path, "Create Collection")
            output({"object_type": "Collection", "name": collection.name, "item_count": 0, "saved": saved})
        except SystemExit:
            raise
        except Exception as exc:
            error("COLLECTION_CREATE_ERROR", str(exc), exit_code=EXIT_ERROR)

    @collections_group.command("from-search")
    @click.option("--name", required=True, help="Collection name.")
    @click.option("--purpose", default="", help="What this collection is for.")
    @click.option("--tag", "tags", multiple=True, help="Collection tag. Repeat for multiple tags.")
    @click.option("--query", "query", default=None, help="Search Coop descriptions.")
    @click.option("--type", "object_type", default=None, help="Filter by Coop object type.")
    @click.option("--visibility", default=None, help="Filter by visibility: public, private, or unlisted.")
    @click.option("--community", is_flag=True, help="Search public community objects.")
    @click.option("--page", default=1, type=click.IntRange(min=1), show_default=True)
    @click.option("--page-size", default=100, type=click.IntRange(min=1, max=100), show_default=True)
    @click.option("--output", "output_path", required=True, help="Destination .ep package.")
    def collection_from_search(
        name: str,
        purpose: str,
        tags: tuple[str, ...],
        query: str | None,
        object_type: str | None,
        visibility: str | None,
        community: bool,
        page: int,
        page_size: int,
        output_path: str,
    ) -> None:
        """Create a local Collection from one page of Coop search results.

        Search results contribute only object type, UUID, and version. Descriptions
        and other changing Coop metadata are resolved when requested.
        """
        try:
            from edsl.collections import Collection
            from edsl.coop import Coop

            result = Coop().list(
                object_type=object_type,
                visibility=visibility,
                search_query=query,
                page=page,
                page_size=page_size,
                community=community,
            )
            collection = Collection(name=name, purpose=purpose, tags=list(tags))
            for item in result:
                data = dict(item)
                collection.add(
                    object_type=data["object_type"],
                    object_uuid=data["uuid"],
                    version_at_add=str(data["version"]) if data.get("version") is not None else None,
                )

            saved = _save_collection(collection, output_path, "Create Collection from Coop search")
            total_pages = getattr(result, "total_pages", None)
            warnings = []
            if total_pages and page < total_pages:
                warnings.append(
                    f"Saved page {page} of {total_pages}; rerun with another --page to add more search results."
                )
            output({
                "object_type": "Collection",
                "name": collection.name,
                "item_count": len(collection),
                "search": {
                    "query": query,
                    "type": object_type,
                    "visibility": visibility,
                    "community": community,
                    "page": page,
                    "page_size": page_size,
                    "total_count": getattr(result, "total_count", None),
                    "total_pages": total_pages,
                },
                "saved": saved,
            }, warnings=warnings)
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "COLLECTION_SEARCH_ERROR",
                str(exc),
                suggestion="Check the search filters and Coop authentication with 'ep auth status'.",
                exit_code=EXIT_REMOTE,
            )

    @collections_group.command("add")
    @click.argument("collection_path", type=click.Path(exists=True))
    @click.argument("object_uuid")
    @click.option("--type", "object_type", required=True, help="Coop object type, such as prompt or survey.")
    @click.option("--version-at-add", default=None, help="Version string to record with this reference.")
    def add_item(collection_path: str, object_uuid: str, object_type: str, version_at_add: str | None) -> None:
        """Add a typed Coop UUID reference to a local Collection."""
        try:
            collection = _load_collection(collection_path)
            collection.add(object_type, object_uuid, version_at_add=version_at_add)
            saved = _save_collection(collection, collection_path, f"Add {object_type} to Collection")
            output({"name": collection.name, "item_count": len(collection), "added": {"object_type": object_type, "object_uuid": object_uuid}, "saved": saved})
        except SystemExit:
            raise
        except Exception as exc:
            error("COLLECTION_ADD_ERROR", str(exc), exit_code=EXIT_ERROR)

    @collections_group.command("remove")
    @click.argument("collection_path", type=click.Path(exists=True))
    @click.argument("object_uuid")
    @click.option("--type", "object_type", default=None, help="Required when the UUID appears under multiple types.")
    def remove_item(collection_path: str, object_uuid: str, object_type: str | None) -> None:
        """Remove a UUID reference from a local Collection."""
        try:
            collection = _load_collection(collection_path)
            collection.remove(object_uuid, object_type=object_type)
            saved = _save_collection(collection, collection_path, "Remove object from Collection")
            output({"name": collection.name, "item_count": len(collection), "removed_uuid": object_uuid, "saved": saved})
        except SystemExit:
            raise
        except Exception as exc:
            error("COLLECTION_REMOVE_ERROR", str(exc), exit_code=EXIT_ERROR)

    @collections_group.command("show")
    @click.argument("collection_path", type=click.Path(exists=True))
    def show_collection(collection_path: str) -> None:
        """Show the local Collection metadata and ordered references."""
        try:
            collection = _load_collection(collection_path)
            output({
                "object_type": "Collection",
                "name": collection.name,
                "purpose": collection.purpose,
                "tags": collection.tags,
                "metadata": collection.metadata,
                "item_count": len(collection),
                "items": [item.to_dict() for item in collection],
                "path": str(collection_path),
            })
        except SystemExit:
            raise
        except Exception as exc:
            error("COLLECTION_SHOW_ERROR", str(exc), exit_code=EXIT_ERROR)

    @collections_group.command("metadata")
    @click.argument("collection_path", type=click.Path(exists=True))
    def collection_metadata(collection_path: str) -> None:
        """Fetch current Coop metadata for each member without fetching contents."""
        try:
            collection = _load_collection(collection_path)
            members = collection.fetch_metadata()
            output({"name": collection.name, "member_count": len(members), "members": members})
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "COLLECTION_METADATA_ERROR",
                str(exc),
                suggestion="Check Coop authentication and whether every member is still accessible.",
                exit_code=EXIT_REMOTE,
            )


def _load_collection(path: str):
    from edsl.collections import Collection

    collection = load_git_object(Path(path))
    if not isinstance(collection, Collection):
        error("UNSUPPORTED_OBJECT", f"Expected a Collection package, got {type(collection).__name__}.", exit_code=EXIT_USAGE)
    return collection


def _save_collection(collection, path: str, message: str) -> dict:
    info = collection.git.save(path, message=message)
    return {"path": info.get("path", path), "commit": info.get("commit"), "branch": info.get("branch")}
