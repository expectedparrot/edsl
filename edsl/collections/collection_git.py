"""Git-backed package persistence for metadata-only Collection objects."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import TYPE_CHECKING

from edsl.base import BaseException as EDSLBaseException
from edsl.base import git_package as gitpkg
from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec

if TYPE_CHECKING:
    from .collection import Collection

FORMAT_NAME = "edsl.collection.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()


class CollectionGitError(EDSLBaseException):
    """Raised when an underlying git command fails."""

    def __init__(self, command: list[str], stderr: str = "", stdout: str = "") -> None:
        details = (stderr or stdout or "").strip()
        message = f"Git command failed: {_display_git_command(command)}"
        if details:
            message = f"{message}\n{details}"
        super().__init__(message, show_docs=False)


class CollectionGitNestedRepoWarning(UserWarning):
    """Warning emitted when a Collection package is nested in another Git repo."""


class CollectionGitDescriptor(GitBackedDescriptor):
    def __init__(self) -> None:
        super().__init__(_git_spec)


class CollectionGitPackage(gitpkg.GitPackage):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="Collection",
            display_name=Path(path).stem,
            error_cls=CollectionGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}

    def html(self, filename: str | Path | None = None, *, ref: str = "HEAD") -> str:
        data = _read_collection_dict_at_ref(self.path, ref)
        rows = []
        for index, item in enumerate(data.get("items", []), start=1):
            cells = (
                index,
                item.get("object_type", ""),
                item.get("object_uuid", ""),
                item.get("added_at", ""),
                item.get("version_at_add", "") or "",
            )
            rows.append(
                "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>"
            )
        title = html.escape(data.get("name", "EDSL Collection"))
        purpose = html.escape(data.get("purpose", ""))
        tags = ", ".join(html.escape(tag) for tag in data.get("tags", []))
        document = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title></head><body><h1>{title}</h1>"
            f"<p>{purpose}</p><p>{tags}</p><table><thead><tr>"
            "<th>#</th><th>Type</th><th>UUID</th><th>Added</th><th>Version at add</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></body></html>"
        )
        if filename is not None:
            Path(filename).write_text(document, encoding="utf-8")
        return document


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="Collection",
        package_suffix=PACKAGE_SUFFIX,
        default_name="collection",
        error_cls=CollectionGitError,
        warning_cls=CollectionGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=CollectionGitPackage,
        read=_read_collection,
        write=_write_collection,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_collection_git_accessor",
        default_commit_message="Save Collection",
    )


def _read_collection(path: Path, ref: str) -> "Collection":
    data = _read_collection_dict_at_ref(path, ref)
    from .collection import Collection

    return Collection.from_dict(data)


def _read_collection_dict_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(
        path, "manifest.json", ref, error_cls=CollectionGitError
    )
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported Collection git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported Collection git package version: "
            f"{manifest.get('format_version')!r}"
        )
    if manifest.get("edsl_class_name") != "Collection":
        raise ValueError("Collection package manifest has an invalid edsl_class_name")
    return gitpkg.read_json_at_ref(
        path, "collection.json", ref, error_cls=CollectionGitError
    )


def _write_collection(path: Path, collection: "Collection", **_kwargs) -> dict:
    data = collection.to_dict(add_edsl_version=False)
    (path / "collection.json").write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    existing = gitpkg.read_manifest_file(path)
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "Collection",
        "object_type": "Collection",
        "name": collection.name,
        "n_items": len(collection),
    }
    remotes = gitpkg.manifest_remotes(existing)
    if remotes:
        manifest["remotes"] = remotes
    if "primary_remote" in existing:
        manifest["primary_remote"] = existing["primary_remote"]
    elif isinstance(existing.get("remote"), dict) and existing["remote"].get("name"):
        manifest["primary_remote"] = existing["remote"]["name"]
    from edsl import __version__

    manifest["edsl_version"] = __version__
    gitpkg.write_manifest_dict(path, manifest)
    return {}


def _refresh_instance_from_loaded(
    instance: "Collection", loaded: "Collection"
) -> None:
    accessor = instance.__dict__.get("_collection_git_accessor")
    instance.__dict__.update(loaded.__dict__)
    if accessor is not None:
        instance.__dict__["_collection_git_accessor"] = accessor


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    data_path = path / "collection.json"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    if not data_path.is_file():
        errors.append("missing collection.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"invalid manifest.json: {exc}"]
    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "Collection":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")
    if data_path.is_file():
        try:
            from .collection import Collection

            data = json.loads(data_path.read_text(encoding="utf-8"))
            Collection.from_dict(data)
        except (json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
            errors.append(f"invalid collection.json: {exc}")
    return errors


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)
