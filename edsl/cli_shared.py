"""Shared helpers for the EDSL CLI."""

from __future__ import annotations

import gzip
import json
import sys
import zipfile
from pathlib import Path
from typing import Optional


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_AUTH = 4
EXIT_VALIDATION = 5
EXIT_REMOTE = 6


def output(data: dict, warnings: Optional[list] = None) -> None:
    """Write a success envelope to stdout."""
    envelope = {"status": "ok", "data": data, "warnings": warnings or []}
    json.dump(envelope, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def error(
    code: str,
    message: str,
    suggestion: str = "",
    exit_code: int = EXIT_ERROR,
    details: Optional[list] = None,
) -> None:
    """Write an error envelope to stdout and exit."""
    err = {"code": code, "message": message}
    if suggestion:
        err["suggestion"] = suggestion
    if details:
        err["details"] = details
    envelope = {"status": "error", "error": err}
    json.dump(envelope, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    raise SystemExit(exit_code)


def read_json_file(path: str) -> dict:
    """Read and parse a JSON file, or emit an error."""
    p = Path(path)
    if not p.exists():
        error(
            "FILE_NOT_FOUND",
            f"File not found: {path}",
            suggestion="Check the file path.",
            exit_code=EXIT_NOT_FOUND,
        )
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        error(
            "INVALID_JSON",
            f"Failed to parse JSON from {path}: {e}",
            suggestion="Ensure the file contains valid JSON.",
            exit_code=EXIT_USAGE,
        )


def read_package_manifest(path: Path) -> dict:
    if path.is_dir():
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            error(
                "INVALID_PACKAGE",
                f"No manifest.json found in package: {path}",
                exit_code=EXIT_USAGE,
            )
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    with zipfile.ZipFile(path) as archive:
        with archive.open("manifest.json") as manifest_file:
            return json.loads(manifest_file.read().decode("utf-8"))


def read_serialized_object(path: Path) -> dict:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    return read_json_file(str(path))


def load_git_object(path: Path):
    manifest = read_package_manifest(path)
    class_name = manifest.get("edsl_class_name") or manifest.get("object_type")
    if class_name == "Survey":
        from edsl.surveys import Survey

        return Survey.git.load(path)
    if class_name == "AgentList":
        from edsl.agents import AgentList

        return AgentList.git.load(path)
    if class_name == "Jobs":
        from edsl.jobs import Jobs

        return Jobs.git.load(path)
    if class_name == "Results":
        from edsl.results import Results

        return Results.git.load(path)
    if class_name == "ScenarioList":
        from edsl.scenarios import ScenarioList

        return ScenarioList.git.load(path)
    if class_name == "ModelList":
        from edsl.language_models import ModelList

        return ModelList.git.load(path)
    error(
        "UNSUPPORTED_OBJECT",
        f"Object package type does not support push: {class_name or 'unknown'}",
        suggestion="Currently supported package types: Survey, AgentList, Jobs, Results, ScenarioList, ModelList.",
        exit_code=EXIT_USAGE,
    )


def load_any_object(target: str, expected_object_type: str | None = None):
    path = Path(target)
    if path.exists():
        if path.is_dir() or path.suffix == ".ep":
            return load_git_object(path)
        return load_openable_json(path)

    from edsl.coop import Coop

    return Coop().pull(target, expected_object_type=expected_object_type)


def load_openable_json(path: Path):
    data = read_serialized_object(path)
    class_name = data.get("edsl_class_name", "")
    if class_name == "Survey":
        from edsl.surveys import Survey

        return Survey.from_dict(data)
    if class_name == "AgentList":
        from edsl.agents import AgentList

        return AgentList.from_dict(data)
    if class_name == "Jobs":
        from edsl.jobs import Jobs

        return Jobs.from_dict(data)
    if class_name == "Results":
        from edsl.results import Results

        return Results.from_dict(data)
    if class_name == "ScenarioList":
        from edsl.scenarios import ScenarioList

        return ScenarioList.from_dict(data)
    if class_name == "ModelList":
        from edsl.language_models import ModelList

        return ModelList.from_dict(data)
    error(
        "UNSUPPORTED_OBJECT",
        f"Unsupported or missing edsl_class_name in JSON: {class_name or 'unknown'}",
        suggestion="Expected a serialized Survey, AgentList, Jobs, Results, ScenarioList, or ModelList.",
        exit_code=EXIT_USAGE,
    )


def jsonable(value):
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if hasattr(value, "items"):
        return {key: jsonable(val) for key, val in value.items()}
    if hasattr(value, "__dict__"):
        return {
            key: jsonable(val)
            for key, val in value.__dict__.items()
            if not key.startswith("_")
        }
    return value


def save_results(results_obj, output_path: str) -> dict:
    path = Path(output_path)
    if path.suffix == ".ep":
        info = results_obj.git.save(path)
        return {
            "path": info.get("path", str(path)),
            "format": "ep",
            "object_type": "Results",
            "commit": info.get("commit"),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results_obj.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    return {"path": str(path), "format": "json", "object_type": "Results"}


def save_edsl_object(obj, output_path: str, object_type: str | None = None) -> dict:
    path = Path(output_path)
    class_name = object_type or type(obj).__name__
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".ep":
        info = obj.git.save(path)
        return {
            "path": info.get("path", str(path)),
            "format": "ep",
            "object_type": class_name,
            "commit": info.get("commit"),
        }

    if hasattr(obj, "save") and path.suffix in ("", ".gz"):
        saved = obj.save(str(path))
        return {
            "path": str(saved) if saved else str(path),
            "format": "serialized",
            "object_type": class_name,
        }

    path.write_text(json.dumps(obj.to_dict(), indent=2, default=str), encoding="utf-8")
    return {"path": str(path), "format": "json", "object_type": class_name}


def load_results_object(file_path: str):
    from edsl.results import Results

    path = Path(file_path)
    if path.is_dir() or path.suffix == ".ep":
        return Results.git.load(path)
    if path.name.endswith(".json.gz"):
        data = read_serialized_object(path)
    else:
        data = read_json_file(file_path)
    return Results.from_dict(data)
