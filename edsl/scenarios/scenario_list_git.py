"""Git-backed package persistence for ScenarioList objects."""

from __future__ import annotations

import json
import base64
import binascii
import hashlib
import subprocess
from pathlib import Path
from typing import Any, TYPE_CHECKING

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import ScenarioError

if TYPE_CHECKING:
    from .scenario_list import ScenarioList


FORMAT_NAME = "edsl.scenario_list.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".scenario_list.ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()


class ScenarioListGitError(ScenarioError):
    """Raised when an underlying git command fails."""

    def __init__(self, command: list[str], stderr: str = "", stdout: str = "") -> None:
        self.command = command
        self.stderr = stderr
        self.stdout = stdout
        details = (stderr or stdout or "").strip()
        message = f"Git command failed: {_display_git_command(command)}"
        if details:
            message = f"{message}\n{details}"
        super().__init__(message)


class ScenarioListGitNestedRepoWarning(UserWarning):
    """Warning emitted when a ScenarioList Git package is nested in another Git repo."""


class ScenarioListGitDescriptor(GitBackedDescriptor):
    def __init__(self) -> None:
        super().__init__(_git_spec)


class ScenarioListGitPackage(gitpkg.GitPackage):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="ScenarioList",
            display_name=_package_display_name(Path(path)),
            error_cls=ScenarioListGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="ScenarioList",
        package_suffix=PACKAGE_SUFFIX,
        default_name="scenario_list",
        error_cls=ScenarioListGitError,
        warning_cls=ScenarioListGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=ScenarioListGitPackage,
        read=_read_scenario_list,
        write=_write_scenario_list,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_scenario_list_git_accessor",
        default_commit_message="Save ScenarioList",
    )


def _read_scenario_list(path: Path, ref: str) -> "ScenarioList":
    scenario_list_dict = _read_scenario_list_dict_at_ref(path, ref)
    from .scenario_list import ScenarioList

    return ScenarioList.from_dict(scenario_list_dict)


def _write_scenario_list(path: Path, scenario_list: "ScenarioList", **_kwargs) -> dict:
    (path / "scenarios").mkdir(exist_ok=True)

    scenario_list_dict = scenario_list.to_dict(add_edsl_version=False)
    existing_order, existing_scenarios = _load_existing_package_state(path)
    scenario_ids = _scenario_ids_for_scenarios(
        scenario_list_dict["scenarios"], existing_order, existing_scenarios
    )
    _write_package(path, scenario_list_dict, scenario_ids)
    return {}


def _normalize_package_path(path, for_load: bool = False) -> Path:
    return gitpkg.normalize_package_path(path, package_suffix=PACKAGE_SUFFIX, for_load=for_load)


def _default_unsaved_package_path() -> Path:
    return _normalize_package_path("scenario_list")


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _init_package(path: Path) -> None:
    gitpkg.init_package(path, error_cls=ScenarioListGitError)
    (path / "scenarios").mkdir(exist_ok=True)


def _read_scenario_list_dict_at_ref(path: Path, ref: str) -> dict:
    manifest = _load_manifest_at_ref(path, ref)
    scenario_list_dict = {
        "scenarios": [
            _hydrate_filestore_refs(
                path,
                gitpkg.read_json_at_ref(
                    path,
                    f"scenarios/{scenario_id}.json",
                    ref,
                    error_cls=ScenarioListGitError,
                ),
                ref,
            )
            for scenario_id in manifest.get("scenario_order", [])
        ]
    }
    codebook = _read_optional_json_at_ref(path, "codebook.json", ref, default=None)
    if codebook:
        scenario_list_dict["codebook"] = codebook
    return scenario_list_dict


def _read_optional_json_at_ref(path: Path, file_path: str, ref: str, default):
    try:
        return gitpkg.read_json_at_ref(path, file_path, ref, error_cls=ScenarioListGitError)
    except ScenarioListGitError:
        return default


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(path, "manifest.json", ref, error_cls=ScenarioListGitError)
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported ScenarioList git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported ScenarioList git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _load_existing_order(path: Path) -> list[str]:
    manifest = gitpkg.read_manifest_file(path)
    return list(manifest.get("scenario_order", []))


def _load_existing_package_state(path: Path) -> tuple[list[str], dict[str, dict]]:
    existing_order = _load_existing_order(path)
    existing_scenarios = {}
    for scenario_id in existing_order:
        scenario_path = path / "scenarios" / f"{scenario_id}.json"
        if not scenario_path.exists():
            continue
        try:
            existing_scenarios[scenario_id] = json.loads(scenario_path.read_text())
        except json.JSONDecodeError:
            continue
    return existing_order, existing_scenarios


def _scenario_ids_for_scenarios(scenario_dicts: list[dict], existing_order: list[str], existing_scenarios: dict[str, dict]) -> list[str]:
    used: set[str] = set()
    assigned: list[str] = []
    next_index = _next_scenario_index(existing_order)
    for scenario_dict in scenario_dicts:
        matched_id = None
        for scenario_id in existing_order:
            if scenario_id in used:
                continue
            if existing_scenarios.get(scenario_id) == scenario_dict:
                matched_id = scenario_id
                break
        if matched_id is None:
            while True:
                candidate = f"{next_index:06d}"
                next_index += 1
                if candidate not in used and candidate not in existing_scenarios:
                    matched_id = candidate
                    break
        used.add(matched_id)
        assigned.append(matched_id)
    return assigned


def _next_scenario_index(existing_order: list[str]) -> int:
    numeric_ids = [int(scenario_id) for scenario_id in existing_order if scenario_id.isdigit()]
    return max(numeric_ids, default=0) + 1


def _write_package(path: Path, scenario_list_dict: dict, scenario_ids: list[str]) -> None:
    _write_manifest(path, scenario_list_dict, scenario_ids)
    _write_scenarios(path, scenario_list_dict["scenarios"], scenario_ids)
    _write_codebook(path, scenario_list_dict.get("codebook"))


def _write_manifest(path: Path, scenario_list_dict: dict, scenario_ids: list[str]) -> None:
    existing_manifest = gitpkg.read_manifest_file(path)
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "ScenarioList",
        "object_type": "ScenarioList",
        "scenario_order": scenario_ids,
        "n_scenarios": len(scenario_ids),
    }
    existing_remotes = gitpkg.manifest_remotes(existing_manifest)
    if existing_remotes:
        manifest["remotes"] = existing_remotes
    if "primary_remote" in existing_manifest:
        manifest["primary_remote"] = existing_manifest["primary_remote"]
    elif "remote" in existing_manifest and existing_manifest["remote"].get("name"):
        manifest["primary_remote"] = existing_manifest["remote"]["name"]
    try:
        from edsl import __version__
        manifest["edsl_version"] = __version__
    except Exception:
        pass
    gitpkg.write_manifest_dict(path, manifest)


def _write_scenarios(path: Path, scenario_dicts: list[dict], scenario_ids: list[str]) -> None:
    scenarios_dir = path / "scenarios"
    scenarios_dir.mkdir(exist_ok=True)
    live_files = {f"{scenario_id}.json" for scenario_id in scenario_ids}
    filestore_refs: list[dict] = []
    for scenario_id, scenario_dict in zip(scenario_ids, scenario_dicts):
        scenario_dict = _extract_filestore_blobs(path, scenario_dict)
        filestore_refs.extend(_collect_filestore_refs(scenario_dict))
        (scenarios_dir / f"{scenario_id}.json").write_text(
            json.dumps(scenario_dict, indent=2, sort_keys=True) + "\n"
        )
    for existing in scenarios_dir.glob("*.json"):
        if existing.name not in live_files:
            existing.unlink()
    _write_filestore_manifest(path, filestore_refs)
    _prune_unreferenced_filestore_blobs(path, {ref["sha256"] for ref in filestore_refs})


def _write_codebook(path: Path, codebook: Optional[dict]) -> None:
    codebook_path = path / "codebook.json"
    if not codebook:
        if codebook_path.exists():
            codebook_path.unlink()
        return
    codebook_path.write_text(json.dumps(codebook, indent=2, sort_keys=True) + "\n")


def _write_filestore_manifest(path: Path, filestore_refs: list[dict]) -> None:
    manifest_path = path / "filestore_manifest.json"
    if not filestore_refs:
        if manifest_path.exists():
            manifest_path.unlink()
        return
    files_by_sha = {}
    for ref in filestore_refs:
        files_by_sha[ref["sha256"]] = {
            key: ref.get(key)
            for key in ("sha256", "path", "suffix", "mime_type", "binary", "size")
        }
    manifest = {
        "format": "edsl.scenario_list.filestore_manifest",
        "format_version": 1,
        "files": [files_by_sha[sha] for sha in sorted(files_by_sha)],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def _prune_unreferenced_filestore_blobs(path: Path, live_hashes: set[str]) -> None:
    files_dir = path / "files" / "sha256"
    if not files_dir.exists():
        return
    for blob_path in files_dir.glob("*/*"):
        sha256 = blob_path.parent.name + blob_path.name
        if sha256 not in live_hashes:
            blob_path.unlink()
    for directory in sorted(files_dir.glob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    root_files_dir = path / "files"
    if files_dir.exists() and not any(files_dir.iterdir()):
        files_dir.rmdir()
    if root_files_dir.exists() and not any(root_files_dir.iterdir()):
        root_files_dir.rmdir()


def _extract_filestore_blobs(path: Path, value: Any) -> Any:
    if _is_filestore_instance(value):
        return _write_filestore_ref(path, value.to_dict(add_edsl_version=False))
    if isinstance(value, list):
        return [_extract_filestore_blobs(path, item) for item in value]
    if not isinstance(value, dict):
        return value
    if _is_serialized_filestore(value):
        return _write_filestore_ref(path, value)
    return {key: _extract_filestore_blobs(path, item) for key, item in value.items()}


def _is_filestore_instance(value: Any) -> bool:
    try:
        from .file_store import FileStore

        return isinstance(value, FileStore)
    except Exception:
        return False


def _hydrate_filestore_refs(path: Path, value: Any, ref: str) -> Any:
    if isinstance(value, list):
        return [_hydrate_filestore_refs(path, item, ref) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("edsl_type") == "FileStoreRef":
        return _read_filestore_ref(path, value, ref)
    return {key: _hydrate_filestore_refs(path, item, ref) for key, item in value.items()}


def _collect_filestore_refs(value: Any) -> list[dict]:
    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(_collect_filestore_refs(item))
        return refs
    if not isinstance(value, dict):
        return []
    if value.get("edsl_type") == "FileStoreRef":
        return [value]
    refs = []
    for item in value.values():
        refs.extend(_collect_filestore_refs(item))
    return refs


def _is_serialized_filestore(value: dict) -> bool:
    return "base64_string" in value and "path" in value


def _write_filestore_ref(path: Path, filestore_dict: dict) -> dict:
    base64_string = filestore_dict.get("base64_string")
    if not isinstance(base64_string, str) or base64_string == "offloaded":
        return filestore_dict
    try:
        content = base64.b64decode(base64_string.encode("utf-8"), validate=True)
    except (binascii.Error, ValueError):
        return filestore_dict
    sha256 = hashlib.sha256(content).hexdigest()
    blob_path = _filestore_blob_path(path, sha256)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.write_bytes(content)
    metadata = {key: item for key, item in filestore_dict.items() if key != "base64_string"}
    return {
        "edsl_type": "FileStoreRef",
        "sha256": sha256,
        "path": filestore_dict.get("path"),
        "suffix": filestore_dict.get("suffix"),
        "mime_type": filestore_dict.get("mime_type"),
        "binary": filestore_dict.get("binary"),
        "size": len(content),
        "metadata": metadata,
    }


def _read_filestore_ref(path: Path, filestore_ref: dict, ref: str) -> dict:
    sha256 = filestore_ref.get("sha256")
    if not isinstance(sha256, str):
        raise ValueError(f"Invalid FileStoreRef without sha256: {filestore_ref!r}")
    blob_relpath = _filestore_blob_relpath(sha256)
    command = ["git", "-C", str(path), "show", f"{ref}:{blob_relpath}"]
    try:
        completed = subprocess.run(command, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"Missing FileStore blob for sha256 {sha256}") from None
    content = completed.stdout
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if actual_sha256 != sha256:
        raise ValueError(
            f"FileStore blob hash mismatch for {sha256}: found {actual_sha256}"
        )
    metadata = dict(filestore_ref.get("metadata") or {})
    metadata["base64_string"] = base64.b64encode(content).decode("utf-8")
    metadata.setdefault("path", filestore_ref.get("path"))
    metadata.setdefault("suffix", filestore_ref.get("suffix"))
    metadata.setdefault("mime_type", filestore_ref.get("mime_type"))
    metadata.setdefault("binary", filestore_ref.get("binary"))
    return metadata


def _filestore_blob_path(path: Path, sha256: str) -> Path:
    return path / _filestore_blob_relpath(sha256)


def _filestore_blob_relpath(sha256: str) -> str:
    return f"files/sha256/{sha256[:2]}/{sha256[2:]}"


def _refresh_instance_from_loaded(instance: "ScenarioList", loaded: "ScenarioList") -> None:
    accessor = instance.__dict__.get("_scenario_list_git_accessor")
    instance.__dict__.update(loaded.__dict__)
    if accessor is not None:
        instance.__dict__["_scenario_list_git_accessor"] = accessor


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    scenarios_dir = path / "scenarios"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    if not scenarios_dir.is_dir():
        errors.append("missing scenarios directory")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid manifest.json: {exc.msg}"]
    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "ScenarioList":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")
    scenario_order = manifest.get("scenario_order")
    if not isinstance(scenario_order, list):
        errors.append("manifest scenario_order must be a list")
        scenario_order = []
    seen: set[str] = set()
    for scenario_id in scenario_order:
        if not isinstance(scenario_id, str):
            errors.append(f"invalid scenario id in manifest: {scenario_id!r}")
            continue
        if scenario_id in seen:
            errors.append(f"duplicate scenario id: {scenario_id}")
        seen.add(scenario_id)
        scenario_path = scenarios_dir / f"{scenario_id}.json"
        if not scenario_path.exists():
            errors.append(f"missing scenario file: scenarios/{scenario_id}.json")
            continue
        try:
            scenario_dict = json.loads(scenario_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid scenario file scenarios/{scenario_id}.json: {exc.msg}")
            continue
        for filestore_ref in _collect_filestore_refs(scenario_dict):
            errors.extend(_validate_filestore_ref(path, filestore_ref))
    if scenarios_dir.is_dir():
        expected_files = {f"{scenario_id}.json" for scenario_id in seen}
        for scenario_file in sorted(scenarios_dir.glob("*.json")):
            if scenario_file.name not in expected_files:
                errors.append(f"extra scenario file: scenarios/{scenario_file.name}")
    if (path / "codebook.json").exists():
        try:
            json.loads((path / "codebook.json").read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid codebook.json: {exc.msg}")
    if (path / "filestore_manifest.json").exists():
        errors.extend(_validate_filestore_manifest(path))
    n_scenarios = manifest.get("n_scenarios")
    if n_scenarios is not None and n_scenarios != len(scenario_order):
        errors.append("manifest n_scenarios does not match scenario_order")
    return errors


def _validate_filestore_ref(path: Path, filestore_ref: dict) -> list[str]:
    errors: list[str] = []
    sha256 = filestore_ref.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64:
        return [f"invalid FileStoreRef sha256: {sha256!r}"]
    blob_path = _filestore_blob_path(path, sha256)
    if not blob_path.exists():
        return [f"missing FileStore blob: {_filestore_blob_relpath(sha256)}"]
    actual_sha256 = hashlib.sha256(blob_path.read_bytes()).hexdigest()
    if actual_sha256 != sha256:
        errors.append(
            f"FileStore blob hash mismatch for {sha256}: found {actual_sha256}"
        )
    size = filestore_ref.get("size")
    if isinstance(size, int) and size != blob_path.stat().st_size:
        errors.append(f"FileStore blob size mismatch for {sha256}")
    return errors


def _validate_filestore_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "filestore_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid filestore_manifest.json: {exc.msg}"]
    if manifest.get("format") != "edsl.scenario_list.filestore_manifest":
        errors.append("invalid filestore_manifest format")
    if manifest.get("format_version") != 1:
        errors.append("invalid filestore_manifest format_version")
    files = manifest.get("files")
    if not isinstance(files, list):
        return [*errors, "filestore_manifest files must be a list"]
    for file_ref in files:
        if not isinstance(file_ref, dict):
            errors.append(f"invalid filestore_manifest file entry: {file_ref!r}")
            continue
        errors.extend(_validate_filestore_ref(path, file_ref))
    return errors


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)
