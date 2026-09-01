"""Git-backed package persistence for Jobs objects."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import JobsErrors

if TYPE_CHECKING:
    from .jobs import Jobs


FORMAT_NAME = "edsl.jobs.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()
_COMPONENTS = {
    "survey": "survey",
    "agents": "agents",
    "scenarios": "scenarios",
    "models": "models",
}


class JobsGitError(JobsErrors):
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


class JobsGitNestedRepoWarning(UserWarning):
    """Warning emitted when a Jobs Git package is nested in another Git repo."""


class JobsGitDescriptor(GitBackedDescriptor):
    def __init__(self) -> None:
        super().__init__(_git_spec)


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="Jobs",
        package_suffix=PACKAGE_SUFFIX,
        default_name="jobs",
        error_cls=JobsGitError,
        warning_cls=JobsGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=JobsGitPackage,
        read=_read_job,
        write=_write_job,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_jobs_git_accessor",
        default_commit_message="Save Jobs",
    )


def _read_job(path: Path, ref: str) -> "Jobs":
    with _materialized_ref(path, ref) as tree_path:
        return _read_job_from_tree(tree_path)


def _write_job(path: Path, job: "Jobs", **_kwargs) -> dict:
    _write_job_package(path, job)
    return {}


class JobsGitPackage(gitpkg.GitPackage):
    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="Jobs",
            display_name=_package_display_name(Path(path)),
            error_cls=JobsGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}

    def html(
        self,
        filename: str | Path | None = None,
        *,
        ref: str = "HEAD",
    ) -> str:
        """Render this package as a standalone HTML document."""
        job = _read_job(self.path, ref)
        from edsl.base.html_artifacts import package_remote_context
        from .jobs_html_renderer import JobsHTMLRenderer

        manifest = _load_manifest_at_ref(self.path, ref)
        html = JobsHTMLRenderer(
            job,
            package_context=package_remote_context(
                self.path, ref, manifest=manifest, error_cls=JobsGitError
            ),
        ).render()
        if filename is not None:
            Path(filename).write_text(html, encoding="utf-8")
        return html


class _materialized_ref:
    def __init__(self, path: Path, ref: str) -> None:
        self.path = path
        self.ref = ref
        self._tempdir: Optional[tempfile.TemporaryDirectory] = None

    def __enter__(self) -> Path:
        self._tempdir = tempfile.TemporaryDirectory()
        temp_path = Path(self._tempdir.name)
        tar_path = temp_path / "archive.tar"
        gitpkg.run_git(
            [
                "git",
                "-C",
                str(self.path),
                "archive",
                "--format=tar",
                "-o",
                str(tar_path),
                self.ref,
            ],
            error_cls=JobsGitError,
        )
        with tarfile.open(tar_path) as archive:
            if sys.version_info >= (3, 12):
                archive.extractall(temp_path / "tree", filter="data")
            else:
                archive.extractall(temp_path / "tree")
        return temp_path / "tree"

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._tempdir is not None:
            self._tempdir.cleanup()


def _normalize_package_path(path, for_load: bool = False) -> Path:
    return gitpkg.normalize_package_path(
        path, package_suffix=PACKAGE_SUFFIX, for_load=for_load
    )


def _default_unsaved_package_path() -> Path:
    return _normalize_package_path("jobs")


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(
        path, "manifest.json", ref, error_cls=JobsGitError
    )
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported Jobs git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported Jobs git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _init_package(path: Path) -> None:
    gitpkg.init_package(path, error_cls=JobsGitError)


def _write_job_package(path: Path, job: "Jobs") -> None:
    _write_manifest(path, job)
    _write_job_metadata(path, job)
    _write_embedded_survey(path / "survey", job.survey)
    _write_embedded_agents(path / "agents", job.agents)
    _write_embedded_scenarios(path / "scenarios", job.scenarios)
    _write_embedded_models(path / "models", job.models)
    _write_dependencies(path, job)


def _write_manifest(path: Path, job: "Jobs") -> None:
    existing_manifest = gitpkg.read_manifest_file(path)
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "Jobs",
        "object_type": "Jobs",
        "components": dict(_COMPONENTS),
        "has_depends_on": job._depends_on is not None,
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


def _write_job_metadata(path: Path, job: "Jobs") -> None:
    metadata = {
        "_post_run_methods": _jsonable(job._post_run_methods),
        "_where_clauses": list(getattr(job, "_where_clauses", [])),
        "_include_expression": getattr(job, "_include_expression", None),
        "dependencies": ["dependencies/000001"] if job._depends_on is not None else [],
    }
    (path / "job.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    )


def _write_dependencies(path: Path, job: "Jobs") -> None:
    dependencies_dir = path / "dependencies"
    if job._depends_on is None:
        if dependencies_dir.exists():
            shutil.rmtree(dependencies_dir)
        return
    dependency_path = dependencies_dir / "000001"
    dependency_path.mkdir(parents=True, exist_ok=True)
    _write_job_package(dependency_path, job._depends_on)
    for existing in dependencies_dir.iterdir():
        if existing.name != "000001":
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()


def _write_embedded_survey(path: Path, survey) -> None:
    from edsl.surveys import survey_git

    path.mkdir(parents=True, exist_ok=True)
    survey_dict = survey.to_dict(add_edsl_version=False)
    existing_order, existing_questions = survey_git._load_existing_package_state(path)
    question_ids = survey_git._question_ids_for_questions(
        survey_dict["questions"], existing_order, existing_questions
    )
    survey_git._write_package(path, survey, survey_dict, question_ids)


def _write_embedded_agents(path: Path, agents) -> None:
    from edsl.agents import agent_list_git

    path.mkdir(parents=True, exist_ok=True)
    existing_order, existing_agents = agent_list_git._load_existing_package_state(path)
    agent_ids = agent_list_git._agent_ids_for_agents(
        agents, existing_order, existing_agents
    )
    agent_list_git._write_manifest(path, agents, agent_ids)
    agent_list_git._write_agents(path, agents, agent_ids)


def _write_embedded_scenarios(path: Path, scenarios) -> None:
    from edsl.scenarios import scenario_list_git

    path.mkdir(parents=True, exist_ok=True)
    scenario_list_dict = scenarios.to_dict(add_edsl_version=False)
    existing_order, existing_scenarios = scenario_list_git._load_existing_package_state(
        path
    )
    scenario_ids = scenario_list_git._scenario_ids_for_scenarios(
        scenario_list_dict["scenarios"], existing_order, existing_scenarios
    )
    scenario_list_git._write_package(path, scenario_list_dict, scenario_ids)


def _write_embedded_models(path: Path, models) -> None:
    from edsl.language_models import model_list_git

    path.mkdir(parents=True, exist_ok=True)
    model_list_dict = models.to_dict(add_edsl_version=False)
    existing_order, existing_models = model_list_git._load_existing_package_state(path)
    model_ids = model_list_git._model_ids_for_models(
        model_list_dict["models"], existing_order, existing_models
    )
    model_list_git._write_package(path, model_list_dict, model_ids)


def _read_job_from_tree(path: Path) -> "Jobs":
    _load_manifest(path)
    job_metadata = _read_json_file(path / "job.json")
    survey = _read_embedded_survey(path / "survey")
    agents = _read_embedded_agents(path / "agents")
    scenarios = _read_embedded_scenarios(path / "scenarios")
    models = _read_embedded_models(path / "models")

    from .jobs import Jobs

    job = Jobs(survey=survey, agents=agents, models=models, scenarios=scenarios)
    job._post_run_methods = _restore_post_run_methods(
        job_metadata.get("_post_run_methods", [])
    )
    job._where_clauses = list(job_metadata.get("_where_clauses", []))
    job._include_expression = job_metadata.get("_include_expression")
    dependencies = job_metadata.get("dependencies") or []
    if dependencies:
        job._depends_on = _read_job_from_tree(path / dependencies[0])
    return job


def _read_embedded_survey(path: Path):
    from edsl.surveys import Survey

    manifest = _read_json_file(path / "manifest.json")
    survey_dict = {
        "questions": [
            _read_json_file(path / "questions" / f"{question_id}.json")
            for question_id in manifest.get("question_order", [])
        ],
        "memory_plan": _read_optional_json_file(
            path / "metadata" / "memory_plan.json", {}
        ),
        "rule_collection": _read_optional_json_file(
            path / "metadata" / "rule_collection.json", {}
        ),
        "question_groups": _read_optional_json_file(
            path / "metadata" / "question_groups.json", {}
        ),
    }
    for key in ["name", "questions_to_randomize", "options_to_pin"]:
        value = _read_optional_json_file(path / "metadata" / f"{key}.json", None)
        if value is not None:
            survey_dict[key] = value
    return Survey.from_dict(survey_dict)


def _read_embedded_agents(path: Path):
    from edsl.agents import Agent, AgentList

    manifest = _read_json_file(path / "manifest.json")
    agents = [
        Agent.from_dict(_read_json_file(path / "agents" / f"{agent_id}.json"))
        for agent_id in manifest.get("agent_order", [])
    ]
    agent_list = AgentList(agents)
    if manifest.get("codebook"):
        agent_list.set_codebook(manifest["codebook"])
        agent_list._codebook = manifest["codebook"]
    if manifest.get("instruction"):
        agent_list.set_instruction(manifest["instruction"])
    if manifest.get("traits_presentation_template"):
        agent_list.set_traits_presentation_template(
            manifest["traits_presentation_template"]
        )
        agent_list._traits_presentation_template = manifest[
            "traits_presentation_template"
        ]
    return agent_list


def _read_embedded_scenarios(path: Path):
    from edsl.scenarios import ScenarioList

    manifest = _read_json_file(path / "manifest.json")
    scenario_list_dict = {
        "scenarios": [
            _hydrate_filestore_refs(
                path,
                _read_json_file(path / "scenarios" / f"{scenario_id}.json"),
            )
            for scenario_id in manifest.get("scenario_order", [])
        ]
    }
    codebook = _read_optional_json_file(path / "codebook.json", None)
    if codebook:
        scenario_list_dict["codebook"] = codebook
    return ScenarioList.from_dict(scenario_list_dict)


def _read_embedded_models(path: Path):
    from edsl.language_models import ModelList

    manifest = _read_json_file(path / "manifest.json")
    return ModelList.from_dict(
        {
            "models": [
                _read_json_file(path / "models" / f"{model_id}.json")
                for model_id in manifest.get("model_order", [])
            ]
        }
    )


def _hydrate_filestore_refs(path: Path, value: Any) -> Any:
    if isinstance(value, list):
        return [_hydrate_filestore_refs(path, item) for item in value]
    if not isinstance(value, dict):
        return value
    if value.get("edsl_type") == "FileStoreRef":
        return _read_filestore_ref(path, value)
    return {key: _hydrate_filestore_refs(path, item) for key, item in value.items()}


def _read_filestore_ref(path: Path, filestore_ref: dict) -> dict:
    sha256 = filestore_ref.get("sha256")
    if not isinstance(sha256, str):
        raise ValueError(f"Invalid FileStoreRef without sha256: {filestore_ref!r}")
    blob_path = path / "files" / "sha256" / sha256[:2] / sha256[2:]
    if not blob_path.exists():
        raise ValueError(f"Missing FileStore blob for sha256 {sha256}")
    content = blob_path.read_bytes()
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


def _load_manifest(path: Path) -> dict:
    manifest = _read_json_file(path / "manifest.json")
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported Jobs git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported Jobs git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _read_json_file(path: Path) -> dict:
    return json.loads(path.read_text())


def _read_optional_json_file(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def _restore_post_run_methods(value: list) -> list:
    restored = []
    for item in value:
        if isinstance(item, list) and len(item) == 3:
            restored.append((item[0], tuple(item[1]), item[2]))
        else:
            restored.append(item)
    return restored


def _jsonable(value):
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _refresh_instance_from_loaded(instance: "Jobs", loaded: "Jobs") -> None:
    accessor = instance.__dict__.get("_jobs_git_accessor")
    instance.__dict__.update(loaded.__dict__)
    if accessor is not None:
        instance.__dict__["_jobs_git_accessor"] = accessor


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    job_path = path / "job.json"
    if not manifest_path.exists():
        return ["missing manifest.json"]
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid manifest.json: {exc.msg}"]
    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "Jobs":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")
    if not job_path.exists():
        errors.append("missing job.json")
    else:
        try:
            job_metadata = json.loads(job_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid job.json: {exc.msg}")
            job_metadata = {}
    errors.extend(_validate_component(path, "survey"))
    errors.extend(_validate_component(path, "agents"))
    errors.extend(_validate_component(path, "scenarios"))
    errors.extend(_validate_component(path, "models"))
    for dependency in job_metadata.get("dependencies") or []:
        dependency_path = path / dependency
        if not dependency_path.is_dir():
            errors.append(f"missing dependency directory: {dependency}")
            continue
        for error in _validate_package(dependency_path):
            errors.append(f"{dependency}: {error}")
    return errors


def _validate_component(path: Path, component: str) -> list[str]:
    component_path = path / component
    if not component_path.is_dir():
        return [f"missing component directory: {component}"]
    if (component_path / ".git").exists():
        return [f"embedded component must not contain .git: {component}"]
    if component == "survey":
        from edsl.surveys import survey_git

        return [
            f"survey: {error}" for error in survey_git._validate_package(component_path)
        ]
    if component == "agents":
        from edsl.agents import agent_list_git

        return [
            f"agents: {error}"
            for error in agent_list_git._validate_package(component_path)
        ]
    if component == "scenarios":
        from edsl.scenarios import scenario_list_git

        return [
            f"scenarios: {error}"
            for error in scenario_list_git._validate_package(component_path)
        ]
    if component == "models":
        from edsl.language_models import model_list_git

        return [
            f"models: {error}"
            for error in model_list_git._validate_package(component_path)
        ]
    return []


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)
