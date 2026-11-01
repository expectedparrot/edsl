"""A package's ``object_uuid``: its Coop object's uuid, which also names its git repo."""

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from edsl import Jobs, Survey
from edsl.base import git_package as gitpkg

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="package tests require git"
)

COOP_UUID = "11111111-2222-4333-8444-555555555555"


def _manifest(package_path: Path) -> dict:
    with zipfile.ZipFile(package_path) as archive:
        return json.loads(archive.read("manifest.json"))


def _edit_package(package_path: Path, change) -> None:
    """Apply change(worktree) to the package and commit it, outside edsl's save."""
    worktree = gitpkg.unpack_package_archive(package_path, package_suffix=".ep")
    try:
        change(worktree)
        gitpkg.git(worktree, "add", "-A")
        gitpkg.git(
            worktree, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "edit"
        )
        gitpkg.pack_package_archive(worktree, package_path, package_suffix=".ep")
    finally:
        shutil.rmtree(worktree, ignore_errors=True)


@pytest.fixture
def coop(monkeypatch):
    """Coop picks COOP_UUID for a new object; the push kwargs are kept."""
    pushed = []

    def fake_push(self, **kwargs):
        pushed.append(kwargs)
        return {"uuid": COOP_UUID, "url": "https://example.test/content/x"}

    class FakeCoop:
        def __init__(self, url=None):
            pass

        def get_metadata(self, url_or_uuid):
            return {"uuid": str(url_or_uuid)}

    import edsl.coop as coop_module

    monkeypatch.setattr(Survey, "push", fake_push)
    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    return pushed


def test_saving_records_no_uuid(tmp_path):
    package_path = tmp_path / "survey.ep"
    survey = Survey.example()
    survey.git.save(package_path)
    survey.git.save(message="resave")

    assert "object_uuid" not in _manifest(package_path)


def test_coop_push_records_the_uuid_coop_picked(tmp_path, coop):
    package_path = tmp_path / "survey.ep"
    survey = Survey.example()
    survey.git.save(package_path)

    survey.git.coop_push()
    Survey.git.load(package_path).git.save(message="reopened")

    assert "uuid" not in coop[0]
    assert _manifest(package_path)["object_uuid"] == COOP_UUID
    with zipfile.ZipFile(package_path) as archive:
        assert json.loads(archive.read("coop_info.json"))["uuid"] == COOP_UUID


def test_a_rebuilt_manifest_keeps_remote_url(tmp_path):
    package_path = tmp_path / "survey.ep"
    Survey.example().git.save(package_path)
    remote_url = "https://git.example.test/edsl/alice/obj-x.git"

    def add_remote_url(worktree):
        manifest = gitpkg.read_manifest_file(worktree)
        manifest["remote_url"] = remote_url
        gitpkg.write_manifest_dict(worktree, manifest)

    _edit_package(package_path, add_remote_url)
    survey = Survey.git.load(package_path)
    survey.name = "renamed"
    survey.git.save(message="rename")

    manifest = _manifest(package_path)
    assert manifest["remote_url"] == remote_url
    assert manifest["name"] == "renamed"


def test_an_older_pushed_package_takes_the_uuid_in_its_coop_info(tmp_path):
    package_path = tmp_path / "survey.ep"
    Survey.example().git.save(package_path)
    worktree = gitpkg.unpack_package_archive(package_path, package_suffix=".ep")
    assert gitpkg.record_object_uuid(worktree) is None

    (worktree / "coop_info.json").write_text(json.dumps({"uuid": COOP_UUID}))

    assert gitpkg.record_object_uuid(worktree) == COOP_UUID
    assert gitpkg.read_manifest_file(worktree)["object_uuid"] == COOP_UUID


def test_a_coop_info_uuid_that_is_not_a_uuid_is_ignored(tmp_path):
    package_path = tmp_path / "survey.ep"
    Survey.example().git.save(package_path)
    worktree = gitpkg.unpack_package_archive(package_path, package_suffix=".ep")
    (worktree / "coop_info.json").write_text(json.dumps({"uuid": "survey-uuid"}))

    assert gitpkg.record_object_uuid(worktree) is None
    assert "object_uuid" not in gitpkg.read_manifest_file(worktree)


def test_only_the_top_level_package_of_a_job_gets_a_uuid(tmp_path):
    package_path = tmp_path / "job.ep"
    Jobs.example().git.save(package_path)
    worktree = gitpkg.unpack_package_archive(package_path, package_suffix=".ep")
    (worktree / "coop_info.json").write_text(json.dumps({"uuid": COOP_UUID}))
    gitpkg.record_object_uuid(worktree)

    manifests = {
        str(path.relative_to(worktree)): json.loads(path.read_text())
        for path in worktree.rglob("manifest.json")
        if ".git" not in path.parts
    }

    assert len(manifests) > 1
    assert [name for name, m in manifests.items() if "object_uuid" in m] == ["manifest.json"]
