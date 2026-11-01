"""ep auth setup-git and the git credential helper it installs."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

import edsl.__main__ as cli_module

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

HOST = "https://git.example.test"


@pytest.fixture
def git_home(tmp_path, monkeypatch):
    """A global git config of its own."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return tmp_path


class FakeResponse:
    def json(self):
        return {"server_url": f"{HOST}/edsl", "objects": []}


@pytest.fixture
def coop(monkeypatch):
    """Coop whose git host is HOST, for a user named alice."""
    profile = {"username": "alice"}

    class FakeCoop:
        api_key = "the-key"

        def get_profile(self):
            return profile

        def _send_server_request(self, uri, method, **kwargs):
            assert (method, uri) == ("GET", "api/v0/git-repos")
            return FakeResponse()

        def _resolve_server_response(self, response):
            pass

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    return profile


def _helpers(host=HOST) -> list[str]:
    result = subprocess.run(
        ["git", "config", "--global", "--get-all", f"credential.{host}.helper"],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines()


def _ep(*args, stdin=None):
    return CliRunner().invoke(cli_module.app, list(args), input=stdin)


def test_setup_git_sets_the_helper_for_coops_git_host(git_home, coop):
    result = _ep("auth", "setup-git")
    _ep("auth", "setup-git")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["host"] == HOST
    helpers = _helpers()
    assert helpers[0] == ""
    assert helpers[1].startswith("!")
    assert helpers[1].endswith(f" auth git-credential --hostname {HOST}")
    assert len(helpers) == 2


def test_setup_git_hostname_and_unset(git_home, coop):
    _ep("auth", "setup-git")
    _ep("auth", "setup-git", "--hostname", "chickgit.example.test")

    other = "https://chickgit.example.test"
    assert _helpers(other)[1].endswith(f"auth git-credential --hostname {other}")

    _ep("auth", "setup-git", "--unset")
    assert _helpers() == []
    assert len(_helpers(other)) == 2


def test_git_credential_answers_only_for_the_git_host(git_home, coop):
    asked = "protocol=https\nhost=git.example.test\npath=edsl/alice/obj-x.git\n\n"

    answer = _ep("auth", "git-credential", "get", "--hostname", HOST, stdin=asked)
    other = _ep(
        "auth", "git-credential", "get", "--hostname", HOST,
        stdin="protocol=https\nhost=github.com\n\n",
    )
    store = _ep("auth", "git-credential", "store", "--hostname", HOST, stdin=asked)

    assert answer.output == "username=alice\npassword=the-key\n"
    assert other.output == ""
    assert store.output == ""


def test_git_credential_without_a_username_sends_the_key_alone(git_home, coop):
    coop["username"] = None

    answer = _ep(
        "auth", "git-credential", "get", "--hostname", HOST,
        stdin="protocol=https\nhost=git.example.test\n\n",
    )

    assert answer.output == "username=the-key\npassword=\n"


def test_git_runs_the_installed_helper(git_home, monkeypatch):
    ep = Path(sys.executable).with_name("ep")
    if not ep.exists():
        pytest.skip("no ep script next to this Python")
    # No server: the username lookup fails fast, so the key goes alone.
    monkeypatch.setenv("EXPECTED_PARROT_API_KEY", "the-key")
    monkeypatch.setenv("EXPECTED_PARROT_URL", "http://localhost:9")
    subprocess.run(
        [str(ep), "auth", "setup-git", "--hostname", HOST], check=True, capture_output=True
    )

    filled = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=git.example.test\n\n",
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )

    assert "username=the-key" in filled.stdout.splitlines()
