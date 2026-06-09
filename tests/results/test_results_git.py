import json
import shutil
import subprocess

import pytest

from edsl.results import Results, ResultsGitError, ResultsGitNestedRepoWarning
from edsl.results.exceptions import ResultsError
from edsl.base.base_exception import BaseException as EDSLBaseException


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="Results git package tests require git"
)


def test_results_git_error_uses_results_exception_hierarchy():
    assert issubclass(ResultsGitError, ResultsError)
    assert issubclass(ResultsGitError, EDSLBaseException)
    assert issubclass(ResultsGitNestedRepoWarning, UserWarning)


def test_results_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = Results.example()
    results._job_uuid = "job-123"
    results.results_uuid = "results-456"

    info = results.git.save()

    package_path = tmp_path / "results.results.ep"
    assert info["status"] == "ok"
    assert info["path"] == "results.results.ep"
    assert package_path.is_dir()
    assert (package_path / ".git").is_dir()
    assert (package_path / "manifest.json").is_file()
    assert (package_path / "results.jsonl").is_file()

    manifest = json.loads((package_path / "manifest.json").read_text())
    assert manifest["format"] == "edsl.results.git_package"
    assert manifest["edsl_class_name"] == "Results"
    assert manifest["object_type"] == "Results"
    assert manifest["n_results"] == len(results)
    assert manifest["content_sha256"] == info["content_sha256"]
    assert manifest["source"]["job_uuid"] == "job-123"
    assert manifest["source"]["results_uuid"] == "results-456"
    assert "edsl_version" in manifest

    loaded = Results.git.load(package_path)
    assert loaded == results
    assert loaded.git.path == package_path
    assert loaded.git.validate() == {"status": "ok", "errors": []}


def test_results_git_save_is_immutable_by_default(tmp_path):
    package_path = tmp_path / "archive.results.ep"
    first = Results.example()
    first.git.save(package_path, message="first")

    second = Results.example().sample(1)
    with pytest.raises(ResultsGitError, match="immutable"):
        second.git.save(package_path, message="second")

    info = second.git.save(package_path, message="second", allow_new_commit=True)
    assert info["status"] == "ok"
    assert Results.git.load(package_path) == second


def test_results_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "archive.results.ep"
    first_results = Results.example()
    first = first_results.git.save(package_path, message="initial")

    second_results = Results.example().sample(1)
    second = second_results.git.save(
        package_path, message="updated", allow_new_commit=True
    )

    old = Results.git.load(package_path, ref=first["commit"])
    current = Results.git.load(package_path)

    assert old == first_results
    assert current == second_results
    assert current.git.commit == second["commit"]


def test_results_git_tag_restore(tmp_path):
    package_path = tmp_path / "archive.results.ep"
    results = Results.example()
    first = results.git.save(package_path, message="main")
    tag_info = results.git.tag("published", message="published results")

    assert tag_info["commit"] == first["commit"]
    assert results.git.tags() == ["published"]

    updated = Results.example().sample(1)
    updated.git.save(package_path, message="updated", allow_new_commit=True)
    restore_info = updated.git.restore("published")

    assert restore_info["commit"] == first["commit"]
    assert updated == results


def test_results_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.results.ep"
    second_path = tmp_path / "second.results.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = Results.example()
    first.git.save(first_path, message="initial results")
    first.git.remote_add("origin", str(remote_path))
    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"

    subprocess.run(["git", "clone", str(remote_path), str(second_path)], check=True)
    second = Results.git.load(second_path)
    assert second == first
