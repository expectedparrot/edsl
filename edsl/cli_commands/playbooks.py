"""Commands for managing reusable EDSL prompts (playbooks) on Coop."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import click
from platformdirs import user_cache_path

from edsl.cli_shared import EXIT_REMOTE, EXIT_USAGE, error, jsonable, output


def register(app: click.Group) -> None:
    @app.group("playbooks", invoke_without_command=True)
    @click.pass_context
    def playbooks(ctx):
        """Find, inspect, and publish reusable EDSL prompts on Expected Parrot."""
        if ctx.invoked_subcommand is None:
            output({"commands": ["list", "search", "show", "push", "update"]})

    @playbooks.command("list")
    @click.option("--visibility", type=click.Choice(["private", "public", "unlisted"]))
    @click.option(
        "--namespace",
        default="mine",
        show_default=True,
        help="Search scope: 'mine', 'ep', or an owner username.",
    )
    @click.option(
        "--routing",
        is_flag=True,
        help="Return compact name, description, and fetch guidance.",
    )
    @click.option(
        "--refresh", is_flag=True, help="Refresh the local metadata catalog from Coop."
    )
    @click.option("--page", default=1, type=click.IntRange(min=1))
    @click.option("--page-size", default=20, type=click.IntRange(min=1, max=100))
    def list_playbooks(visibility, namespace, routing, refresh, page, page_size):
        """List playbooks in your, EP, or a named owner's namespace."""
        try:
            from edsl.coop import Coop

            coop = Coop()
            catalog, cache = _namespace_catalog(
                coop, namespace=namespace, visibility=visibility, refresh=refresh
            )
            start = (page - 1) * page_size
            items = catalog[start : start + page_size]
            if routing:
                items = [_routing_record(item) for item in items]
            data = {
                "playbooks": items,
                "page": page,
                "page_size": page_size,
                "returned_count": len(items),
                "namespace": namespace,
                "total_count": len(catalog),
                "catalog_cache": cache,
            }
            data["total_pages"] = (len(catalog) + page_size - 1) // page_size
            output(data)
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "PLAYBOOK_LIST_ERROR",
                str(exc),
                suggestion="Check authentication with 'ep auth status'.",
                exit_code=EXIT_REMOTE,
            )

    @playbooks.command("search")
    @click.argument("query")
    @click.option(
        "--namespace",
        default="mine",
        show_default=True,
        help="Search scope: 'mine', 'ep', or an owner username.",
    )
    @click.option(
        "--refresh", is_flag=True, help="Refresh the local metadata catalog from Coop."
    )
    @click.option("--page", default=1, type=click.IntRange(min=1))
    @click.option("--page-size", default=20, type=click.IntRange(min=1, max=100))
    def search_playbooks(query, namespace, refresh, page, page_size):
        """Search playbook names, aliases, and descriptions."""
        try:
            from edsl.coop import Coop

            coop = Coop()
            catalog, cache = _namespace_catalog(
                coop, namespace=namespace, refresh=refresh
            )
            ranked = _rank_matches(catalog, query)
            start = (page - 1) * page_size
            items = [
                dict(item, match=reason)
                for item, reason in ranked[start : start + page_size]
            ]
            output(
                {
                    "playbooks": items,
                    "query": query,
                    "page": page,
                    "page_size": page_size,
                    "returned_count": len(items),
                    "namespace": namespace,
                    "total_count": len(ranked),
                    "total_pages": (len(ranked) + page_size - 1) // page_size,
                    "catalog_cache": cache,
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "PLAYBOOK_SEARCH_ERROR",
                str(exc),
                suggestion="Check authentication with 'ep auth status'.",
                exit_code=EXIT_REMOTE,
            )

    @playbooks.command("show")
    @click.argument("identifier")
    @click.option(
        "--output",
        "output_path",
        type=str,
        help="Write raw text, a .json resumable snapshot, or use '-' for raw stdout.",
    )
    def show_playbook(identifier, output_path):
        """Fetch and display a playbook by UUID, URL, or owner/alias."""
        try:
            from edsl.coop import Coop
            from edsl.prompts import Prompt

            coop = Coop()
            resolved = _identifier(identifier)
            prompt = coop.get(resolved, expected_object_type="prompt")
            if not isinstance(prompt, Prompt):
                error(
                    "NOT_A_PLAYBOOK",
                    f"Expected a Prompt, received {type(prompt).__name__}.",
                    exit_code=EXIT_USAGE,
                )
            metadata = jsonable(coop.get_metadata(resolved))
            if output_path:
                if output_path == "-":
                    click.echo(str(prompt), nl=False)
                    return
                path = Path(output_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix.lower() == ".json":
                    snapshot = _snapshot(prompt, metadata)
                    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
                else:
                    path.write_text(str(prompt), encoding="utf-8")
                output(
                    {
                        "metadata": metadata,
                        "saved_path": str(path),
                        "format": "snapshot"
                        if path.suffix.lower() == ".json"
                        else "text",
                    }
                )
                return
            output({"playbook": str(prompt), "metadata": metadata})
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "PLAYBOOK_SHOW_ERROR",
                str(exc),
                suggestion="Check the identifier and your access to this playbook.",
                exit_code=EXIT_REMOTE,
            )

    @playbooks.command("push")
    @click.argument("source", type=click.Path(exists=True, path_type=Path))
    @click.option("--alias", help="Short Expected Parrot alias.")
    @click.option("--description", help="Description used to find this playbook.")
    @click.option(
        "--visibility",
        type=click.Choice(["private", "public", "unlisted"]),
        default=None,
    )
    @click.option(
        "--force",
        is_flag=True,
        help="Overwrite an existing playbook with the same alias.",
    )
    def push_playbook(source, alias, description, visibility, force):
        """Create a playbook from Markdown, text, or Prompt JSON on Coop.

        PUSH creates a new playbook. It never updates an existing one unless
        --force is supplied; use 'ep playbooks update' to target one explicitly.
        """
        try:
            from edsl.coop import Coop
            from edsl.prompts import Prompt

            prompt, saved_metadata = _load_playbook(source, Prompt)
            alias = alias or saved_metadata.get("alias")
            description = description or saved_metadata.get("description")
            visibility = visibility or saved_metadata.get("visibility") or "private"
            info = Coop().push(
                prompt,
                alias=alias,
                description=description,
                visibility=visibility,
                force=force,
            )
            output(
                {
                    "object_type": "Prompt",
                    "source": str(source),
                    "playbook": jsonable(info),
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "PLAYBOOK_PUSH_ERROR",
                str(exc),
                suggestion="Check the playbook file, alias, and API key.",
                exit_code=EXIT_REMOTE,
            )

    @playbooks.command("update")
    @click.argument("identifier")
    @click.argument("source", type=click.Path(exists=True, path_type=Path))
    def update_playbook(identifier, source):
        """Replace the prompt text of an existing playbook explicitly."""
        try:
            from edsl.coop import Coop
            from edsl.prompts import Prompt

            prompt, _ = _load_playbook(source, Prompt)
            result = Coop().patch(_identifier(identifier), value=prompt)
            output(
                {
                    "operation": "update",
                    "identifier": identifier,
                    "result": jsonable(result),
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "PLAYBOOK_UPDATE_ERROR",
                str(exc),
                suggestion="Check the playbook identifier, source file, and API key.",
                exit_code=EXIT_REMOTE,
            )


def _identifier(value: str) -> str:
    """Turn owner/alias into the Coop content URL; preserve UUIDs and URLs."""
    if value.startswith(("http://", "https://")) or (
        len(value) == 36 and value.count("-") == 4
    ):
        return value
    if "/" in value:
        from edsl.config import CONFIG

        return f"{CONFIG.EXPECTED_PARROT_URL.rstrip('/')}/content/{value.strip('/')}"
    return value


def _routing_record(item: dict) -> dict:
    alias = str(item.get("alias") or "")
    owner = item.get("owner_username")
    name = f"{owner}/{alias}" if owner and alias and "/" not in alias else alias
    return {
        "name": name,
        "description": item.get("description"),
        "visibility": item.get("visibility"),
        "object_type": item.get("object_type", "prompt"),
        "uuid": item.get("uuid"),
        "fetch_command": f"ep playbooks show {name or item.get('uuid')} --output -",
    }


def _cache_path(coop, *, community: bool, visibility: str | None) -> Path | None:
    from edsl.config import CONFIG

    api_url = getattr(coop, "api_url", None) or CONFIG.EXPECTED_PARROT_URL
    if not api_url:
        return None
    key = hashlib.sha256(f"{api_url}|{community}|{visibility}".encode()).hexdigest()[
        :16
    ]
    root = Path(
        os.environ.get("EDSL_PLAYBOOK_CACHE_DIR")
        or user_cache_path("edsl") / "playbooks"
    )
    return root / f"catalog-{key}.json"


def _catalog(
    coop, *, community: bool, visibility: str | None = None, refresh: bool = False
) -> tuple[list[dict], dict]:
    path = _cache_path(coop, community=community, visibility=visibility)
    ttl_seconds = 300
    if path and not refresh:
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            age = max(0.0, time.time() - float(cached["fetched_at"]))
            if age <= ttl_seconds and isinstance(cached.get("playbooks"), list):
                return cached["playbooks"], {
                    "hit": True,
                    "age_seconds": round(age, 1),
                    "ttl_seconds": ttl_seconds,
                }
        except (OSError, ValueError, TypeError, KeyError):
            pass

    entries: list[dict] = []
    page = 1
    while True:
        result = coop.list(
            object_type="prompt",
            visibility=visibility,
            community=community,
            page=page,
            page_size=100,
        )
        current = [jsonable(item) for item in result]
        entries.extend(current)
        total_pages = getattr(result, "total_pages", None)
        if (total_pages is not None and page >= total_pages) or len(current) < 100:
            break
        page += 1
    cache_info = {"hit": False, "age_seconds": 0, "ttl_seconds": ttl_seconds}
    if path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps({"fetched_at": time.time(), "playbooks": entries}),
                encoding="utf-8",
            )
            temp_path.replace(path)
            cache_info["path"] = str(path)
        except OSError:
            pass
    return entries, cache_info


def _namespace_catalog(
    coop, *, namespace: str, visibility: str | None = None, refresh: bool = False
) -> tuple[list[dict], dict]:
    """Resolve the CLI namespace over Coop's current list scopes.

    ``ep`` maps to public playbooks outside the current user's collection;
    ``mine`` maps to owned/shared playbooks. A username searches both scopes
    and filters by owner, allowing users to address a publisher namespace.
    """
    normalized = namespace.casefold()
    if normalized in {"ep", "mine"}:
        return _catalog(
            coop,
            community=normalized == "ep",
            visibility=visibility,
            refresh=refresh,
        )

    catalogs = []
    cache_info = {}
    for scope, community in (("mine", False), ("ep", True)):
        entries, cache = _catalog(
            coop, community=community, visibility=visibility, refresh=refresh
        )
        cache_info[scope] = cache
        catalogs.extend(entries)
    by_uuid = {str(item.get("uuid")): item for item in catalogs}
    owner = normalized
    matches = [
        item
        for item in by_uuid.values()
        if str(item.get("owner_username") or "").casefold() == owner
    ]
    return matches, {"namespace": namespace, "catalogs": cache_info}


def _rank_matches(catalog: list[dict], query: str) -> list[tuple[dict, str]]:
    needle = " ".join(query.casefold().split())
    ranked = []
    for item in catalog:
        alias = str(item.get("alias") or "").casefold()
        description = str(item.get("description") or "").casefold()
        owner = str(item.get("owner_username") or "").casefold()
        full_name = f"{owner}/{alias}" if owner and alias else alias
        if alias == needle or full_name == needle:
            rank, reason = 0, "exact_alias"
        elif needle in alias or needle in owner or needle in full_name:
            rank, reason = 1, "name"
        elif needle in description:
            rank, reason = 2, "description"
        else:
            continue
        ranked.append((rank, item, reason))
    ranked.sort(
        key=lambda entry: (entry[0], str(entry[1].get("alias") or "").casefold())
    )
    return [(item, reason) for _, item, reason in ranked]


def _snapshot(prompt, metadata: dict) -> dict:
    return {
        "format": "edsl-playbook",
        "format_version": 1,
        "prompt": prompt.to_dict(),
        "metadata": metadata,
    }


def _load_playbook(source: Path, Prompt) -> tuple[object, dict]:
    metadata: dict = {}
    suffix = source.suffix.lower()
    if suffix in {".md", ".txt"}:
        return Prompt(source.read_text(encoding="utf-8")), metadata
    if suffix != ".json":
        error(
            "USAGE_ERROR",
            f"Unsupported playbook file: {source}",
            suggestion="Use Markdown, text, or Prompt JSON.",
            exit_code=EXIT_USAGE,
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("format") == "edsl-playbook":
        if payload.get("format_version") != 1:
            error(
                "UNSUPPORTED_PLAYBOOK_SNAPSHOT",
                f"Unsupported snapshot version: {payload.get('format_version')}",
                exit_code=EXIT_USAGE,
            )
        metadata = payload.get("metadata") or {}
        payload = payload.get("prompt")
    return Prompt.from_dict(payload), metadata
