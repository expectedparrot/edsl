"""Object and Coop commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_REMOTE,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    jsonable,
    load_git_object,
    output,
)


def register(app: click.Group) -> None:
    @app.command("clone")
    @click.argument("identifier")
    @click.option("--path", "output_path", default=None, help="Package path to save to.")
    def clone_object(identifier, output_path):
        """Clone a shared EDSL object into a git-backed package."""
        try:
            from edsl.config import CONFIG
            from edsl.coop import Coop

            coop_identifier = _coop_content_identifier(identifier, CONFIG.EXPECTED_PARROT_URL)
            coop_client = Coop()
            obj = coop_client.get(coop_identifier)
            coop_info = coop_client.get_metadata(coop_identifier)
            coop_info = _plain_dict(coop_info)

            if not hasattr(obj, "git"):
                error(
                    "UNSUPPORTED_OBJECT",
                    f"Fetched object does not support git-backed packages: {type(obj).__name__}",
                    suggestion="Use an EDSL object type with .git support.",
                    exit_code=EXIT_VALIDATION,
                )

            save_path = output_path or _default_clone_path(identifier, coop_info, obj)
            save_info = obj.git.save(save_path, message=f"Clone {identifier}")
            coop_commit_info = obj.git._write_coop_info_and_commit(
                coop_info,
                message=f"Store Coop info for {identifier}",
            )

            data = {
                "object_type": type(obj).__name__,
                "path": str(obj.git.path),
                "source": identifier,
                "resolved_identifier": coop_identifier,
                "coop_info": coop_info,
                "save": save_info,
                "commit": coop_commit_info.get("commit"),
                "branch": coop_commit_info.get("branch"),
                "message": coop_commit_info.get("message"),
            }
            output(data)

        except SystemExit:
            raise
        except Exception as e:
            error(
                "CLONE_ERROR",
                str(e),
                suggestion="Check the owner/alias, your API key, and the destination path.",
                exit_code=EXIT_REMOTE,
            )


    def _coop_content_identifier(identifier: str, expected_parrot_url: str) -> str:
        if identifier.startswith(("http://", "https://")):
            return identifier
        is_uuid = len(identifier) == 36 and identifier.count("-") == 4
        if is_uuid:
            return identifier
        if "/" in identifier:
            return f"{expected_parrot_url.rstrip('/')}/content/{identifier.strip('/')}"
        return identifier


    def _default_clone_path(identifier: str, coop_info: dict, obj) -> str:
        alias = coop_info.get("alias")
        if not alias and "/" in identifier and not identifier.startswith(("http://", "https://")):
            alias = identifier.strip("/").split("/")[-1]
        if not alias and coop_info.get("alias_url"):
            alias = str(coop_info["alias_url"]).rstrip("/").split("/")[-1]
        if not alias:
            alias = type(obj).__name__.lower()
        return _safe_clone_name(str(alias))


    def _safe_clone_name(value: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value)
        safe = safe.strip(".-")
        return safe or "edsl_object"


    def _plain_dict(value) -> dict:
        if hasattr(value, "items"):
            return dict(value)
        if hasattr(value, "__dict__"):
            return {key: val for key, val in value.__dict__.items() if not key.startswith("_")}
        return {"value": str(value)}


    def _remote_identifier(target: str) -> str:
        """Resolve a UUID/URL/owner-alias or a local .ep package to a remote identifier."""
        path = Path(target)
        if path.exists():
            if not (path.is_dir() or path.suffix == ".ep"):
                error(
                    "USAGE_ERROR",
                    f"Expected a remote identifier or .ep package: {target}",
                    suggestion="Use a UUID, URL, owner/alias, or a git-backed .ep package.",
                    exit_code=EXIT_USAGE,
                )
            obj = load_git_object(path)
            coop_info = obj.git._read_coop_info()
            if not coop_info:
                error(
                    "NO_COOP_INFO",
                    f"No coop_info.json found for package: {target}",
                    suggestion="Use 'ep clone <owner>/<alias>' or 'ep push <path.ep>' first.",
                    exit_code=EXIT_VALIDATION,
                )
            return obj.git._coop_identifier(coop_info)
        from edsl.config import CONFIG

        return _coop_content_identifier(target, CONFIG.EXPECTED_PARROT_URL)


    @app.command("push")
    @click.argument("object_path", type=click.Path(exists=True))
    @click.option("--alias", default=None, help="Short Expected Parrot alias.")
    @click.option("--description", default=None, help="Object description.")
    @click.option("--visibility", default=None, help="private, public, or unlisted.")
    @click.option("--force", is_flag=True, default=False, help="Patch an existing alias conflict when creating.")
    def push_object(object_path, alias, description, visibility, force):
        """Push or patch an EDSL object on Expected Parrot."""
        source_path = Path(object_path)
        try:
            if not (source_path.is_dir() or source_path.suffix == ".ep"):
                error(
                    "USAGE_ERROR",
                    f"Push requires a git-backed .ep package: {object_path}",
                    suggestion="Save the object as a .ep package first, then run 'ep push <path.ep>'.",
                    exit_code=EXIT_USAGE,
                )

            obj = load_git_object(source_path)
            if not hasattr(obj, "git"):
                error(
                    "UNSUPPORTED_OBJECT",
                    f"Object does not support git-backed packages: {type(obj).__name__}",
                    suggestion="Use an EDSL object type with .git support.",
                    exit_code=EXIT_VALIDATION,
                )

            had_coop_info = _object_has_coop_info(obj)
            info = obj.git.coop_push(
                description=description,
                alias=alias,
                visibility=visibility,
                force=force,
                message=f"Push {source_path.name} to Expected Parrot",
            )

            output(
                {
                    "object_type": type(obj).__name__,
                    "source": str(source_path),
                    "path": str(obj.git.path) if getattr(obj.git, "path", None) else None,
                    "operation": "patch" if had_coop_info else "push",
                    "coop_info": info.get("coop_info"),
                    "commit": info.get("commit"),
                    "branch": info.get("branch"),
                    "message": info.get("message"),
                    "result": info,
                }
            )

        except SystemExit:
            raise
        except Exception as e:
            error(
                "PUSH_ERROR",
                str(e),
                suggestion="Check the object path, alias, visibility, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    @app.command("pull")
    @click.argument("object_path", type=click.Path(exists=True))
    def pull_object(object_path):
        """Fetch the latest Expected Parrot object into a git-backed package."""
        source_path = Path(object_path)
        try:
            if not (source_path.is_dir() or source_path.suffix == ".ep"):
                error(
                    "USAGE_ERROR",
                    f"Pull requires a git-backed .ep package: {object_path}",
                    suggestion="Use 'ep clone <owner>/<alias>' first, or pass a .ep package path.",
                    exit_code=EXIT_USAGE,
                )

            obj = load_git_object(source_path)
            if not _object_has_coop_info(obj):
                error(
                    "NO_COOP_INFO",
                    f"No coop_info.json found for package: {object_path}",
                    suggestion="Use 'ep clone <owner>/<alias>' or 'ep push <object>' first.",
                    exit_code=EXIT_VALIDATION,
                )

            info = obj.git._coop_pull_if_remote_updated(
                message=f"Pull {source_path.name} from Expected Parrot"
            )
            coop_info = obj.git._read_coop_info()
            if info is None:
                info = {
                    "status": "unchanged",
                    "path": str(obj.git.path),
                    "commit": getattr(obj.git, "commit", None),
                    "branch": getattr(obj.git, "current_branch", None),
                    "message": "remote metadata is not newer",
                }
            status = info.get("status")
            output(
                {
                    "object_type": type(obj).__name__,
                    "source": str(source_path),
                    "path": str(obj.git.path) if getattr(obj.git, "path", None) else str(source_path),
                    "operation": "unchanged" if status == "unchanged" else "updated",
                    "coop_info": coop_info,
                    "commit": info.get("commit"),
                    "branch": info.get("branch"),
                    "message": info.get("message"),
                    "result": info,
                }
            )

        except SystemExit:
            raise
        except Exception as e:
            error(
                "PULL_ERROR",
                str(e),
                suggestion="Check the package path, stored Coop info, and Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    def _object_has_coop_info(obj) -> bool:
        try:
            return obj.git._read_coop_info() is not None
        except Exception:
            return False


    @app.command("metadata")
    @click.argument("target")
    def metadata(target):
        """Get metadata for a remote object or local .ep package."""
        try:
            from edsl.coop import Coop

            identifier = _remote_identifier(target)
            output(jsonable(Coop().get_metadata(identifier)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "METADATA_ERROR",
                str(e),
                suggestion="Check the object identifier and your Expected Parrot API key.",
                exit_code=EXIT_REMOTE,
            )


    @app.command("update-metadata")
    @click.argument("target")
    @click.option("--description", default=None, help="New object description.")
    @click.option("--alias", default=None, help="New object alias.")
    @click.option("--visibility", default=None, help="private, public, or unlisted.")
    def update_metadata(target, description, alias, visibility):
        """Update remote object metadata without changing object contents."""
        if description is None and alias is None and visibility is None:
            error(
                "USAGE_ERROR",
                "Nothing to update.",
                suggestion="Provide at least one of --description, --alias, or --visibility.",
                exit_code=EXIT_USAGE,
            )
        try:
            from edsl.coop import Coop

            identifier = _remote_identifier(target)
            result = Coop().patch_metadata(
                identifier,
                description=description,
                alias=alias,
                visibility=visibility,
            )
            output(jsonable(result))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "METADATA_ERROR",
                str(e),
                suggestion="Check the object identifier, metadata values, and API key.",
                exit_code=EXIT_REMOTE,
            )


    @app.command("share")
    @click.argument("target")
    @click.option("--user", "username_or_email", required=True, help="Expected Parrot username or email.")
    def share(target, username_or_email):
        """Share a remote object or local .ep package with a user."""
        try:
            from edsl.coop import Coop

            identifier = _remote_identifier(target)
            output(jsonable(Coop().share_object(identifier, username_or_email)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SHARE_ERROR",
                str(e),
                suggestion="Check the object identifier, recipient, and API key.",
                exit_code=EXIT_REMOTE,
            )


    @app.command("unshare")
    @click.argument("target")
    @click.option("--user", "username_or_email", required=True, help="Expected Parrot username or email.")
    def unshare(target, username_or_email):
        """Remove a user's access to a remote object or local .ep package."""
        try:
            from edsl.coop import Coop

            identifier = _remote_identifier(target)
            output(jsonable(Coop().unshare_object(identifier, username_or_email)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SHARE_ERROR",
                str(e),
                suggestion="Check the object identifier, recipient, and API key.",
                exit_code=EXIT_REMOTE,
            )


    @app.command("shared")
    @click.argument("target")
    def shared(target):
        """List users a remote object or local .ep package is shared with."""
        try:
            from edsl.coop import Coop

            identifier = _remote_identifier(target)
            output(jsonable(Coop().get_object_shared_users(identifier)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SHARE_ERROR",
                str(e),
                suggestion="Check the object identifier and API key.",
                exit_code=EXIT_REMOTE,
            )


    @app.command("delete")
    @click.argument("target")
    @click.option("--yes", is_flag=True, default=False, help="Confirm deletion.")
    def delete(target, yes):
        """Delete a remote object."""
        if not yes:
            error(
                "CONFIRMATION_REQUIRED",
                "Deleting a remote object requires --yes.",
                suggestion="Re-run with --yes if you intend to permanently delete this object.",
                exit_code=EXIT_USAGE,
            )
        try:
            from edsl.coop import Coop

            identifier = _remote_identifier(target)
            output(jsonable(Coop().delete(identifier)))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "DELETE_ERROR",
                str(e),
                suggestion="Check the object identifier and API key.",
                exit_code=EXIT_REMOTE,
            )


    # ---------------------------------------------------------------------------
    # ep search
    # ---------------------------------------------------------------------------

    def _search_objects(query, obj_type, visibility, community, page, page_size):
        try:
            from edsl.coop import Coop
            coop_client = Coop()

            kwargs = {
                "page": page,
                "page_size": page_size,
                "community": community,
            }
            if query:
                kwargs["search_query"] = query
            if obj_type:
                kwargs["object_type"] = obj_type
            if visibility:
                kwargs["visibility"] = visibility

            result = coop_client.list(**kwargs)

            objects = []
            for item in result:
                obj = {}
                if hasattr(item, 'items'):
                    obj = dict(item)
                elif hasattr(item, '__dict__'):
                    obj = {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
                else:
                    obj = dict(item) if hasattr(item, '__iter__') else {"value": str(item)}
                objects.append(obj)

            data = {
                "objects": objects,
                "page": page,
                "page_size": page_size,
                "returned_count": len(objects),
                "query": query,
                "type": obj_type,
                "visibility": visibility,
                "community": community,
            }
            for attr in ("current_page", "total_pages", "total_count"):
                if hasattr(result, attr):
                    data[attr] = getattr(result, attr)
            if hasattr(result, "page_size"):
                data["page_size"] = getattr(result, "page_size")
            output(data)

        except SystemExit:
            raise
        except Exception as e:
            error("SEARCH_ERROR", str(e),
                   suggestion="Check your API key with 'ep auth status'.",
                   exit_code=EXIT_REMOTE)


    @app.command("search")
    @click.option("--query", "-q", default=None, help="Search by description.")
    @click.option("--type", "obj_type", default=None, help="Filter by object type.")
    @click.option("--visibility", default=None, help="public, private, unlisted.")
    @click.option("--community", is_flag=True, default=False, help="Search community objects.")
    @click.option("--page", default=1, type=int, help="Page number.")
    @click.option("--page_size", default=10, type=int, help="Results per page (max 100).")
    def search(query, obj_type, visibility, community, page, page_size):
        """Search for shared EDSL objects."""
        _search_objects(query, obj_type, visibility, community, page, page_size)


