"""A package's ``object_uuid``: its one id for its Coop object and git repo."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from uuid import UUID

import pytest

from edsl import Jobs, Survey
from edsl.base import git_package as gitpkg

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="package tests require git"
)


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


def test_first_save_records_a_uuid_that_later_saves_keep(tmp_path):
    package_path = tmp_path / "survey.ep"
    survey = Survey.example()
    survey.git.save(package_path)
    object_uuid = _manifest(package_path)["object_uuid"]
    UUID(object_uuid)

    survey.git.save(message="resave")
    Survey.git.load(package_path).git.save(message="reopened")

    assert _manifest(package_path)["object_uuid"] == object_uuid


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


@pytest.mark.parametrize("source", ["coop_info", "origin"])
def test_an_older_package_reuses_the_uuid_it_carries(tmp_path, monkeypatch, source):
    package_path = tmp_path / "survey.ep"
    Survey.example().git.save(package_path)
    carried = "11111111-2222-4333-8444-555555555555"

    class FakeCoop:
        """Save checks Coop for a newer copy of a pushed package; there is none."""

        def __init__(self, url=None):
            pass

        def get_metadata(self, url_or_uuid):
            return {"uuid": str(url_or_uuid)}

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)

    def make_older(worktree):
        manifest = gitpkg.read_manifest_file(worktree)
        manifest.pop("object_uuid")
        gitpkg.write_manifest_dict(worktree, manifest)
        if source == "coop_info":
            (worktree / "coop_info.json").write_text(json.dumps({"uuid": carried}))
        else:
            url = f"https://git.example.test/edsl/alice/obj-{carried}.git"
            subprocess.run(["git", "-C", str(worktree), "remote", "add", "origin", url], check=True)

    _edit_package(package_path, make_older)
    assert "object_uuid" not in _manifest(package_path)

    Survey.git.load(package_path).git.save(message="resave")

    assert _manifest(package_path)["object_uuid"] == carried


def test_only_the_top_level_package_of_a_job_gets_a_uuid(tmp_path):
    package_path = tmp_path / "job.ep"
    Jobs.example().git.save(package_path)

    with zipfile.ZipFile(package_path) as archive:
        manifests = [
            json.loads(archive.read(name))
            for name in archive.namelist()
            if name.endswith("manifest.json") and not name.startswith(".git/")
        ]

    assert len(manifests) > 1
    assert [m for m in manifests if "object_uuid" in m] == [_manifest(package_path)]


def test_coop_push_sends_the_package_uuid(tmp_path, monkeypatch):
    package_path = tmp_path / "survey.ep"
    survey = Survey.example()
    survey.git.save(package_path)
    object_uuid = _manifest(package_path)["object_uuid"]
    sent = []

    def fake_push(self, **kwargs):
        sent.append(kwargs.get("uuid"))
        return {"uuid": kwargs.get("uuid"), "url": "https://example.test/content/x"}

    class FakeCoop:
        def __init__(self, url=None):
            pass

        def get_metadata(self, url_or_uuid):
            return {"uuid": str(url_or_uuid)}

    monkeypatch.setattr(Survey, "push", fake_push)
    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)

    survey.git.coop_push()

    assert sent == [object_uuid]
    with zipfile.ZipFile(package_path) as archive:
        assert json.loads(archive.read("coop_info.json"))["uuid"] == object_uuid
