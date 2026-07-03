"""Git-backed package persistence for Survey objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import SurveyError

if TYPE_CHECKING:
    from .survey import Survey


FORMAT_NAME = "edsl.survey.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()


class SurveyGitError(SurveyError):
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


class SurveyGitNestedRepoWarning(UserWarning):
    """Warning emitted when a Survey Git package is nested in another Git repo."""


class SurveyGitDescriptor(GitBackedDescriptor):
    """Descriptor exposing Git package operations on Survey classes/instances."""

    def __init__(self) -> None:
        super().__init__(_git_spec)


class SurveyGitPackage(gitpkg.GitPackage):
    """Package-level helper for a Git-backed Survey directory."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="Survey",
            display_name=_package_display_name(Path(path)),
            error_cls=SurveyGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}

    def html(
        self,
        filename: str | Path | None = None,
        *,
        ref: str = "HEAD",
        **kwargs,
    ) -> str:
        """Render this package as an HTML document."""
        survey = _read_survey(self.path, ref)
        if filename is None:
            file_store = survey.html(**kwargs)
        else:
            file_store = survey.html(filename=str(filename), **kwargs)
        path = Path(file_store.path)
        return path.read_text(encoding="utf-8")


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="Survey",
        package_suffix=PACKAGE_SUFFIX,
        default_name="survey",
        error_cls=SurveyGitError,
        warning_cls=SurveyGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=SurveyGitPackage,
        read=_read_survey,
        write=_write_survey,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_survey_git_accessor",
        default_commit_message="Save Survey",
    )


def _read_survey(path: Path, ref: str) -> "Survey":
    survey_dict = _read_survey_dict_at_ref(path, ref)
    from .survey import Survey

    return Survey.from_dict(survey_dict)


def _write_survey(path: Path, survey: "Survey", **_kwargs) -> dict:
    (path / "questions").mkdir(exist_ok=True)
    (path / "metadata").mkdir(exist_ok=True)

    survey_dict = survey.to_dict(add_edsl_version=False)
    existing_order, existing_questions = _load_existing_package_state(path)
    question_ids = _question_ids_for_questions(
        survey_dict["questions"], existing_order, existing_questions
    )
    _write_package(path, survey, survey_dict, question_ids)
    return {}


def _normalize_package_path(path, for_load: bool = False) -> Path:
    return gitpkg.normalize_package_path(
        path,
        package_suffix=PACKAGE_SUFFIX,
        for_load=for_load,
    )


def _default_unsaved_package_path() -> Path:
    return _normalize_package_path("survey")


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _init_package(path: Path) -> None:
    gitpkg.init_package(path, error_cls=SurveyGitError)
    (path / "questions").mkdir(exist_ok=True)
    (path / "metadata").mkdir(exist_ok=True)


def _read_survey_dict_at_ref(path: Path, ref: str) -> dict:
    manifest = _load_manifest_at_ref(path, ref)
    survey_dict = {
        "questions": [
            gitpkg.read_json_at_ref(
                path,
                f"questions/{question_id}.json",
                ref,
                error_cls=SurveyGitError,
            )
            for question_id in manifest.get("question_order", [])
        ],
        "memory_plan": _read_optional_json_at_ref(
            path, "metadata/memory_plan.json", ref, default={}
        ),
        "rule_collection": _read_optional_json_at_ref(
            path, "metadata/rule_collection.json", ref, default={}
        ),
        "question_groups": _read_optional_json_at_ref(
            path, "metadata/question_groups.json", ref, default={}
        ),
    }
    optional_fields = {
        "name": "metadata/name.json",
        "questions_to_randomize": "metadata/questions_to_randomize.json",
        "options_to_pin": "metadata/options_to_pin.json",
    }
    for key, file_path in optional_fields.items():
        value = _read_optional_json_at_ref(path, file_path, ref, default=None)
        if value is not None:
            survey_dict[key] = value
    return survey_dict


def _read_optional_json_at_ref(path: Path, file_path: str, ref: str, default):
    try:
        return gitpkg.read_json_at_ref(path, file_path, ref, error_cls=SurveyGitError)
    except SurveyGitError:
        return default


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(
        path, "manifest.json", ref, error_cls=SurveyGitError
    )
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported Survey git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported Survey git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _load_existing_order(path: Path) -> list[str]:
    manifest = gitpkg.read_manifest_file(path)
    return list(manifest.get("question_order", []))


def _load_existing_package_state(path: Path) -> tuple[list[str], dict[str, dict]]:
    existing_order = _load_existing_order(path)
    existing_questions = {}
    for question_id in existing_order:
        question_path = path / "questions" / f"{question_id}.json"
        if not question_path.exists():
            continue
        try:
            existing_questions[question_id] = json.loads(question_path.read_text())
        except json.JSONDecodeError:
            continue
    return existing_order, existing_questions


def _question_ids_for_questions(
    question_dicts: list[dict],
    existing_order: list[str],
    existing_questions: dict[str, dict],
) -> list[str]:
    used: set[str] = set()
    assigned: list[str] = []
    next_index = _next_question_index(existing_order)
    for question_dict in question_dicts:
        matched_id = None
        for question_id in existing_order:
            if question_id in used:
                continue
            if existing_questions.get(question_id) == question_dict:
                matched_id = question_id
                break
        if matched_id is None:
            while True:
                candidate = f"{next_index:06d}"
                next_index += 1
                if candidate not in used and candidate not in existing_questions:
                    matched_id = candidate
                    break
        used.add(matched_id)
        assigned.append(matched_id)
    return assigned


def _next_question_index(existing_order: list[str]) -> int:
    numeric_ids = [
        int(question_id) for question_id in existing_order if question_id.isdigit()
    ]
    return max(numeric_ids, default=0) + 1


def _write_package(
    path: Path, survey: "Survey", survey_dict: dict, question_ids: list[str]
) -> None:
    _write_manifest(path, survey, survey_dict, question_ids)
    _write_questions(path, survey_dict["questions"], question_ids)
    _write_metadata(path, survey_dict)


def _write_manifest(
    path: Path, survey: "Survey", survey_dict: dict, question_ids: list[str]
) -> None:
    existing_manifest = gitpkg.read_manifest_file(path)
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "Survey",
        "object_type": "Survey",
        "question_order": question_ids,
        "n_questions": len(question_ids),
    }
    if survey_dict.get("name") is not None:
        manifest["name"] = survey_dict["name"]
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


def _write_questions(
    path: Path, question_dicts: list[dict], question_ids: list[str]
) -> None:
    questions_dir = path / "questions"
    questions_dir.mkdir(exist_ok=True)
    live_files = {f"{question_id}.json" for question_id in question_ids}
    for question_id, question_dict in zip(question_ids, question_dicts):
        (questions_dir / f"{question_id}.json").write_text(
            json.dumps(question_dict, indent=2, sort_keys=True) + "\n"
        )
    for existing in questions_dir.glob("*.json"):
        if existing.name not in live_files:
            existing.unlink()


def _write_metadata(path: Path, survey_dict: dict) -> None:
    metadata_dir = path / "metadata"
    metadata_dir.mkdir(exist_ok=True)
    required = {
        "memory_plan": survey_dict["memory_plan"],
        "rule_collection": survey_dict["rule_collection"],
        "question_groups": survey_dict["question_groups"],
    }
    optional = {
        "name": survey_dict.get("name"),
        "questions_to_randomize": survey_dict.get("questions_to_randomize"),
        "options_to_pin": survey_dict.get("options_to_pin"),
    }
    for name, value in required.items():
        (metadata_dir / f"{name}.json").write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n"
        )
    for name, value in optional.items():
        target = metadata_dir / f"{name}.json"
        if value is None:
            if target.exists():
                target.unlink()
            continue
        target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _refresh_instance_from_loaded(instance: "Survey", loaded: "Survey") -> None:
    accessor = instance.__dict__.get("_survey_git_accessor")
    instance.__dict__.update(loaded.__dict__)
    if accessor is not None:
        instance.__dict__["_survey_git_accessor"] = accessor


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    questions_dir = path / "questions"
    metadata_dir = path / "metadata"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    if not questions_dir.is_dir():
        errors.append("missing questions directory")
    if not metadata_dir.is_dir():
        errors.append("missing metadata directory")
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid manifest.json: {exc.msg}"]
    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "Survey":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")
    question_order = manifest.get("question_order")
    if not isinstance(question_order, list):
        errors.append("manifest question_order must be a list")
        question_order = []
    seen: set[str] = set()
    for question_id in question_order:
        if not isinstance(question_id, str):
            errors.append(f"invalid question id in manifest: {question_id!r}")
            continue
        if question_id in seen:
            errors.append(f"duplicate question id: {question_id}")
        seen.add(question_id)
        question_path = questions_dir / f"{question_id}.json"
        if not question_path.exists():
            errors.append(f"missing question file: questions/{question_id}.json")
            continue
        try:
            json.loads(question_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(
                f"invalid question file questions/{question_id}.json: {exc.msg}"
            )
    if questions_dir.is_dir():
        expected_files = {f"{question_id}.json" for question_id in seen}
        for question_file in sorted(questions_dir.glob("*.json")):
            if question_file.name not in expected_files:
                errors.append(f"extra question file: questions/{question_file.name}")
    for name in ["memory_plan", "rule_collection", "question_groups"]:
        metadata_path = metadata_dir / f"{name}.json"
        if not metadata_path.exists():
            errors.append(f"missing metadata file: metadata/{name}.json")
            continue
        try:
            json.loads(metadata_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid metadata file metadata/{name}.json: {exc.msg}")
    n_questions = manifest.get("n_questions")
    if n_questions is not None and n_questions != len(question_order):
        errors.append("manifest n_questions does not match question_order")
    return errors


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)
