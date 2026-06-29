"""Git-backed immutable archive persistence for Results objects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import ResultsError

if TYPE_CHECKING:
    from .results import Results


FORMAT_NAME = "edsl.results.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".results.ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()


class ResultsGitError(ResultsError):
    """Raised when an underlying git command fails."""

    def __init__(
        self,
        command: list[str],
        stderr: str = "",
        stdout: str = "",
        message: Optional[str] = None,
    ) -> None:
        self.command = command
        self.stderr = stderr
        self.stdout = stdout
        details = (stderr or stdout or "").strip()
        message = message or f"Git command failed: {_display_git_command(command)}"
        if details:
            message = f"{message}\n{details}"
        super().__init__(message)


class ResultsGitNestedRepoWarning(UserWarning):
    """Warning emitted when a Results Git package is nested in another Git repo."""


class ResultsGitDescriptor(GitBackedDescriptor):
    def __init__(self) -> None:
        super().__init__(_git_spec)


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="Results",
        package_suffix=PACKAGE_SUFFIX,
        default_name="results",
        error_cls=ResultsGitError,
        warning_cls=ResultsGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=ResultsGitPackage,
        read=_read_results,
        write=_write_results,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_results_git_accessor",
        default_commit_message="Save Results",
    )


def _read_results(path: Path, ref: str) -> "Results":
    manifest = _load_manifest_at_ref(path, ref)
    jsonl = gitpkg.git(
        path, "show", f"{ref}:results.jsonl", capture=True, error_cls=ResultsGitError
    )
    content_sha256 = _content_sha256(jsonl)
    if content_sha256 != manifest.get("content_sha256"):
        raise ValueError("Results package content digest does not match manifest")
    from .results import Results

    results = Results.from_jsonl(jsonl)
    _restore_source_metadata(results, manifest.get("source", {}))
    results.git.content_sha256 = content_sha256
    return results


def _write_results(
    path: Path, results: "Results", *, allow_new_commit: bool = False, **_kwargs
) -> dict:
    jsonl = results.to_jsonl()
    content_sha256 = _content_sha256(jsonl)
    existing_manifest = gitpkg.read_manifest_file(path)
    existing_sha256 = existing_manifest.get("content_sha256")
    if existing_sha256 and existing_sha256 != content_sha256 and not allow_new_commit:
        raise ResultsGitError(
            ["git", "-C", str(path), "commit"],
            message=(
                "Results git packages are immutable by default. Existing "
                f"content_sha256={existing_sha256}, new content_sha256={content_sha256}. "
                "Use allow_new_commit=True to archive a different Results payload "
                "in this package."
            ),
        )

    _write_package(path, results, jsonl, content_sha256)
    return {"content_sha256": content_sha256}


class ResultsGitPackage(gitpkg.GitPackage):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="Results",
            display_name=_package_display_name(Path(path)),
            error_cls=ResultsGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}


def _normalize_package_path(path, for_load: bool = False) -> Path:
    return gitpkg.normalize_package_path(path, package_suffix=PACKAGE_SUFFIX, for_load=for_load)


def _default_unsaved_package_path() -> Path:
    return _normalize_package_path("results")


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _init_package(path: Path) -> None:
    gitpkg.init_package(path, error_cls=ResultsGitError)


def _write_package(path: Path, results: "Results", jsonl: str, content_sha256: str) -> None:
    (path / "results.jsonl").write_text(jsonl)
    gitpkg.write_manifest_dict(path, _manifest(results, content_sha256))


def _manifest(results: "Results", content_sha256: str) -> dict:
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "Results",
        "object_type": "Results",
        "content_sha256": content_sha256,
        "n_results": len(results),
        "source": _source_metadata(results),
    }
    if getattr(results, "name", None) is not None:
        manifest["name"] = results.name
    try:
        from edsl import __version__
        manifest["edsl_version"] = __version__
    except Exception:
        pass
    return manifest


def _source_metadata(results: "Results") -> dict:
    source = {}
    job_uuid = getattr(results, "_job_uuid", None) or getattr(results, "job_uuid", None)
    results_uuid = getattr(results, "results_uuid", None)
    if job_uuid is not None:
        source["job_uuid"] = job_uuid
    if results_uuid is not None:
        source["results_uuid"] = results_uuid
    return source


def _restore_source_metadata(results: "Results", source: dict) -> None:
    if source.get("job_uuid") is not None:
        results._job_uuid = source["job_uuid"]
    if source.get("results_uuid") is not None:
        results.results_uuid = source["results_uuid"]


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(path, "manifest.json", ref, error_cls=ResultsGitError)
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported Results git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported Results git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _content_sha256(jsonl: str) -> str:
    return hashlib.sha256(jsonl.encode("utf-8")).hexdigest()


def _refresh_instance_from_loaded(instance: "Results", loaded: "Results") -> None:
    accessor = instance.__dict__.get("_results_git_accessor")
    instance.__dict__.update(loaded.__dict__)
    if accessor is not None:
        instance.__dict__["_results_git_accessor"] = accessor


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    results_path = path / "results.jsonl"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    if not results_path.exists():
        errors.append("missing results.jsonl")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid manifest.json: {exc.msg}"]
    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "Results":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")
    content_sha256 = manifest.get("content_sha256")
    if not isinstance(content_sha256, str):
        errors.append("missing manifest content_sha256")
    elif results_path.exists():
        actual_sha256 = _content_sha256(results_path.read_text())
        if actual_sha256 != content_sha256:
            errors.append(
                f"results.jsonl content_sha256 mismatch: expected {content_sha256}, found {actual_sha256}"
            )
    if results_path.exists():
        try:
            from .results import Results

            loaded = Results.from_jsonl(results_path)
            n_results = manifest.get("n_results")
            if n_results is not None and n_results != len(loaded):
                errors.append("manifest n_results does not match results.jsonl")
        except Exception as exc:
            errors.append(f"invalid results.jsonl: {exc}")
    return errors


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)
