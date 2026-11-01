"""ep push/clone/pull/log/delete with a package's obj-<uuid> git repo."""

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

import edsl.__main__ as cli_module
from edsl import Survey
from edsl.base import git_package as gitpkg

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="package tests require git"
)


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


@pytest.fixture
def git_host(tmp_path):
    """Where Coop's file:// repos live, under ``host/tester``."""
    return tmp_path / "host"


def _repo(git_host: Path, object_uuid: str) -> Path:
    return git_host / "tester" / f"obj-{object_uuid}.git"


@pytest.fixture
def coop(monkeypatch, git_host):
    """Coop as the CLI sees it. It picks a new uuid per object, whose repo
    exists unless ``make_repo`` is off; ``calls`` records what it was asked."""
    calls = {"push": [], "requests": [], "deleted": [], "make_repo": True}
    repos = []

    def remote(object_uuid):
        return {"git_remote_url": f"file://{_repo(git_host, object_uuid)}"}

    def fake_push(self, **kwargs):
        assert "uuid" not in kwargs and kwargs["git_repo"] is True
        object_uuid = str(uuid.uuid4())
        calls["push"].append(object_uuid)
        if calls["make_repo"]:
            repo = _repo(git_host, object_uuid)
            repo.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "-q", "--bare", str(repo)], check=True)
        return {"uuid": object_uuid, "owner_username": "tester", **remote(object_uuid)}

    class FakeCoop:
        def __init__(self, url=None):
            pass

        def get_metadata(self, url_or_uuid):
            return {"uuid": str(url_or_uuid), "owner_username": "tester"}

        def patch(self, url_or_uuid, **kwargs):
            return {"uuid": str(url_or_uuid), **remote(url_or_uuid)}

        def delete(self, url_or_uuid):
            calls["deleted"].append(str(url_or_uuid))
            return {"deleted": True}

        def _send_server_request(self, uri, method, **kwargs):
            calls["requests"].append((method, uri))
            if method == "GET":
                return FakeResponse(body={"objects": repos})
            return FakeResponse(body={"deleted": True})

        def _resolve_server_response(self, response):
            pass

    import edsl.coop as coop_module

    monkeypatch.setattr(Survey, "push", fake_push)
    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    calls["repos"] = repos
    return calls


def _ep(*args):
    result = CliRunner().invoke(cli_module.app, [str(arg) for arg in args])
    return result.exit_code, json.loads(result.output)


def _saved_package(tmp_path: Path) -> Path:
    package_path = tmp_path / "survey.ep"
    Survey.example().git.save(package_path)
    return package_path


def _pushed_package(tmp_path: Path, coop, git_host: Path):
    """A saved and pushed .ep, the uuid Coop gave it, and its repo."""
    package_path = _saved_package(tmp_path)
    code, out = _ep("push", package_path)
    assert code == 0, out
    object_uuid = coop["push"][-1]
    return package_path, object_uuid, _repo(git_host, object_uuid)


def _head(repo: Path) -> str:
    return gitpkg.git(repo, "rev-parse", "HEAD", capture=True).strip()


def test_push_goes_to_coop_then_to_the_repo_coops_uuid_names(tmp_path, coop, git_host):
    package_path = _saved_package(tmp_path)

    code, out = _ep("push", package_path)

    assert code == 0, out
    object_uuid = coop["push"][0]
    repo = _repo(git_host, object_uuid)
    assert out["data"]["coop_info"]["uuid"] == object_uuid
    assert out["data"]["remote_url"] == f"file://{repo}"
    assert _head(repo) == out["data"]["commit"]
    assert gitpkg.read_manifest_file(Survey.git.load(package_path).git.worktree_path)[
        "object_uuid"
    ] == object_uuid


def test_push_reports_a_failed_git_push(tmp_path, coop, git_host):
    coop["make_repo"] = False
    package_path = _saved_package(tmp_path)

    code, out = _ep("push", package_path)

    assert code == cli_module.EXIT_REMOTE
    assert out["error"]["code"] == "GIT_PUSH_ERROR"
    assert out["error"]["details"][0]["coop_info"]["uuid"] == coop["push"][0]


def test_clone_a_remote_url_adds_no_commit(tmp_path, coop, git_host):
    package_path, object_uuid, repo = _pushed_package(tmp_path, coop, git_host)

    code, out = _ep("clone", f"file://{repo}", "--path", tmp_path / "copy.ep")

    assert code == 0, out
    assert out["data"]["operation"] == "git"
    assert out["data"]["commit"] == _head(repo)
    assert out["data"]["remote_url"] == f"file://{repo}"
    assert out["data"]["coop_info"]["uuid"] == object_uuid
    assert Survey.git.load(tmp_path / "copy.ep") == Survey.example()


def test_clone_a_uuid_uses_your_repo(tmp_path, coop, git_host):
    package_path, object_uuid, repo = _pushed_package(tmp_path, coop, git_host)
    coop["repos"].append({"uuid": object_uuid, "remote_url": f"file://{repo}"})

    code, out = _ep("clone", object_uuid, "--path", tmp_path / "copy.ep")

    assert code == 0, out
    assert out["data"]["operation"] == "git"
    assert out["data"]["commit"] == _head(repo)


def test_pull_fast_forwards_from_origin(tmp_path, coop, git_host):
    package_path, object_uuid, repo = _pushed_package(tmp_path, coop, git_host)
    _ep("clone", f"file://{repo}", "--path", tmp_path / "copy.ep")
    survey = Survey.git.load(package_path)
    survey.name = "renamed"
    survey.git.save(message="rename")
    _ep("push", package_path)

    code, out = _ep("pull", tmp_path / "copy.ep")

    assert code == 0, out
    assert out["data"]["operation"] == "updated"
    assert out["data"]["commit"] == _head(repo)


def test_log(tmp_path, coop, git_host):
    package_path, _, _ = _pushed_package(tmp_path, coop, git_host)

    code, out = _ep("log", package_path, "-n", "1", "--oneline")

    assert code == 0, out
    assert len(out["data"]["commits"]) == 1
    assert out["data"]["commits"][0].endswith("Push survey.ep to Expected Parrot")


def test_delete_a_pushed_package_deletes_its_coop_object(tmp_path, coop, git_host):
    package_path, object_uuid, _ = _pushed_package(tmp_path, coop, git_host)

    code, out = _ep("delete", package_path, "--yes")

    assert code == 0, out
    assert coop["deleted"] == [object_uuid]
