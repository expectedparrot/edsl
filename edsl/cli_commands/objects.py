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
    load_openable_json,
    output,
)


def register(app: click.Group) -> None:
    @app.command("clone")
    @click.argument("identifier")
    @click.option("--path", "output_path", default=None, help="Package path to save to.")
    def clone_object(identifier, output_path):
        """Clone an EDSL object into a git-backed .ep package.

        IDENTIFIER is a git remote URL (.../obj-<uuid>.git), a uuid, an
        owner/alias, or a Coop URL. An object whose git repo you can read comes
        with its full history; any other is fetched from Coop. Cloning adds no
        commit of its own.
        """
        try:
            from edsl.base import git_package as gitpkg
            from edsl.config import CONFIG
            from edsl.coop import Coop

            if gitpkg.uuid_from_remote_url(identifier):
                _git_clone(identifier, output_path, source=identifier)
                return

            coop_identifier = _coop_content_identifier(identifier, CONFIG.EXPECTED_PARROT_URL)
            coop_client = Coop()
            coop_info = None if _is_uuid(identifier) else _plain_dict(
                coop_client.get_metadata(coop_identifier)
            )
            object_uuid = identifier if coop_info is None else coop_info.get("uuid")
            remote_url = _own_repo_url(coop_client, object_uuid)
            if remote_url:
                alias = coop_info and coop_info.get("alias")
                _git_clone(remote_url, output_path, source=identifier, alias=alias)
                return

            obj = coop_client.get(coop_identifier)
            if coop_info is None:
                coop_info = _plain_dict(coop_client.get_metadata(coop_identifier))

            if not hasattr(obj, "git"):
                class_name = type(obj).__name__
                error(
                    "UNSUPPORTED_OBJECT",
                    f"Fetched object does not support git-backed packages: {class_name}",
                    suggestion=f"Use {class_name}.pull() from Python, or 'ep inspect' to view it.",
                    exit_code=EXIT_VALIDATION,
                )

            save_path = output_path or _default_clone_path(identifier, coop_info, obj)
            save_info = obj.git._save_overwriting_package(
                save_path, message=f"Clone {identifier}", coop_info=coop_info
            )

            data = {
                "object_type": type(obj).__name__,
                "path": str(obj.git.path),
                "source": identifier,
                "resolved_identifier": coop_identifier,
                "operation": "coop",
                "coop_info": coop_info,
                "save": save_info,
                "commit": save_info.get("commit"),
                "branch": save_info.get("branch"),
                "message": save_info.get("message"),
            }
            output(data)

        except SystemExit:
            raise
        except Exception as e:
            error(
                "CLONE_ERROR",
                str(e),
                suggestion="Check the identifier, your API key, and the destination path.",
                exit_code=EXIT_REMOTE,
            )


    def _git_clone(remote_url: str, output_path, *, source: str, alias=None) -> None:
        import shutil

        from edsl.base import git_package as gitpkg

        object_uuid = gitpkg.uuid_from_remote_url(remote_url)
        save_path = output_path or _safe_clone_name(alias or f"obj-{object_uuid}")
        destination = gitpkg.clone_destination(save_path, package_suffix=".ep")
        if destination.exists():
            error(
                "USAGE_ERROR",
                f"Destination already exists: {destination}",
                suggestion="Pass --path to clone somewhere else.",
                exit_code=EXIT_USAGE,
            )
        worktree_path = gitpkg.clone_package(remote_url, destination, package_suffix=".ep")
        try:
            commit = gitpkg.head_commit(worktree_path)
            branch = gitpkg.current_branch(worktree_path)
            origin = gitpkg.remote_url(worktree_path, gitpkg.REMOTE_NAME)
        finally:
            shutil.rmtree(worktree_path, ignore_errors=True)
        obj = load_git_object(destination)
        output(
            {
                "object_type": type(obj).__name__,
                "path": str(destination),
                "source": source,
                "operation": "git",
                "remote_url": origin,
                "object_uuid": object_uuid,
                "coop_info": obj.git._read_coop_info(),
                "commit": commit,
                "branch": branch,
            }
        )


    def _is_uuid(value: str) -> bool:
        from uuid import UUID

        try:
            UUID(value)
        except (TypeError, ValueError):
            return False
        return True


    def _own_repo_url(coop_client, object_uuid):
        """The remote URL of your git repo for ``object_uuid``; None if you have
        none, or Coop has no git host."""
        if not object_uuid:
            return None
        try:
            response = coop_client._send_server_request(uri="api/v0/git-repos", method="GET")
            coop_client._resolve_server_response(response)
            repos = response.json().get("objects", [])
        except Exception:
            return None
        return next(
            (repo["remote_url"] for repo in repos if repo.get("uuid") == str(object_uuid)),
            None,
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
        """Push or patch an EDSL object on Expected Parrot.

        OBJECT_PATH is a git-backed .ep package, or a .json/.json.gz file for
        objects that have no package format, such as prompts. A package goes
        to Coop, which picks its uuid on the first push; the package records
        it, then its history goes to the obj-<uuid> git repo Coop hands out,
        unless Coop has no git host.
        """
        source_path = Path(object_path)
        try:
            if source_path.is_file() and source_path.name.endswith((".json", ".json.gz")):
                _push_json_object(source_path, alias, description, visibility, force)
                return

            if not (source_path.is_dir() or source_path.suffix == ".ep"):
                error(
                    "USAGE_ERROR",
                    f"Push requires a git-backed .ep package or a .json file: {object_path}",
                    suggestion="Save the object as a .ep package (or .json for prompts), then run 'ep push <path>'.",
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

            from edsl.base.git_accessor import GitPushError

            had_coop_info = _object_has_coop_info(obj)
            try:
                info = obj.git.coop_push(
                    description=description,
                    alias=alias,
                    visibility=visibility,
                    force=force,
                    message=f"Push {source_path.name} to Expected Parrot",
                )
            except GitPushError as exc:
                error(
                    "GIT_PUSH_ERROR",
                    str(exc),
                    suggestion="Coop has the object. Run 'ep push' again to retry the git push.",
                    exit_code=EXIT_REMOTE,
                    details=[jsonable(exc.result)],
                )

            output(
                {
                    "object_type": type(obj).__name__,
                    "source": str(source_path),
                    "path": str(obj.git.path) if getattr(obj.git, "path", None) else None,
                    "operation": "patch" if had_coop_info else "push",
                    "coop_info": info.get("coop_info"),
                    "remote_url": obj.git.remotes().get(info["git"]["remote"]) if "git" in info else None,
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


    def _push_json_object(source_path: Path, alias, description, visibility, force):
        """Push a JSON-serialized object as a new Expected Parrot object.

        Only for objects with no .ep package format. Package-backed objects must
        be pushed as packages, which record the Coop object they belong to.
        """
        from edsl.coop import Coop

        obj = load_openable_json(source_path)
        if hasattr(obj, "git"):
            error(
                "USAGE_ERROR",
                f"{type(obj).__name__} must be pushed as a git-backed .ep package: {source_path}",
                suggestion="Save the object as a .ep package first, then run 'ep push <path.ep>'.",
                exit_code=EXIT_USAGE,
            )
        push_kwargs = {"description": description, "alias": alias, "force": force}
        if visibility is not None:
            push_kwargs["visibility"] = visibility
        info = Coop().push(obj, **push_kwargs)
        output(
            {
                "object_type": type(obj).__name__,
                "source": str(source_path),
                "operation": "push",
                "coop_info": jsonable(info),
            }
        )


    @app.command("log")
    @click.argument("object_path", type=click.Path(exists=True))
    @click.option("-n", "--max-count", type=int, default=None, help="Show at most this many commits.")
    @click.option("--oneline", is_flag=True, default=False, help="One '<short commit> <message>' line per commit.")
    def log_object(object_path, max_count, oneline):
        """Show the commit history in a git-backed .ep package, newest first."""
        import shutil

        from edsl.base import git_package as gitpkg

        source_path = Path(object_path)
        try:
            unpacked = not source_path.is_dir()
            worktree_path = (
                gitpkg.unpack_package_archive(source_path, package_suffix=".ep")
                if unpacked
                else source_path
            )
            try:
                commits = gitpkg.GitPackage(
                    worktree_path, package_suffix=".ep", object_type="object"
                ).log()
            finally:
                if unpacked:
                    shutil.rmtree(worktree_path, ignore_errors=True)
            commits = commits[:max_count] if max_count is not None else commits
            if oneline:
                commits = [f"{entry['commit'][:7]} {entry['message']}" for entry in commits]
            output({"path": str(source_path), "commits": commits})
        except SystemExit:
            raise
        except Exception as e:
            error(
                "LOG_ERROR",
                str(e),
                suggestion="Pass a git-backed .ep package.",
                exit_code=EXIT_VALIDATION,
            )


    @app.command("pull")
    @click.argument("object_path", type=click.Path(exists=True))
    def pull_object(object_path):
        """Update a git-backed package from its git repo, then from Coop.

        Fast-forwards from origin if the package has one, then fetches the
        Coop object if Coop has a newer version than the package records.
        """
        source_path = Path(object_path)
        try:
            from edsl.base import git_package as gitpkg

            if not (source_path.is_dir() or source_path.suffix == ".ep"):
                error(
                    "USAGE_ERROR",
                    f"Pull requires a git-backed .ep package: {object_path}",
                    suggestion="Use 'ep clone <owner>/<alias>' first, or pass a .ep package path.",
                    exit_code=EXIT_USAGE,
                )

            obj = load_git_object(source_path)
            has_origin = gitpkg.REMOTE_NAME in obj.git.remotes()
            if not has_origin and not _object_has_coop_info(obj):
                error(
                    "NO_REMOTE",
                    f"Package has no git remote and no coop_info.json: {object_path}",
                    suggestion="Use 'ep clone <owner>/<alias>' or 'ep push <path.ep>' first.",
                    exit_code=EXIT_VALIDATION,
                )

            before = obj.git.commit
            git_info = obj.git.pull(remote=gitpkg.REMOTE_NAME) if has_origin else None
            coop_info = None
            info = None
            if _object_has_coop_info(obj):
                info = obj.git._coop_pull_if_remote_updated(
                    message=f"Pull {source_path.name} from Expected Parrot"
                )
                coop_info = obj.git._read_coop_info()
            changed = info is not None or obj.git.commit != before
            output(
                {
                    "object_type": type(obj).__name__,
                    "source": str(source_path),
                    "path": str(obj.git.path) if getattr(obj.git, "path", None) else str(source_path),
                    "operation": "updated" if changed else "unchanged",
                    "coop_info": coop_info,
                    "commit": obj.git.commit,
                    "branch": obj.git.current_branch,
                    "git": git_info,
                    "result": info,
                }
            )

        except SystemExit:
            raise
        except Exception as e:
            error(
                "PULL_ERROR",
                str(e),
                suggestion="Check the package path, its remotes, and your Expected Parrot API key.",
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
        """Delete a remote object, and its git repo with it.

        TARGET is a uuid, URL, owner/alias, or a pushed .ep package.
        """
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


