"""Tests for the Study class (v2 — bearer token auth, UUID-centric)."""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from edsl.study import Study
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
        # Ensure no Ed25519 key management
        assert not hasattr(study, "_private_key")


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
    def test_headers_include_bearer(self, study):
        h = study._headers
        assert h["Authorization"] == f"Bearer {API_KEY}"

    def test_missing_api_key_raises(self, study):
        with patch.dict(os.environ, {}, clear=True):
            with patch("edsl.study.study.Study._get_api_key", side_effect=StudyAuthError("No API key found.")):
                with pytest.raises(StudyAuthError):
                    study._headers


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
# Push (mocked HTTP)
# ------------------------------------------------------------------


class TestPush:
    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_first_push_creates_uuid(self, mock_clean, mock_git, mock_post, study):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "uuid": "new-uuid-123",
            "token": "glpat-xxxx",
            "gitlab_url": "https://gitlab.com/bot/new-uuid-123",
            "expires_at": "2026-03-19",
        }
        mock_post.return_value = mock_resp

        study.push()

        assert study.uuid == "new-uuid-123"
        assert study._gitlab_url == "https://gitlab.com/bot/new-uuid-123"
        mock_git.assert_called_once()

    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_push_with_metadata(self, mock_clean, mock_git, mock_post, study):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "uuid": "uuid-1",
            "token": "glpat-xxxx",
            "gitlab_url": "https://gitlab.com/bot/uuid-1",
            "expires_at": "2026-03-19",
        }
        mock_post.return_value = mock_resp

        study.push(alias="cool-study", title="Cool", description="desc", visibility="public")

        assert study.alias == "cool-study"
        assert study.title == "Cool"
        assert study.visibility == "public"

    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_subsequent_push(self, mock_clean, mock_git, mock_post, study):
        study._uuid = "existing-uuid"
        study._gitlab_url = "https://gitlab.com/bot/existing-uuid"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "uuid": "existing-uuid",
            "token": "glpat-yyyy",
            "gitlab_url": "https://gitlab.com/bot/existing-uuid",
            "expires_at": "2026-03-19",
        }
        mock_post.return_value = mock_resp

        study.push()

        call_body = mock_post.call_args[1]["json"]
        assert call_body["uuid"] == "existing-uuid"

    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_check_git_clean")
    def test_push_409_alias_taken(self, mock_clean, mock_post, study):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.ok = False
        mock_post.return_value = mock_resp

        with pytest.raises(StudyServerError, match="Alias already taken"):
            study.push(alias="taken")


# ------------------------------------------------------------------
# Pull (mocked HTTP)
# ------------------------------------------------------------------


class TestPull:
    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_git_run")
    def test_pull_success(self, mock_git, mock_post, study):
        study._uuid = "test-uuid"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "token": "glpat-read",
            "gitlab_url": "https://gitlab.com/bot/test-uuid",
            "expires_at": "2026-03-19",
        }
        mock_post.return_value = mock_resp

        study.pull()

        assert mock_git.call_count == 2

    def test_pull_before_push_raises(self, study):
        with pytest.raises(StudyError, match="not been pushed"):
            study.pull()


# ------------------------------------------------------------------
# set_metadata (mocked HTTP)
# ------------------------------------------------------------------


class TestSetMetadata:
    @patch("edsl.study.study.requests.patch")
    def test_set_metadata(self, mock_patch, study):
        study._uuid = "test-uuid"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"uuid": "test-uuid"}
        mock_patch.return_value = mock_resp

        study.set_metadata(alias="new-alias", title="New Title")

        assert study.alias == "new-alias"
        assert study.title == "New Title"

    def test_set_metadata_before_push_raises(self, study):
        with pytest.raises(StudyError, match="not been pushed"):
            study.set_metadata(alias="test")

    def test_set_metadata_no_fields_raises(self, study):
        study._uuid = "test-uuid"
        with pytest.raises(StudyError, match="at least one field"):
            study.set_metadata()


# ------------------------------------------------------------------
# Study.clone (mocked HTTP + git)
# ------------------------------------------------------------------


class TestClone:
    @patch("edsl.study.study.requests.post")
    def test_clone_by_uuid(self, mock_post, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "uuid": "clone-uuid",
            "token": "glpat-clone",
            "gitlab_url": "https://gitlab.com/bot/clone-uuid.git",
            "expires_at": "2026-03-19",
        }
        mock_post.return_value = mock_resp

        # Pre-create directory to simulate git clone
        clone_path = tmp_path / "clone-uuid-1"  # first 12 chars
        clone_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=str(clone_path), check=True, capture_output=True)

        # Mock only the git clone subprocess call
        real_run = subprocess.run

        def fake_run(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "clone":
                return MagicMock(returncode=0)
            return real_run(cmd, **kwargs)

        with patch("edsl.study.study.subprocess.run", side_effect=fake_run):
            # The dir_name will be uuid[:12] = "clone-uuid-1" (first 12 of "clone-uuid")
            # Actually clone-uuid[:12] = "clone-uuid-1" — let me check
            pass

        # Simpler: just mock subprocess globally and create the dir
        clone_dir = tmp_path / "clone-uuid"
        clone_dir.mkdir(exist_ok=True)
        subprocess.run(["git", "init"], cwd=str(clone_dir), check=True, capture_output=True)

        with patch("edsl.study.study.subprocess.run", side_effect=fake_run):
            s = Study.clone(
                uuid="clone-uuid",
                directory_location=str(tmp_path),
                server_url="https://test.example.com",
            )

        assert s._uuid == "clone-uuid"
        assert os.path.isfile(os.path.join(s.path, ".study.json"))

    @patch("edsl.study.study.requests.post")
    def test_clone_not_found(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.ok = False
        mock_resp.json.return_value = {"error": "not_found"}
        mock_post.return_value = mock_resp

        with pytest.raises(StudyServerError, match="not found"):
            Study.clone(uuid="nope", server_url="https://test.example.com")

    def test_clone_requires_uuid_or_alias(self):
        with pytest.raises(StudyError, match="uuid or alias"):
            Study.clone(server_url="https://test.example.com")


# ------------------------------------------------------------------
# Study.list (mocked HTTP)
# ------------------------------------------------------------------


class TestList:
    @patch("edsl.study.study.requests.get")
    def test_list_returns_scenario_list(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "repos": [
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
        }
        mock_get.return_value = mock_resp

        result = Study.list(server_url="https://test.example.com")

        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        assert len(result) == 1
        assert result[0]["alias"] == "study-a"

    @patch("edsl.study.study.requests.get")
    def test_list_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"repos": []}
        mock_get.return_value = mock_resp

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
# Authed URL construction
# ------------------------------------------------------------------


class TestAuthedUrl:
    def test_injects_token(self):
        url = Study._authed_remote_url(
            "https://gitlab.example.com/bot/uuid-here", "glpat-token123"
        )
        assert "oauth2:glpat-token123@gitlab.example.com" in url

    def test_preserves_port(self):
        url = Study._authed_remote_url(
            "https://gitlab.example.com:8443/bot/uuid", "tok"
        )
        assert "oauth2:tok@gitlab.example.com:8443" in url


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
