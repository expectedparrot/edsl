import json
import shutil
import subprocess

import pytest

from edsl import Model, ModelList
from edsl.base.base_exception import BaseException as EDSLBaseException
from edsl.language_models import ModelListGitError, ModelListGitNestedRepoWarning
from edsl.language_models.exceptions import LanguageModelExceptions


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="ModelList git package tests require git"
)


def test_model_list_git_error_uses_language_model_exception_hierarchy():
    assert issubclass(ModelListGitError, LanguageModelExceptions)
    assert issubclass(ModelListGitError, EDSLBaseException)
    assert issubclass(ModelListGitNestedRepoWarning, UserWarning)


def test_model_list_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model_list = ModelList.example()

    info = model_list.git.save()

    package_path = tmp_path / "model_list.model_list.ep"
    assert info["status"] == "ok"
    assert info["path"] == "model_list.model_list.ep"
    assert package_path.is_dir()
    assert (package_path / ".git").is_dir()
    assert (package_path / "manifest.json").is_file()
    assert (package_path / "models" / "000001.json").is_file()

    manifest = json.loads((package_path / "manifest.json").read_text())
    assert manifest["format"] == "edsl.model_list.git_package"
    assert manifest["edsl_class_name"] == "ModelList"
    assert manifest["object_type"] == "ModelList"
    assert manifest["model_order"] == ["000001", "000002", "000003"]
    assert "edsl_version" in manifest

    loaded = ModelList.git.load(package_path)
    assert loaded == model_list
    assert loaded.git.path == package_path


def test_model_list_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "models.model_list.ep"
    first_list = ModelList([Model("test", canned_response="first")])
    first = first_list.git.save(package_path, message="initial")

    second_list = ModelList(
        [
            Model("test", canned_response="first"),
            Model("test", canned_response="second"),
        ]
    )
    second = second_list.git.save(package_path, message="updated")

    old = ModelList.git.load(package_path, ref=first["commit"])
    current = ModelList.git.load(package_path)

    assert old == first_list
    assert current == second_list
    assert current.git.commit == second["commit"]


def test_model_list_git_branch_tag_restore(tmp_path):
    package_path = tmp_path / "models.model_list.ep"
    model_list = ModelList([Model("test", canned_response="main")])
    first = model_list.git.save(package_path, message="main")
    tag_info = model_list.git.tag("baseline", message="baseline models")

    assert tag_info["commit"] == first["commit"]
    assert model_list.git.tags() == ["baseline"]

    model_list.git.branch("experiment")
    model_list.git.switch("experiment")
    updated = ModelList([Model("test", canned_response="experiment")])
    updated.git.save(package_path, message="experiment")

    restore_info = updated.git.restore("baseline")

    assert restore_info["commit"] == first["commit"]
    assert updated == model_list
    assert subprocess.check_output(
        ["git", "-C", str(package_path), "branch", "--show-current"], text=True
    ).strip() == "experiment"


def test_model_list_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.model_list.ep"
    second_path = tmp_path / "second.model_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = ModelList([Model("test", canned_response="initial")])
    first.git.save(first_path, message="initial models")
    first.git.remote_add("origin", str(remote_path))
    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"

    subprocess.run(["git", "clone", str(remote_path), str(second_path)], check=True)
    second = ModelList.git.load(second_path)
    assert second == first

    updated = ModelList([Model("test", canned_response="updated")])
    updated.git.save(first_path, message="updated models")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated
