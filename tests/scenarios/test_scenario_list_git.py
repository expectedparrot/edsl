import json
import base64
import shutil
import subprocess

import pytest

from edsl import FileStore, Scenario, ScenarioList
from edsl.scenarios import ScenarioListGitError, ScenarioListGitNestedRepoWarning
from edsl.scenarios.exceptions import ScenarioError
from edsl.base.base_exception import BaseException as EDSLBaseException


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="ScenarioList git package tests require git"
)


def test_scenario_list_git_error_uses_scenario_exception_hierarchy():
    assert issubclass(ScenarioListGitError, ScenarioError)
    assert issubclass(ScenarioListGitError, EDSLBaseException)
    assert issubclass(ScenarioListGitNestedRepoWarning, UserWarning)


def test_scenario_list_git_save_default_path_and_load_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    scenario_list = ScenarioList.example()

    info = scenario_list.git.save()

    package_path = tmp_path / "scenario_list.scenario_list.ep"
    assert info["status"] == "ok"
    assert info["path"] == "scenario_list.scenario_list.ep"
    assert package_path.is_dir()
    assert (package_path / ".git").is_dir()
    assert (package_path / "manifest.json").is_file()
    assert (package_path / "scenarios" / "000001.json").is_file()

    manifest = json.loads((package_path / "manifest.json").read_text())
    assert manifest["format"] == "edsl.scenario_list.git_package"
    assert manifest["edsl_class_name"] == "ScenarioList"
    assert manifest["object_type"] == "ScenarioList"
    assert manifest["scenario_order"] == ["000001", "000002"]
    assert "edsl_version" in manifest

    loaded = ScenarioList.git.load(package_path)
    assert loaded == scenario_list
    assert loaded.git.path == package_path


def test_scenario_list_git_save_codebook_and_validate(tmp_path):
    package_path = tmp_path / "scenarios.scenario_list.ep"
    scenario_list = ScenarioList(
        [Scenario({"food": "pizza"})], codebook={"food": "Favorite food"}
    )

    scenario_list.git.save(package_path, message="initial scenarios")

    assert json.loads((package_path / "codebook.json").read_text()) == {
        "food": "Favorite food"
    }
    loaded = ScenarioList.git.load(package_path)
    assert loaded == scenario_list
    assert loaded.codebook == {"food": "Favorite food"}
    assert scenario_list.git.validate() == {"status": "ok", "errors": []}


def test_scenario_list_git_stores_filestore_as_content_addressed_blob(tmp_path):
    source_path = tmp_path / "source.txt"
    source_path.write_text("hello from a filestore\n")
    package_path = tmp_path / "files.scenario_list.ep"
    scenario_list = ScenarioList([Scenario({"document": FileStore(str(source_path))})])

    scenario_list.git.save(package_path)

    scenario_json = json.loads((package_path / "scenarios" / "000001.json").read_text())
    filestore_ref = scenario_json["document"]
    assert filestore_ref["edsl_type"] == "FileStoreRef"
    assert "base64_string" not in json.dumps(scenario_json)

    sha256 = filestore_ref["sha256"]
    blob_path = package_path / "files" / "sha256" / sha256[:2] / sha256[2:]
    assert blob_path.read_bytes() == b"hello from a filestore\n"
    filestore_manifest = json.loads((package_path / "filestore_manifest.json").read_text())
    assert filestore_manifest["format"] == "edsl.scenario_list.filestore_manifest"
    assert filestore_manifest["files"][0]["sha256"] == sha256

    loaded = ScenarioList.git.load(package_path)
    loaded_file = loaded[0]["document"]
    assert isinstance(loaded_file, FileStore)
    assert base64.b64decode(loaded_file.base64_string) == b"hello from a filestore\n"
    assert loaded_file.suffix == "txt"
    assert scenario_list.git.validate() == {"status": "ok", "errors": []}


def test_scenario_list_git_validate_detects_missing_filestore_blob(tmp_path):
    source_path = tmp_path / "source.txt"
    source_path.write_text("hello from a filestore\n")
    package_path = tmp_path / "files.scenario_list.ep"
    scenario_list = ScenarioList([Scenario({"document": FileStore(str(source_path))})])
    scenario_list.git.save(package_path)

    scenario_json = json.loads((package_path / "scenarios" / "000001.json").read_text())
    sha256 = scenario_json["document"]["sha256"]
    (package_path / "files" / "sha256" / sha256[:2] / sha256[2:]).unlink()

    validation = scenario_list.git.validate()

    assert validation["status"] == "invalid"
    missing_blob_error = f"missing FileStore blob: files/sha256/{sha256[:2]}/{sha256[2:]}"
    assert validation["errors"].count(missing_blob_error) == 2


def test_scenario_list_git_loads_historical_filestore_blob(tmp_path):
    first_source = tmp_path / "first.txt"
    second_source = tmp_path / "second.txt"
    first_source.write_text("first file\n")
    second_source.write_text("second file\n")
    package_path = tmp_path / "files.scenario_list.ep"

    first_list = ScenarioList([Scenario({"document": FileStore(str(first_source))})])
    first = first_list.git.save(package_path, message="first file")
    second_list = ScenarioList([Scenario({"document": FileStore(str(second_source))})])
    second = second_list.git.save(package_path, message="second file")

    old = ScenarioList.git.load(package_path, ref=first["commit"])
    current = ScenarioList.git.load(package_path, ref=second["commit"])

    assert base64.b64decode(old[0]["document"].base64_string) == b"first file\n"
    assert base64.b64decode(current[0]["document"].base64_string) == b"second file\n"


def test_scenario_list_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "scenarios.scenario_list.ep"
    first_list = ScenarioList.example()
    first = first_list.git.save(package_path, message="initial")

    second_list = ScenarioList([*ScenarioList.example(), Scenario({"extra": True})])
    second = second_list.git.save(package_path, message="updated")

    old = ScenarioList.git.load(package_path, ref=first["commit"])
    current = ScenarioList.git.load(package_path)

    assert old == first_list
    assert current == second_list
    assert current.git.commit == second["commit"]


def test_scenario_list_git_branch_tag_restore(tmp_path):
    package_path = tmp_path / "scenarios.scenario_list.ep"
    scenario_list = ScenarioList.example()
    first = scenario_list.git.save(package_path, message="main")
    tag_info = scenario_list.git.tag("baseline", message="baseline scenarios")

    assert tag_info["commit"] == first["commit"]
    assert scenario_list.git.tags() == ["baseline"]

    scenario_list.git.branch("experiment")
    scenario_list.git.switch("experiment")
    updated = ScenarioList([*ScenarioList.example(), Scenario({"extra": True})])
    updated.git.save(package_path, message="experiment")

    restore_info = updated.git.restore("baseline")

    assert restore_info["commit"] == first["commit"]
    assert updated == scenario_list
    assert subprocess.check_output(
        ["git", "-C", str(package_path), "branch", "--show-current"], text=True
    ).strip() == "experiment"


def test_scenario_list_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.scenario_list.ep"
    second_path = tmp_path / "second.scenario_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = ScenarioList.example()
    first.git.save(first_path, message="initial scenarios")
    first.git.remote_add("origin", str(remote_path))
    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"

    subprocess.run(["git", "clone", str(remote_path), str(second_path)], check=True)
    second = ScenarioList.git.load(second_path)
    assert second == first

    updated = ScenarioList([*ScenarioList.example(), Scenario({"extra": True})])
    updated.git.save(first_path, message="updated scenarios")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated
