import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from edsl import Model, ModelList
from edsl.base.base_exception import BaseException as EDSLBaseException
from edsl.language_models import ModelListGitError, ModelListGitNestedRepoWarning
from edsl.language_models.exceptions import LanguageModelExceptions


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="ModelList git package tests require git"
)


def _package_json(package_path: Path, member: str):
    with zipfile.ZipFile(package_path) as archive:
        return json.loads(archive.read(member).decode())


def _package_names(package_path: Path) -> set[str]:
    with zipfile.ZipFile(package_path) as archive:
        return set(archive.namelist())


def test_model_list_git_error_uses_language_model_exception_hierarchy():
    assert issubclass(ModelListGitError, LanguageModelExceptions)
    assert issubclass(ModelListGitError, EDSLBaseException)
    assert issubclass(ModelListGitNestedRepoWarning, UserWarning)


def test_model_list_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    model_list = ModelList.example()

    info = model_list.git.save()

    package_path = tmp_path / "model_list.ep"
    assert info["status"] == "ok"
    assert info["path"] == "model_list.ep"
    assert package_path.is_file()
    names = _package_names(package_path)
    assert ".git/HEAD" in names
    assert "manifest.json" in names
    assert "models/000001.json" in names

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["format"] == "edsl.model_list.git_package"
    assert manifest["edsl_class_name"] == "ModelList"
    assert manifest["object_type"] == "ModelList"
    assert manifest["model_order"] == ["000001", "000002", "000003"]
    assert "edsl_version" in manifest

    loaded = ModelList.git.load(package_path)
    assert loaded == model_list
    assert loaded.git.path == package_path


def test_model_list_git_package_html(tmp_path):
    package_path = tmp_path / "models.ep"
    html_path = tmp_path / "models.html"
    model_list = ModelList.example()
    model_list.git.save(package_path)
    model_list.git._write_coop_info_and_commit(
        {
            "uuid": "model-list-uuid",
            "url": "https://www.expectedparrot.com/content/model-list-uuid",
            "alias_url": "https://www.expectedparrot.com/content/alice/shared-models",
            "alias": "shared-models",
            "description": "A shared model list",
            "owner": "alice",
        },
        message="Add Coop info",
    )

    html = ModelList.git.open(package_path).html(filename=html_path)

    assert "<title>EDSL ModelList</title>" in html
    assert "Expected Parrot" in html
    assert "Expected Parrot Server" in html
    assert "remote-meta" in html
    assert "copy-mini" in html
    assert "object alias" in html
    assert "owner" in html
    assert "model-list-uuid" in html
    assert "alice/shared-models" in html
    assert "alias URL" in html
    assert "https://www.expectedparrot.com/content/alice/shared-models" in html
    assert "shared-models" in html
    assert "A shared model list" in html
    assert "alice" in html
    assert '"href": "https://www.expectedparrot.com/content/model-list-uuid"' in html
    assert 'target="_blank"' in html
    assert "collection-table" in html
    assert "<table" in html
    assert html_path.read_text(encoding="utf-8") == html


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


def test_model_list_git_mutation_save_cleans_stale_files_and_round_trips(tmp_path):
    package_path = tmp_path / "models.model_list.ep"
    model_list = ModelList(
        [
            Model("test", canned_response="removed"),
            Model("test", canned_response="kept"),
        ]
    )
    first = model_list.git.save(package_path, message="initial models")

    model_list.pop(0)
    model_list.append(Model("test", canned_response="added"))
    second = model_list.git.save(message="mutated models")

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["model_order"] == ["000002", "000003"]
    names = _package_names(package_path)
    assert "models/000001.json" not in names
    assert "models/000002.json" in names
    assert "models/000003.json" in names
    assert ModelList.git.load(package_path) == model_list
    assert ModelList.git.load(package_path, ref=first["commit"]) == ModelList(
        [
            Model("test", canned_response="removed"),
            Model("test", canned_response="kept"),
        ]
    )
    assert second["commit"] != first["commit"]


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
    assert (
        subprocess.check_output(
            ["git", "-C", str(updated.git.worktree_path), "branch", "--show-current"],
            text=True,
        ).strip()
        == "experiment"
    )


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

    second = ModelList.git.clone(str(remote_path), path=second_path)
    assert second == first

    updated = ModelList([Model("test", canned_response="updated")])
    updated.git.save(first_path, message="updated models")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated
