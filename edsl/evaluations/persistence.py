"""Evaluation packages use EDSL's shared Git-backed .ep machinery."""

import json

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

_warned = set()


class EvaluationPackage(gitpkg.GitPackage):
    def __init__(self, path):
        super().__init__(path, package_suffix=".ep", object_type="Evaluation")


def _read(path, ref):
    from .evaluation import Evaluation

    manifest = gitpkg.read_json_at_ref(
        path, "manifest.json", ref, error_cls=gitpkg.GitPackageError
    )
    if (
        manifest.get("format") != "edsl.evaluation.git_package"
        or manifest.get("format_version") != 1
    ):
        raise ValueError("Unsupported Evaluation package format")
    return Evaluation.from_dict(
        gitpkg.read_json_at_ref(
            path, "evaluation.json", ref, error_cls=gitpkg.GitPackageError
        )
    )


def _write(path, evaluation, **kwargs):
    manifest = gitpkg.read_manifest_file(path)
    manifest.update(
        format="edsl.evaluation.git_package",
        format_version=1,
        object_type="Evaluation",
        edsl_class_name="Evaluation",
    )
    (path / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (path / "evaluation.json").write_text(
        json.dumps(evaluation.to_dict(), indent=2), encoding="utf-8"
    )
    return {}


def _refresh(instance, loaded):
    for key in ("survey", "agents", "scenarios", "models"):
        setattr(instance, key, getattr(loaded, key))


def evaluation_git():
    return GitBackedDescriptor(
        lambda: GitObjectSpec(
            object_type="Evaluation",
            package_suffix=".ep",
            default_name="evaluation",
            error_cls=gitpkg.GitPackageError,
            warning_cls=gitpkg.GitNestedRepoWarning,
            warned_paths=_warned,
            package_cls=EvaluationPackage,
            read=_read,
            write=_write,
            refresh=_refresh,
            accessor_key="_evaluation_git_accessor",
            default_commit_message="Save Evaluation",
        )
    )
