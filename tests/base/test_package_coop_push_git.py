"""``coop_push`` pushes to Coop, records the uuid Coop picked, then pushes the
package's history to the git repo that uuid names."""

import json
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path

import pytest

from edsl import Survey
from edsl.base import git_package as gitpkg
from edsl.base.git_accessor import GitPushError

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="package tests require git"
)


@pytest.fixture
def git_host(tmp_path):
    """Where Coop's file:// repos live, under ``host/tester``."""
    return tmp_path / "host"


def _bare_repo(host: Path, object_uuid: str) -> Path:
    repo = host / "tester" / f"obj-{object_uuid}.git"
    repo.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "--bare", str(repo)], check=True)
    return repo


@pytest.fixture
def coop(monkeypatch, tmp_path):
    """Coop picks a new uuid per object and, for an .ep (``git_repo=True``),
    returns its repo's URL under ``host/tester``, unless ``git_host`` is off.
    The repo exists unless ``make_repo`` is off."""
    state = {"pushed": [], "git_host": True, "make_repo": True}
    host = tmp_path / "host"

    def remote(object_uuid):
        if not state["git_host"]:
            return {}
        return {"git_remote_url": f"file://{host}/tester/obj-{object_uuid}.git"}

    def fake_push(self, **kwargs):
        assert "uuid" not in kwargs and kwargs["git_repo"] is True
        object_uuid = str(uuid.uuid4())
        state["pushed"].append(object_uuid)
        if state["make_repo"]:
            _bare_repo(host, object_uuid)
        return {"uuid": object_uuid, "owner_username": "tester", **remote(object_uuid)}

    class FakeCoop:
        def __init__(self, url=None):
            pass

        def get_metadata(self, url_or_uuid):
            return {"uuid": str(url_or_uuid), "owner_username": "tester"}

        def patch(self, url_or_uuid, **kwargs):
            assert kwargs["git_repo"] is True
            return {"uuid": str(url_or_uuid), **remote(url_or_uuid)}

    import edsl.coop as coop_module

    monkeypatch.setattr(Survey, "push", fake_push)
    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    return state


def _saved_survey(tmp_path: Path):
    survey = Survey.example()
    survey.git.save(tmp_path / "survey.ep")
    return survey


def _manifest(survey) -> dict:
    with zipfile.ZipFile(survey.git.path) as archive:
        return json.loads(archive.read("manifest.json"))


def _log(survey) -> list[str]:
    return gitpkg.git(
        survey.git.worktree_path, "log", "--format=%s", capture=True
    ).splitlines()


def test_coop_push_records_coops_uuid_then_pushes_to_its_repo(tmp_path, coop, git_host):
    survey = _saved_survey(tmp_path)

    result = survey.git.coop_push()

    object_uuid = coop["pushed"][0]
    repo = git_host / "tester" / f"obj-{object_uuid}.git"
    manifest = _manifest(survey)
    assert manifest["object_uuid"] == object_uuid
    assert manifest["remote_url"] == f"file://{repo}"
    assert result["coop_info"]["uuid"] == object_uuid
    assert result["git"]["remote"] == "origin"
    assert gitpkg.git(repo, "rev-parse", "HEAD", capture=True).strip() == result["commit"]
    assert len(_log(survey)) == 2  # the save, then Coop info with the uuid and remote_url

    survey.git.coop_push()
    assert coop["pushed"] == [object_uuid]
    assert len(_log(survey)) == 2


def test_no_git_host_at_coop_pushes_to_coop_only(tmp_path, coop):
    coop["git_host"] = False
    survey = _saved_survey(tmp_path)

    result = survey.git.coop_push()

    assert "git" not in result
    assert survey.git.remotes() == {}
    assert _manifest(survey)["object_uuid"] == coop["pushed"][0]


def test_a_failed_git_push_keeps_the_coop_result(tmp_path, coop, git_host):
    coop["make_repo"] = False
    survey = _saved_survey(tmp_path)

    with pytest.raises(GitPushError) as raised:
        survey.git.coop_push()

    object_uuid = coop["pushed"][0]
    assert raised.value.result["coop_info"]["uuid"] == object_uuid
    assert _manifest(survey)["object_uuid"] == object_uuid

    _bare_repo(git_host, object_uuid)
    assert survey.git.coop_push()["git"]["status"] == "ok"
    assert coop["pushed"] == [object_uuid]
