"""A package's git remote: ``origin`` and ``remote_url`` name the ``obj-<uuid>``
repo whose URL Coop returned for the package's object."""

import json
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from edsl import Survey
from edsl.base import git_package as gitpkg

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="package tests require git"
)

COOP_UUID = "11111111-2222-4333-8444-555555555555"


def _manifest(package_path: Path) -> dict:
    with zipfile.ZipFile(package_path) as archive:
        return json.loads(archive.read("manifest.json"))


def _bare_repo(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "--bare", str(path)], check=True)
    return path


def _pushed_worktree(tmp_path, coop_info: dict) -> Path:
    """An unpacked package whose coop_info.json is ``coop_info``."""
    package_path = tmp_path / "survey.ep"
    Survey.example().git.save(package_path)
    worktree = gitpkg.unpack_package_archive(package_path, package_suffix=".ep")
    (worktree / "coop_info.json").write_text(json.dumps(coop_info))
    return worktree


def test_push_without_a_remote_goes_to_the_repo_coop_returned(tmp_path):
    repo = _bare_repo(tmp_path / "host" / f"obj-{COOP_UUID}.git")
    package_path = tmp_path / "survey.ep"
    survey = Survey.example()
    survey.git.save(package_path)
    survey.git._write_coop_info_and_commit(
        {"uuid": COOP_UUID, "git_remote_url": f"file://{repo}"}, message="pushed"
    )

    info = survey.git.push()

    manifest = _manifest(package_path)
    assert info["remote"] == "origin"
    assert manifest["object_uuid"] == COOP_UUID
    assert manifest["remote_url"] == f"file://{repo}"
    assert "remotes" not in manifest
    assert survey.git.remotes() == {"origin": f"file://{repo}"}
    assert gitpkg.git(repo, "rev-parse", "HEAD", capture=True).strip() == info["commit"]


def test_push_without_a_coop_object_is_refused(tmp_path):
    survey = Survey.example()
    survey.git.save(tmp_path / "survey.ep")

    with pytest.raises(Exception, match="no Expected Parrot object yet"):
        survey.git.push()


def test_push_without_a_repo_from_coop_is_refused(tmp_path):
    survey = Survey.example()
    survey.git.save(tmp_path / "survey.ep")
    survey.git._write_coop_info_and_commit({"uuid": COOP_UUID}, message="pushed")

    with pytest.raises(ValueError, match="Coop gave this package no git repo"):
        survey.git.push()


def test_an_older_origin_is_repointed_to_the_repo_coop_returned(tmp_path):
    url = f"https://git.example.test/edsl/alice/obj-{COOP_UUID}.git"
    worktree = _pushed_worktree(tmp_path, {"uuid": COOP_UUID, "git_remote_url": url})
    other = f"https://alice:key@old.example.test/edsl/alice/obj-{COOP_UUID}.git"
    gitpkg.git(worktree, "remote", "add", "origin", other)

    assert gitpkg.record_object_remote(worktree) == url
    assert gitpkg.read_manifest_file(worktree)["remote_url"] == url
    assert gitpkg.git(worktree, "remote", "get-url", "origin", capture=True).strip() == url


def test_an_origin_that_is_not_an_object_repo_is_refused(tmp_path):
    worktree = _pushed_worktree(tmp_path, {"uuid": COOP_UUID, "git_remote_url": "file:///x"})
    gitpkg.git(worktree, "remote", "add", "origin", "https://github.com/alice/survey.git")

    with pytest.raises(gitpkg.GitPackageError, match="not an Expected Parrot repo"):
        gitpkg.record_object_remote(worktree)


def test_no_repo_from_coop_leaves_the_package_without_a_remote(tmp_path):
    worktree = _pushed_worktree(tmp_path, {"uuid": COOP_UUID})

    assert gitpkg.record_object_remote(worktree) is None
    assert "remote_url" not in gitpkg.read_manifest_file(worktree)
    assert gitpkg.git(worktree, "remote", capture=True) == ""


def test_a_url_with_credentials_sends_no_bearer_header():
    url = "https://alice:key@git.example.test/edsl/alice/obj-x.git"
    assert gitpkg.without_credentials(url) == "https://git.example.test/edsl/alice/obj-x.git"
    assert gitpkg.http_auth_git_env(url) == {}


@pytest.fixture
def trusted_git_host(monkeypatch):
    monkeypatch.setattr(gitpkg, "coop_git_host", lambda: "https://git.example.test")
    monkeypatch.setattr(gitpkg, "expected_parrot_api_key", lambda: "the-key")


def test_the_default_key_goes_to_coops_git_host(trusted_git_host):
    env = gitpkg.http_auth_git_env(f"https://git.example.test/edsl/alice/obj-{COOP_UUID}.git")
    assert "the-key" in Path(env["EDSL_GIT_AUTH_CONFIG"]).read_text()
    Path(env["EDSL_GIT_AUTH_CONFIG"]).unlink()


@pytest.mark.parametrize(
    "url",
    [
        f"https://attacker.example/obj-{COOP_UUID}.git",
        f"http://git.example.test/edsl/alice/obj-{COOP_UUID}.git",
        f"https://git.example.test:8443/edsl/alice/obj-{COOP_UUID}.git",
        f"https://git.example.test.attacker.example/obj-{COOP_UUID}.git",
    ],
)
def test_the_default_key_never_goes_to_another_host(trusted_git_host, url):
    assert gitpkg.http_auth_git_env(url) == {}


def test_coop_git_host_keeps_coop_notices_off_stdout(monkeypatch, capsys):
    class FakeResponse:
        def json(self):
            return {"server_url": "https://git.example.test/edsl"}

    class FakeCoop:
        def _send_server_request(self, uri, method, **kwargs):
            return FakeResponse()

        def _resolve_server_response(self, response):
            print("EDSL Update Available!")

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)

    assert gitpkg.coop_git_host() == "https://git.example.test"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "EDSL Update Available!" in captured.err


def test_the_default_key_stays_home_when_coop_reports_no_git_host(monkeypatch):
    monkeypatch.setattr(gitpkg, "coop_git_host", lambda: None)
    monkeypatch.setattr(gitpkg, "expected_parrot_api_key", lambda: "the-key")
    assert gitpkg.http_auth_git_env(f"https://git.example.test/obj-{COOP_UUID}.git") == {}
