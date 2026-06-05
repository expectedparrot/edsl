"""Git-backed package persistence for ModelList objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import LanguageModelExceptions

if TYPE_CHECKING:
    from .model_list import ModelList


FORMAT_NAME = "edsl.model_list.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".model_list.ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()


class ModelListGitError(LanguageModelExceptions):
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


class ModelListGitNestedRepoWarning(UserWarning):
    """Warning emitted when a ModelList Git package is nested in another Git repo."""


class ModelListGitDescriptor(GitBackedDescriptor):
    def __init__(self) -> None:
        super().__init__(_git_spec)


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="ModelList",
        package_suffix=PACKAGE_SUFFIX,
        default_name="model_list",
        error_cls=ModelListGitError,
        warning_cls=ModelListGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=ModelListGitPackage,
        read=_read_model_list,
        write=_write_model_list,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_model_list_git_accessor",
        default_commit_message="Save ModelList",
    )


def _read_model_list(path: Path, ref: str) -> "ModelList":
    model_list_dict = _read_model_list_dict_at_ref(path, ref)
    from .model_list import ModelList

    return ModelList.from_dict(model_list_dict)


def _write_model_list(path: Path, model_list: "ModelList", **_kwargs) -> dict:
    (path / "models").mkdir(exist_ok=True)
    model_list_dict = model_list.to_dict(add_edsl_version=False)
    existing_order, existing_models = _load_existing_package_state(path)
    model_ids = _model_ids_for_models(
        model_list_dict["models"], existing_order, existing_models
    )
    _write_package(path, model_list_dict, model_ids)
    return {}


class ModelListGitPackage(gitpkg.GitPackage):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="ModelList",
            display_name=_package_display_name(Path(path)),
            error_cls=ModelListGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}


def _normalize_package_path(path, for_load: bool = False) -> Path:
    return gitpkg.normalize_package_path(path, package_suffix=PACKAGE_SUFFIX, for_load=for_load)


def _default_unsaved_package_path() -> Path:
    return _normalize_package_path("model_list")


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _init_package(path: Path) -> None:
    gitpkg.init_package(path, error_cls=ModelListGitError)
    (path / "models").mkdir(exist_ok=True)


def _read_model_list_dict_at_ref(path: Path, ref: str) -> dict:
    manifest = _load_manifest_at_ref(path, ref)
    return {
        "models": [
            gitpkg.read_json_at_ref(
                path,
                f"models/{model_id}.json",
                ref,
                error_cls=ModelListGitError,
            )
            for model_id in manifest.get("model_order", [])
        ]
    }


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(path, "manifest.json", ref, error_cls=ModelListGitError)
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported ModelList git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported ModelList git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _load_existing_order(path: Path) -> list[str]:
    manifest = gitpkg.read_manifest_file(path)
    return list(manifest.get("model_order", []))


def _load_existing_package_state(path: Path) -> tuple[list[str], dict[str, dict]]:
    existing_order = _load_existing_order(path)
    existing_models = {}
    for model_id in existing_order:
        model_path = path / "models" / f"{model_id}.json"
        if not model_path.exists():
            continue
        try:
            existing_models[model_id] = json.loads(model_path.read_text())
        except json.JSONDecodeError:
            continue
    return existing_order, existing_models


def _model_ids_for_models(model_dicts: list[dict], existing_order: list[str], existing_models: dict[str, dict]) -> list[str]:
    used: set[str] = set()
    assigned: list[str] = []
    next_index = _next_model_index(existing_order)
    for model_dict in model_dicts:
        matched_id = None
        for model_id in existing_order:
            if model_id in used:
                continue
            if existing_models.get(model_id) == model_dict:
                matched_id = model_id
                break
        if matched_id is None:
            while True:
                candidate = f"{next_index:06d}"
                next_index += 1
                if candidate not in used and candidate not in existing_models:
                    matched_id = candidate
                    break
        used.add(matched_id)
        assigned.append(matched_id)
    return assigned


def _next_model_index(existing_order: list[str]) -> int:
    numeric_ids = [int(model_id) for model_id in existing_order if model_id.isdigit()]
    return max(numeric_ids, default=0) + 1


def _write_package(path: Path, model_list_dict: dict, model_ids: list[str]) -> None:
    _write_manifest(path, model_list_dict, model_ids)
    _write_models(path, model_list_dict["models"], model_ids)


def _write_manifest(path: Path, model_list_dict: dict, model_ids: list[str]) -> None:
    existing_manifest = gitpkg.read_manifest_file(path)
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "ModelList",
        "object_type": "ModelList",
        "model_order": model_ids,
        "n_models": len(model_ids),
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


def _write_models(path: Path, model_dicts: list[dict], model_ids: list[str]) -> None:
    models_dir = path / "models"
    models_dir.mkdir(exist_ok=True)
    live_files = {f"{model_id}.json" for model_id in model_ids}
    for model_id, model_dict in zip(model_ids, model_dicts):
        (models_dir / f"{model_id}.json").write_text(
            json.dumps(model_dict, indent=2, sort_keys=True) + "\n"
        )
    for existing in models_dir.glob("*.json"):
        if existing.name not in live_files:
            existing.unlink()


def _refresh_instance_from_loaded(instance: "ModelList", loaded: "ModelList") -> None:
    accessor = instance.__dict__.get("_model_list_git_accessor")
    instance.__dict__.update(loaded.__dict__)
    if accessor is not None:
        instance.__dict__["_model_list_git_accessor"] = accessor


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    models_dir = path / "models"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    if not models_dir.is_dir():
        errors.append("missing models directory")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid manifest.json: {exc.msg}"]
    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "ModelList":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")
    model_order = manifest.get("model_order")
    if not isinstance(model_order, list):
        errors.append("manifest model_order must be a list")
        model_order = []
    seen: set[str] = set()
    for model_id in model_order:
        if not isinstance(model_id, str):
            errors.append(f"invalid model id in manifest: {model_id!r}")
            continue
        if model_id in seen:
            errors.append(f"duplicate model id: {model_id}")
        seen.add(model_id)
        model_path = models_dir / f"{model_id}.json"
        if not model_path.exists():
            errors.append(f"missing model file: models/{model_id}.json")
            continue
        try:
            json.loads(model_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid model file models/{model_id}.json: {exc.msg}")
    if models_dir.is_dir():
        expected_files = {f"{model_id}.json" for model_id in seen}
        for model_file in sorted(models_dir.glob("*.json")):
            if model_file.name not in expected_files:
                errors.append(f"extra model file: models/{model_file.name}")
    n_models = manifest.get("n_models")
    if n_models is not None and n_models != len(model_order):
        errors.append("manifest n_models does not match model_order")
    return errors


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)
