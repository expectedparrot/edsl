"""Tests for the Study class (v2 — bearer token auth, UUID-centric)."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from edsl.study import Study
from edsl.study.client import StudyClient, _get_api_key, _resolve_server_url, authed_remote_url
from edsl.study.exceptions import (
    StudyAuthError,
    StudyError,
    StudyGitError,
    StudyServerError,
)

# All tests mock the API key
API_KEY = "test-api-key-12345"


@pytest.fixture(autouse=True)
def mock_api_key():
    with patch.dict(os.environ, {"EXPECTED_PARROT_API_KEY": API_KEY}):
        yield


@pytest.fixture
def tmp_parent(tmp_path):
    return str(tmp_path)


@pytest.fixture
def study(tmp_parent):
    return Study(
        "my_study",
        directory_location=tmp_parent,
        server_url="https://test.example.com",
    )


# ------------------------------------------------------------------
# client module helpers
# ------------------------------------------------------------------


class TestClientHelpers:
    def test_resolve_server_url_explicit(self):
        assert _resolve_server_url("https://foo.com/") == "https://foo.com"

    def test_resolve_server_url_none_fallback(self):
        url = _resolve_server_url(None)
        assert url.startswith("http")

    def test_get_api_key(self):
        assert _get_api_key() == API_KEY

    def test_get_api_key_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(StudyAuthError):
                _get_api_key()

    def test_authed_remote_url(self):
        url = authed_remote_url(
            "https://gitlab.example.com/bot/uuid-here", "glpat-token123"
        )
        assert "oauth2:glpat-token123@gitlab.example.com" in url

    def test_authed_remote_url_preserves_port(self):
        url = authed_remote_url(
            "https://gitlab.example.com:8443/bot/uuid", "tok"
        )
        assert "oauth2:tok@gitlab.example.com:8443" in url


# ------------------------------------------------------------------
# StudyClient
# ------------------------------------------------------------------


class TestStudyClient:
    def test_headers(self):
        client = StudyClient("https://test.example.com")
        assert client._headers["Authorization"] == f"Bearer {API_KEY}"

    @patch("edsl.study.client.requests.request")
    def test_push_request(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.ok = True
        mock_resp.json.return_value = {"uuid": "u1", "token": "t", "gitlab_url": "g"}
        mock_req.return_value = mock_resp

        client = StudyClient("https://test.example.com")
        data = client.push_request({"uuid": None})
        assert data["uuid"] == "u1"

    @patch("edsl.study.client.requests.request")
    def test_push_request_409(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.ok = False
        mock_req.return_value = mock_resp

        client = StudyClient("https://test.example.com")
        with pytest.raises(StudyServerError, match="Alias already taken"):
            client.push_request({"alias": "taken"})

    @patch("edsl.study.client.requests.request")
    def test_pull_request(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"token": "t", "gitlab_url": "g"}
        mock_req.return_value = mock_resp

        client = StudyClient("https://test.example.com")
        data = client.pull_request("uuid-1")
        assert data["token"] == "t"

    @patch("edsl.study.client.requests.request")
    def test_clone_request_404(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.ok = False
        mock_resp.json.return_value = {"error": "not_found"}
        mock_req.return_value = mock_resp

        client = StudyClient("https://test.example.com")
        with pytest.raises(StudyServerError, match="not found"):
            client.clone_request(uuid="nope")

    @patch("edsl.study.client.requests.request")
    def test_list_repos(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"repos": [{"uuid": "u1"}]}
        mock_req.return_value = mock_resp

        client = StudyClient("https://test.example.com")
        repos = client.list_repos()
        assert len(repos) == 1

    @patch("edsl.study.client.requests.request")
    def test_update_metadata(self, mock_req):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_req.return_value = mock_resp

        client = StudyClient("https://test.example.com")
        client.update_metadata("uuid-1", {"title": "New"})
        mock_req.assert_called_once()


# ------------------------------------------------------------------
# Descriptor validation
# ------------------------------------------------------------------


class TestNameField:
    def test_valid_name(self, tmp_parent):
        s = Study("good-name", directory_location=tmp_parent)
        assert s.name == "good-name"

    def test_default_name(self, tmp_parent):
        s = Study(directory_location=tmp_parent)
        assert s.name == "study"

    def test_rejects_uppercase(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("BadName", directory_location=tmp_parent)

    def test_rejects_empty(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("", directory_location=tmp_parent)


class TestAliasField:
    def test_valid_alias(self, study):
        study.alias = "my-cool-study"
        assert study.alias == "my-cool-study"

    def test_allows_uppercase(self, study):
        study.alias = "MyStudy"
        assert study.alias == "MyStudy"

    def test_rejects_spaces(self, study):
        with pytest.raises(StudyError, match="Invalid alias"):
            study.alias = "has space"

    def test_none_allowed(self, study):
        study.alias = None
        assert study.alias is None


# ------------------------------------------------------------------
# Construction
# ------------------------------------------------------------------


class TestConstruction:
    def test_creates_directory(self, study, tmp_parent):
        assert os.path.isdir(os.path.join(tmp_parent, "my_study"))

    def test_git_init(self, study):
        assert os.path.isdir(os.path.join(study.path, ".git"))

    def test_gitignore_contains_metadata(self, study):
        gitignore = os.path.join(study.path, ".gitignore")
        with open(gitignore) as f:
            assert ".study.json" in f.read()

    def test_metadata_file_created(self, study):
        assert os.path.isfile(os.path.join(study.path, ".study.json"))

    def test_uuid_initially_none(self, study):
        assert study.uuid is None
        assert study.is_pushed is False

    def test_none_directory_uses_tempdir(self):
        s = Study("temptest")
        assert os.path.isdir(s.path)
        assert "temptest" in s.path

    def test_no_cryptography_imports(self, study):
        assert not hasattr(study, "_private_key")


# ------------------------------------------------------------------
# Scaffold
# ------------------------------------------------------------------


class TestScaffold:
    def test_default_scaffold(self, tmp_parent):
        s = Study("scaffolded", directory_location=tmp_parent, scaffold=True)
        p = Path(s.path)
        assert (p / "data" / ".gitkeep").is_file()
        assert (p / "analysis" / ".gitkeep").is_file()
        assert (p / "writeup" / ".gitkeep").is_file()
        assert (p / "writeup" / "plots" / ".gitkeep").is_file()
        assert (p / "writeup" / "tables" / ".gitkeep").is_file()
        assert (p / "writeup" / "report.md").is_file()
        assert "# Report" in (p / "writeup" / "report.md").read_text()
        assert (p / "Makefile").is_file()
        assert ".PHONY" in (p / "Makefile").read_text()

    def test_no_scaffold_by_default(self, tmp_parent):
        s = Study("bare", directory_location=tmp_parent)
        p = Path(s.path)
        assert not (p / "data").exists()
        assert not (p / "Makefile").exists()

    def test_custom_scaffold(self, tmp_parent):
        custom = {
            "src": {"type": "dir"},
            "README.md": {"type": "file", "content": "# Hello\n"},
        }
        s = Study("custom", directory_location=tmp_parent, scaffold=custom)
        p = Path(s.path)
        assert (p / "src" / ".gitkeep").is_file()
        assert (p / "README.md").read_text() == "# Hello\n"
        assert not (p / "data").exists()


# ------------------------------------------------------------------
# Metadata round-trip
# ------------------------------------------------------------------


class TestMetadata:
    def test_save_load_roundtrip(self, study, tmp_parent):
        study._uuid = "fake-uuid"
        study._gitlab_url = "https://gitlab.com/test"
        study.alias = "my-alias"
        study.title = "My Title"
        study.description = "A description"
        study.visibility = "public"
        study._save_metadata()

        s2 = Study("my_study", directory_location=tmp_parent)
        assert s2._uuid == "fake-uuid"
        assert s2._gitlab_url == "https://gitlab.com/test"
        assert s2.alias == "my-alias"
        assert s2.title == "My Title"
        assert s2.description == "A description"
        assert s2.visibility == "public"

    def test_no_secrets_in_to_dict(self, study):
        d = study.to_dict()
        assert "private_key" not in d
        assert "recovery_codes" not in d
        assert "api_key" not in d


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_fields(self, study):
        d = study.to_dict()
        assert d["name"] == "my_study"
        assert d["edsl_class_name"] == "Study"
        assert "uuid" in d

    def test_from_dict_roundtrip(self, study):
        d = study.to_dict()
        s2 = Study.from_dict(d)
        assert s2.name == study.name


# ------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------


class TestAuth:
    def test_client_headers_include_bearer(self):
        client = StudyClient("https://test.example.com")
        h = client._headers
        assert h["Authorization"] == f"Bearer {API_KEY}"

    def test_missing_api_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(StudyAuthError):
                _get_api_key()


# ------------------------------------------------------------------
# add_file
# ------------------------------------------------------------------


class TestAddFile:
    def test_add_file_to_root(self, study, tmp_path):
        src = tmp_path / "hello.txt"
        src.write_text("hello world")
        dest = study.add_file(str(src))
        assert os.path.isfile(dest)

    def test_add_file_to_subdirectory(self, study, tmp_path):
        src = tmp_path / "image.png"
        src.write_bytes(b"\x89PNG")
        dest = study.add_file(str(src), destination_path="assets")
        assert "assets/image.png" in dest

    def test_add_file_rejects_directory(self, study, tmp_path):
        src_dir = tmp_path / "somedir"
        src_dir.mkdir()
        with pytest.raises(StudyError, match="not a directory"):
            study.add_file(str(src_dir))


# ------------------------------------------------------------------
# command()
# ------------------------------------------------------------------


class TestCommand:
    def test_ls(self, study):
        study.command("ls")

    def test_pwd(self, study, capsys):
        study.command("pwd")
        captured = capsys.readouterr()
        assert study.path in captured.out

    def test_git_status(self, study, capsys):
        study.command("git status")
        captured = capsys.readouterr()
        assert "branch" in captured.out.lower() or "On branch" in captured.out

    def test_git_log(self, study, capsys):
        study.command("git log --oneline")
        captured = capsys.readouterr()
        assert "gitignore" in captured.out.lower() or len(captured.out) > 0

    def test_cat(self, study, capsys):
        study.command("cat .gitignore")
        captured = capsys.readouterr()
        assert ".study.json" in captured.out

    def test_failed_command_raises(self, study):
        with pytest.raises(StudyError, match="Command failed"):
            study.command("false")


# ------------------------------------------------------------------
# Git clean check
# ------------------------------------------------------------------


class TestGitClean:
    def test_clean_repo_passes(self, study):
        study._check_git_clean()

    def test_untracked_file_raises(self, study):
        with open(os.path.join(study.path, "untracked.txt"), "w") as f:
            f.write("hello")
        with pytest.raises(StudyGitError, match="not clean"):
            study._check_git_clean()


# ------------------------------------------------------------------
# Push (mocked client)
# ------------------------------------------------------------------


class TestPush:
    @patch.object(StudyClient, "push_request")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_first_push_creates_uuid(self, mock_clean, mock_git, mock_push, study):
        mock_push.return_value = {
            "uuid": "new-uuid-123",
            "token": "glpat-xxxx",
            "gitlab_url": "https://gitlab.com/bot/new-uuid-123",
        }

        study.push()

        assert study.uuid == "new-uuid-123"
        assert study._gitlab_url == "https://gitlab.com/bot/new-uuid-123"
        mock_git.assert_called_once()

    @patch.object(StudyClient, "push_request")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_push_with_metadata(self, mock_clean, mock_git, mock_push, study):
        mock_push.return_value = {
            "uuid": "uuid-1",
            "token": "glpat-xxxx",
            "gitlab_url": "https://gitlab.com/bot/uuid-1",
        }

        study.push(alias="cool-study", title="Cool", description="desc", visibility="public")

        assert study.alias == "cool-study"
        assert study.title == "Cool"
        assert study.visibility == "public"

    @patch.object(StudyClient, "push_request")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_subsequent_push(self, mock_clean, mock_git, mock_push, study):
        study._uuid = "existing-uuid"
        study._gitlab_url = "https://gitlab.com/bot/existing-uuid"

        mock_push.return_value = {
            "uuid": "existing-uuid",
            "token": "glpat-yyyy",
            "gitlab_url": "https://gitlab.com/bot/existing-uuid",
        }

        study.push()

        call_body = mock_push.call_args[0][0]
        assert call_body["uuid"] == "existing-uuid"

    @patch.object(StudyClient, "push_request", side_effect=StudyServerError("Alias already taken."))
    @patch.object(Study, "_check_git_clean")
    def test_push_409_alias_taken(self, mock_clean, mock_push, study):
        with pytest.raises(StudyServerError, match="Alias already taken"):
            study.push(alias="taken")


# ------------------------------------------------------------------
# Pull (mocked client)
# ------------------------------------------------------------------


class TestPull:
    @patch.object(StudyClient, "pull_request")
    @patch.object(Study, "_git_run")
    def test_pull_success(self, mock_git, mock_pull, study):
        study._uuid = "test-uuid"
        mock_pull.return_value = {
            "token": "glpat-read",
            "gitlab_url": "https://gitlab.com/bot/test-uuid",
        }

        study.pull()

        assert mock_git.call_count == 2

    def test_pull_before_push_raises(self, study):
        with pytest.raises(StudyError, match="not been pushed"):
            study.pull()


# ------------------------------------------------------------------
# set_metadata (mocked client)
# ------------------------------------------------------------------


class TestSetMetadata:
    @patch.object(StudyClient, "update_metadata")
    def test_set_metadata(self, mock_update, study):
        study._uuid = "test-uuid"

        study.set_metadata(alias="new-alias", title="New Title")

        assert study.alias == "new-alias"
        assert study.title == "New Title"
        mock_update.assert_called_once_with(
            "test-uuid", {"alias": "new-alias", "title": "New Title"}
        )

    def test_set_metadata_before_push_raises(self, study):
        with pytest.raises(StudyError, match="not been pushed"):
            study.set_metadata(alias="test")

    def test_set_metadata_no_fields_raises(self, study):
        study._uuid = "test-uuid"
        with pytest.raises(StudyError, match="at least one field"):
            study.set_metadata()


# ------------------------------------------------------------------
# Study.clone (mocked client + git)
# ------------------------------------------------------------------


class TestClone:
    @patch.object(StudyClient, "clone_request")
    def test_clone_by_uuid(self, mock_clone_req, tmp_path):
        mock_clone_req.return_value = {
            "uuid": "clone-uuid",
            "token": "glpat-clone",
            "gitlab_url": "https://gitlab.com/bot/clone-uuid.git",
        }

        # Pre-create directory to simulate git clone
        clone_dir = tmp_path / "clone-uuid"
        clone_dir.mkdir(exist_ok=True)
        subprocess.run(["git", "init"], cwd=str(clone_dir), check=True, capture_output=True)

        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "clone":
                return MagicMock(returncode=0)
            return real_run(cmd, **kwargs)

        with patch("edsl.study.study.subprocess.run", side_effect=fake_run):
            s = Study.clone(
                uuid="clone-uuid",
                directory_location=str(tmp_path),
                server_url="https://test.example.com",
            )

        assert s._uuid == "clone-uuid"
        assert os.path.isfile(os.path.join(s.path, ".study.json"))

    @patch.object(StudyClient, "clone_request", side_effect=StudyServerError("Study not found or not yet pushed: not_found"))
    def test_clone_not_found(self, mock_clone_req):
        with pytest.raises(StudyServerError, match="not found"):
            Study.clone(uuid="nope", server_url="https://test.example.com")

    def test_clone_requires_uuid_or_alias(self):
        with pytest.raises(StudyError, match="uuid or alias"):
            Study.clone(server_url="https://test.example.com")


# ------------------------------------------------------------------
# Study.list (mocked client)
# ------------------------------------------------------------------


class TestList:
    @patch.object(StudyClient, "list_repos")
    def test_list_returns_scenario_list(self, mock_list):
        mock_list.return_value = [
            {
                "uuid": "uuid-1",
                "alias": "study-a",
                "title": "Study A",
                "description": "desc",
                "visibility": "private",
                "created_at": "2026-03-18T00:00:00Z",
                "provisioned": 1,
            },
        ]

        result = Study.list(server_url="https://test.example.com")

        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        assert len(result) == 1
        assert result[0]["alias"] == "study-a"

    @patch.object(StudyClient, "list_repos", return_value=[])
    def test_list_empty(self, mock_list):
        result = Study.list(server_url="https://test.example.com")
        assert len(result) == 0


# ------------------------------------------------------------------
# Study.from_repo
# ------------------------------------------------------------------


class TestFromRepo:
    def test_wraps_existing_repo(self, tmp_path):
        repo_dir = tmp_path / "myrepo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
        (repo_dir / "README.md").write_text("hello")
        subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

        s = Study.from_repo(str(repo_dir), server_url="https://test.example.com")

        assert s.name == "myrepo"
        assert s.path == str(repo_dir)
        assert s.uuid is None
        assert os.path.isfile(os.path.join(str(repo_dir), ".study.json"))

    def test_rejects_non_git_dir(self, tmp_path):
        plain_dir = tmp_path / "notgit"
        plain_dir.mkdir()
        with pytest.raises(StudyError, match="Not a git repository"):
            Study.from_repo(str(plain_dir))

    def test_preserves_existing_commits(self, tmp_path):
        repo_dir = tmp_path / "hashistory"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
        (repo_dir / "a.txt").write_text("a")
        subprocess.run(["git", "add", "a.txt"], cwd=str(repo_dir), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "first"], cwd=str(repo_dir), check=True, capture_output=True)

        s = Study.from_repo(str(repo_dir))
        result = subprocess.run(
            ["git", "log", "--oneline"], cwd=s.path,
            check=True, capture_output=True, text=True,
        )
        assert "first" in result.stdout


# ------------------------------------------------------------------
# _new_bare
# ------------------------------------------------------------------


class TestNewBare:
    def test_creates_instance_without_init(self, tmp_path):
        path = tmp_path / "bare_study"
        path.mkdir()
        subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)

        s = Study._new_bare(
            "bare_study", str(path), "https://test.example.com",
            uuid="u1", gitlab_url="https://gitlab.com/u1",
        )

        assert s.name == "bare_study"
        assert s._uuid == "u1"
        assert s._gitlab_url == "https://gitlab.com/u1"
        assert s.alias is None
        assert s.title is None
        assert s.visibility == "private"


# ------------------------------------------------------------------
# Base methods
# ------------------------------------------------------------------


class TestBaseMethods:
    def test_example(self):
        s = Study.example()
        assert s.name == "example_study"
        assert os.path.isdir(s.path)

    def test_code(self, study):
        assert "Study(" in study.code()

    def test_eval_repr(self, study):
        assert "my_study" in study._eval_repr_()

    def test_summary_repr(self, study):
        s = study._summary_repr()
        assert "my_study" in s
