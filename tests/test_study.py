"""Tests for the Study class."""

import base64
import json
import os
import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from edsl.study import Study
from edsl.study.exceptions import (
    StudyAuthError,
    StudyError,
    StudyGitError,
    StudyNotRegisteredError,
    StudyServerError,
)


@pytest.fixture
def tmp_parent(tmp_path):
    """Return a parent directory for study creation."""
    return str(tmp_path)


@pytest.fixture
def study(tmp_parent):
    """Create a Study in a temp directory."""
    return Study(
        "my_study",
        owner="acme",
        project="search",
        topic="rag-v1",
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

    def test_underscores_allowed(self, tmp_parent):
        s = Study("my_study", directory_location=tmp_parent)
        assert s.name == "my_study"

    def test_rejects_uppercase(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("BadName", directory_location=tmp_parent)

    def test_rejects_spaces(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("has space", directory_location=tmp_parent)

    def test_rejects_empty(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("", directory_location=tmp_parent)

    def test_rejects_leading_digit(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("1bad", directory_location=tmp_parent)

    def test_rejects_leading_hyphen(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid name"):
            Study("-leading", directory_location=tmp_parent)


class TestOwnerField:
    def test_allows_dots(self, tmp_parent):
        s = Study("ok", owner="acme.corp", directory_location=tmp_parent)
        assert s.owner == "acme.corp"

    def test_allows_digits_first(self, tmp_parent):
        s = Study("ok", owner="42labs", directory_location=tmp_parent)
        assert s.owner == "42labs"

    def test_rejects_uppercase(self, study):
        with pytest.raises(StudyError, match="Invalid owner"):
            study.owner = "NOT VALID"

    def test_rejects_non_string(self, tmp_parent):
        s = Study("ok", directory_location=tmp_parent)
        with pytest.raises(StudyError, match="must be a string"):
            s.owner = 123


class TestProjectField:
    def test_valid_project(self, tmp_parent):
        s = Study("ok", project="my-project", directory_location=tmp_parent)
        assert s.project == "my-project"

    def test_rejects_dots(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid project"):
            Study("ok", project="bad.project", directory_location=tmp_parent)

    def test_rejects_slashes(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid project"):
            Study("ok", project="bad/project", directory_location=tmp_parent)


class TestTopicField:
    def test_allows_slashes(self, tmp_parent):
        s = Study("ok", topic="rag/v2", directory_location=tmp_parent)
        assert s.topic == "rag/v2"

    def test_allows_dots(self, tmp_parent):
        s = Study("ok", topic="v1.0", directory_location=tmp_parent)
        assert s.topic == "v1.0"

    def test_rejects_uppercase(self, tmp_parent):
        with pytest.raises(StudyError, match="Invalid topic"):
            Study("ok", topic="BAD", directory_location=tmp_parent)


class TestFieldGeneral:
    def test_none_allowed(self, tmp_parent):
        s = Study("ok", directory_location=tmp_parent)
        assert s.owner is None
        assert s.project is None
        assert s.topic is None

    def test_set_later(self, tmp_parent):
        s = Study("ok", directory_location=tmp_parent)
        s.owner = "acme"
        s.project = "search"
        s.topic = "v1"
        assert s.owner == "acme"


# ------------------------------------------------------------------
# Construction & directory initialisation
# ------------------------------------------------------------------


class TestConstruction:
    def test_creates_directory(self, study, tmp_parent):
        assert os.path.isdir(os.path.join(tmp_parent, "my_study"))

    def test_path_is_dir_location_plus_name(self, study, tmp_parent):
        assert study.path == os.path.join(tmp_parent, "my_study")

    def test_git_init(self, study):
        assert os.path.isdir(os.path.join(study.path, ".git"))

    def test_gitignore_contains_metadata(self, study):
        gitignore = os.path.join(study.path, ".gitignore")
        assert os.path.isfile(gitignore)
        with open(gitignore) as f:
            assert ".study.json" in f.read()

    def test_metadata_file_created(self, study):
        assert os.path.isfile(os.path.join(study.path, ".study.json"))

    def test_keypair_generated(self, study):
        assert study._private_key is not None
        assert len(study._public_key_bytes()) == 32

    def test_uuid_initially_none(self, study):
        assert study.uuid is None
        assert study.is_registered is False

    def test_none_directory_uses_tempdir(self):
        s = Study("temptest")
        assert os.path.isdir(s.path)
        assert "temptest" in s.path

    def test_owner_project_topic_optional(self, tmp_parent):
        s = Study("bare", directory_location=tmp_parent)
        assert s.owner is None
        assert s.project is None
        assert s.topic is None
        assert os.path.isdir(s.path)


# ------------------------------------------------------------------
# Metadata round-trip
# ------------------------------------------------------------------


class TestMetadata:
    def test_save_load_roundtrip(self, study, tmp_parent):
        study._uuid = "fake-uuid-1234"
        study._recovery_codes = ["rc_abc", "rc_def"]
        study._save_metadata()

        s2 = Study(
            "my_study",
            directory_location=tmp_parent,
            server_url="https://test.example.com",
        )
        assert s2._uuid == "fake-uuid-1234"
        assert s2._recovery_codes == ["rc_abc", "rc_def"]
        assert s2._private_key is not None
        # Fields loaded from metadata
        assert s2.owner == "acme"
        assert s2.project == "search"
        assert s2.topic == "rag-v1"

    def test_constructor_args_override_metadata(self, study, tmp_parent):
        study._save_metadata()

        s2 = Study(
            "my_study",
            owner="newcorp",
            directory_location=tmp_parent,
        )
        # Constructor arg takes precedence
        assert s2.owner == "newcorp"
        # Others loaded from metadata
        assert s2.project == "search"

    def test_private_key_not_in_to_dict(self, study):
        d = study.to_dict()
        assert "private_key" not in d

    def test_no_secrets_in_to_dict(self, study):
        study._recovery_codes = ["rc_secret"]
        d = study.to_dict()
        assert "recovery_codes" not in d
        assert "private_key" not in d


# ------------------------------------------------------------------
# to_dict / from_dict round-trip
# ------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_fields(self, study):
        d = study.to_dict()
        assert d["name"] == "my_study"
        assert d["owner"] == "acme"
        assert d["project"] == "search"
        assert d["topic"] == "rag-v1"
        assert d["edsl_class_name"] == "Study"
        assert "directory_location" in d

    def test_from_dict_roundtrip(self, study):
        d = study.to_dict()
        s2 = Study.from_dict(d)
        assert s2.name == study.name
        assert s2.owner == study.owner
        assert s2.project == study.project
        assert s2.topic == study.topic

    def test_from_dict_with_none_fields(self, tmp_parent):
        s = Study("bare", directory_location=tmp_parent)
        d = s.to_dict()
        s2 = Study.from_dict(d)
        assert s2.name == "bare"
        assert s2.owner is None


# ------------------------------------------------------------------
# Lazy triple enforcement
# ------------------------------------------------------------------


class TestRequireTriple:
    def test_register_requires_triple(self, tmp_parent):
        s = Study("incomplete", directory_location=tmp_parent)
        with pytest.raises(StudyError, match="owner, project, topic"):
            s.register()

    def test_partial_triple_reports_missing(self, tmp_parent):
        s = Study("incomplete", owner="acme", directory_location=tmp_parent)
        with pytest.raises(StudyError, match="project, topic"):
            s.register()


# ------------------------------------------------------------------
# add_file
# ------------------------------------------------------------------


class TestAddFile:
    def test_add_file_to_root(self, study, tmp_path):
        src = tmp_path / "hello.txt"
        src.write_text("hello world")
        dest = study.add_file(str(src))
        assert os.path.isfile(dest)
        assert dest == os.path.join(study.path, "hello.txt")
        with open(dest) as f:
            assert f.read() == "hello world"

    def test_add_file_to_subdirectory(self, study, tmp_path):
        src = tmp_path / "image.png"
        src.write_bytes(b"\x89PNG")
        dest = study.add_file(str(src), destination_path="assets")
        assert os.path.isfile(dest)
        assert dest == os.path.join(study.path, "assets", "image.png")

    def test_add_file_creates_nested_dirs(self, study, tmp_path):
        src = tmp_path / "data.csv"
        src.write_text("a,b\n1,2")
        dest = study.add_file(str(src), destination_path="data/raw")
        assert os.path.isfile(dest)
        assert "data/raw/data.csv" in dest

    def test_add_file_source_not_found(self, study):
        with pytest.raises(FileNotFoundError):
            study.add_file("/nonexistent/file.txt")

    def test_add_file_rejects_directory(self, study, tmp_path):
        src_dir = tmp_path / "somedir"
        src_dir.mkdir()
        with pytest.raises(StudyError, match="not a directory"):
            study.add_file(str(src_dir))

    def test_add_file_overwrites_existing(self, study, tmp_path):
        src = tmp_path / "test.txt"
        src.write_text("v1")
        study.add_file(str(src))
        src.write_text("v2")
        study.add_file(str(src))
        with open(os.path.join(study.path, "test.txt")) as f:
            assert f.read() == "v2"


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

    def test_uncommitted_staged_file_raises(self, study):
        filepath = os.path.join(study.path, "staged.txt")
        with open(filepath, "w") as f:
            f.write("hello")
        subprocess.run(["git", "add", "staged.txt"], cwd=study.path, check=True)
        with pytest.raises(StudyGitError, match="not clean"):
            study._check_git_clean()


# ------------------------------------------------------------------
# Signing
# ------------------------------------------------------------------


class TestSigning:
    def test_sign_payload_produces_valid_signature(self, study):
        study._uuid = "test-uuid-1234"
        ts, sig_b64 = study._sign_payload("push")

        payload = f"push:test-uuid-1234:{ts}".encode("utf-8")
        padded = sig_b64 + "=" * (-len(sig_b64) % 4)
        sig_bytes = base64.urlsafe_b64decode(padded)

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_key = Ed25519PublicKey.from_public_bytes(study._public_key_bytes())
        pub_key.verify(sig_bytes, payload)

    def test_sign_payload_requires_uuid(self, study):
        with pytest.raises(StudyNotRegisteredError):
            study._sign_payload("push")


# ------------------------------------------------------------------
# Register (mocked HTTP)
# ------------------------------------------------------------------


class TestRegister:
    @patch("edsl.study.study.requests.post")
    def test_register_success(self, mock_post, study):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "uuid": "550e8400-e29b-41d4-a716-446655440000",
            "recovery_codes": ["rc_a", "rc_b", "rc_c", "rc_d", "rc_e"],
        }
        mock_post.return_value = mock_resp

        study.register()

        assert study.uuid == "550e8400-e29b-41d4-a716-446655440000"
        assert study.is_registered is True
        assert len(study._recovery_codes) == 5

        with open(os.path.join(study.path, ".study.json")) as f:
            data = json.load(f)
        assert data["uuid"] == "550e8400-e29b-41d4-a716-446655440000"

    @patch("edsl.study.study.requests.post")
    def test_register_409_adopts_existing(self, mock_post, study):
        # First call is register (409), second is clone-req (200)
        register_resp = MagicMock()
        register_resp.status_code = 409
        register_resp.ok = False

        clone_resp = MagicMock()
        clone_resp.status_code = 200
        clone_resp.ok = True
        clone_resp.json.return_value = {
            "uuid": "adopted-uuid",
            "token": "glpat-adopted",
            "gitlab_url": "https://gitlab.com/bot/adopted-uuid",
            "expires_at": "2026-03-19",
        }
        mock_post.side_effect = [register_resp, clone_resp]

        study.register()

        assert study.uuid == "adopted-uuid"
        assert study._gitlab_url == "https://gitlab.com/bot/adopted-uuid"

    @patch("edsl.study.study.requests.post")
    def test_register_network_error(self, mock_post, study):
        import requests as req
        mock_post.side_effect = req.ConnectionError("Connection refused")

        with pytest.raises(StudyServerError, match="Failed to contact"):
            study.register()


# ------------------------------------------------------------------
# Push (mocked HTTP + git)
# ------------------------------------------------------------------


class TestPush:
    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_push_success(self, mock_clean, mock_git, mock_post, study):
        study._uuid = "test-uuid"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "token": "glpat-xxxx",
            "gitlab_url": "https://gitlab.example.com/bot/test-uuid",
            "expires_at": "2024-03-17T14:30:00Z",
        }
        mock_post.return_value = mock_resp

        study.push()

        mock_clean.assert_called_once()
        mock_git.assert_called_once()
        args = mock_git.call_args
        assert args[0][0] == "push"
        assert "oauth2:glpat-xxxx@" in args[0][1]

    @patch("edsl.study.study.requests.post")
    @patch.object(Study, "_git_run")
    @patch.object(Study, "_check_git_clean")
    def test_push_auto_registers(self, mock_clean, mock_git, mock_post, study):
        # First call is register, second is push-req
        register_resp = MagicMock()
        register_resp.status_code = 201
        register_resp.ok = True
        register_resp.json.return_value = {
            "uuid": "auto-reg-uuid",
            "recovery_codes": ["rc_a"],
        }
        push_resp = MagicMock()
        push_resp.status_code = 200
        push_resp.ok = True
        push_resp.json.return_value = {
            "token": "glpat-auto",
            "gitlab_url": "https://gitlab.com/bot/auto-reg-uuid",
            "expires_at": "2026-03-19",
        }
        mock_post.side_effect = [register_resp, push_resp]

        study.push()

        assert study.uuid == "auto-reg-uuid"
        assert mock_post.call_count == 2


# ------------------------------------------------------------------
# Pull (mocked HTTP + git)
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
            "token": "glpat-yyyy",
            "gitlab_url": "https://gitlab.example.com/bot/test-uuid",
            "expires_at": "2024-03-17T14:30:00Z",
        }
        mock_post.return_value = mock_resp

        study.pull()

        assert mock_git.call_count == 2
        fetch_call = mock_git.call_args_list[0]
        assert fetch_call[0][0] == "fetch"
        assert "oauth2:glpat-yyyy@" in fetch_call[0][1]

        merge_call = mock_git.call_args_list[1]
        assert merge_call[0][0] == "merge"
        assert merge_call[0][1] == "FETCH_HEAD"


# ------------------------------------------------------------------
# Recover (mocked HTTP)
# ------------------------------------------------------------------


class TestRecover:
    @patch("edsl.study.study.requests.post")
    def test_recover_success(self, mock_post, study):
        study._uuid = "test-uuid"
        study._recovery_codes = ["rc_abc", "rc_def"]
        old_pub = study._public_key_bytes()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"uuid": "test-uuid"}
        mock_post.return_value = mock_resp

        study.recover("rc_abc")

        assert study._public_key_bytes() != old_pub
        assert "rc_abc" not in study._recovery_codes
        assert "rc_def" in study._recovery_codes

    @patch("edsl.study.study.requests.post")
    def test_recover_invalid_code(self, mock_post, study):
        study._uuid = "test-uuid"
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.ok = False
        mock_post.return_value = mock_resp

        with pytest.raises(StudyAuthError, match="invalid or already used"):
            study.recover("rc_bad")

    def test_recover_not_registered(self, study):
        with pytest.raises(StudyNotRegisteredError):
            study.recover("rc_any")


# ------------------------------------------------------------------
# Study.from_repo
# ------------------------------------------------------------------


class TestFromRepo:
    def test_wraps_existing_repo(self, tmp_path):
        # Create a real git repo with a file
        repo_dir = tmp_path / "myrepo"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
        (repo_dir / "README.md").write_text("hello")
        subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo_dir), check=True, capture_output=True)

        s = Study.from_repo(
            str(repo_dir),
            owner="acme",
            project="legacy",
            topic="v1",
            server_url="https://test.example.com",
        )

        assert s.name == "myrepo"
        assert s.owner == "acme"
        assert s.project == "legacy"
        assert s.topic == "v1"
        assert s.path == str(repo_dir)
        assert s._private_key is not None
        assert s.uuid is None  # not registered yet
        assert os.path.isfile(os.path.join(str(repo_dir), ".study.json"))

    def test_name_defaults_to_dirname(self, tmp_path):
        repo_dir = tmp_path / "cool-project"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

        s = Study.from_repo(str(repo_dir))
        assert s.name == "cool-project"

    def test_name_override(self, tmp_path):
        repo_dir = tmp_path / "oldname"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

        s = Study.from_repo(str(repo_dir), name="newname")
        assert s.name == "newname"

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

        s = Study.from_repo(str(repo_dir), owner="acme", project="p", topic="t")

        # The original commit should still be there
        result = subprocess.run(
            ["git", "log", "--oneline"], cwd=s.path,
            check=True, capture_output=True, text=True,
        )
        assert "first" in result.stdout

    def test_fields_optional(self, tmp_path):
        repo_dir = tmp_path / "bare"
        repo_dir.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)

        s = Study.from_repo(str(repo_dir))
        assert s.owner is None
        assert s.project is None
        assert s.topic is None


# ------------------------------------------------------------------
# Study.clone (mocked HTTP + git)
# ------------------------------------------------------------------


class TestClone:
    @patch("edsl.study.study.requests.post")
    def test_clone_success(self, mock_post, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "uuid": "clone-uuid-1234",
            "token": "glpat-clone",
            "gitlab_url": "https://gitlab.com/bot/clone-uuid-1234.git",
            "expires_at": "2026-03-19",
        }
        mock_post.return_value = mock_resp

        # Pre-create the directory with a git repo to simulate git clone
        clone_path = tmp_path / "v1"
        clone_path.mkdir()
        subprocess.run(
            ["git", "init"], cwd=str(clone_path),
            check=True, capture_output=True, text=True,
        )

        # Patch subprocess.run only for the clone call (it will be a no-op
        # since we already created the dir)
        real_run = subprocess.run

        def fake_subprocess_run(cmd, **kwargs):
            if cmd[0] == "git" and cmd[1] == "clone":
                # Already created above; skip
                return MagicMock(returncode=0)
            return real_run(cmd, **kwargs)

        with patch("edsl.study.study.subprocess.run", side_effect=fake_subprocess_run):
            s = Study.clone(
                "acme", "search", "v1",
                directory_location=str(tmp_path),
                server_url="https://test.example.com",
            )

        assert s._uuid == "clone-uuid-1234"
        assert s.owner == "acme"
        assert s.project == "search"
        assert s.topic == "v1"
        assert s.path == str(clone_path)
        assert os.path.isfile(os.path.join(str(clone_path), ".study.json"))

        # Verify the clone-req was called with the right body
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["owner"] == "acme"

    @patch("edsl.study.study.requests.post")
    def test_clone_not_found(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.ok = False
        mock_resp.json.return_value = {"error": "not_found"}
        mock_post.return_value = mock_resp

        with pytest.raises(StudyServerError, match="not found"):
            Study.clone("nope", "nah", "no", server_url="https://test.example.com")


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
                    "owner": "acme",
                    "project": "search",
                    "topic": "v1",
                    "created_at": "2026-03-18T00:00:00Z",
                    "provisioned": 1,
                },
                {
                    "uuid": "uuid-2",
                    "owner": "acme",
                    "project": "chat",
                    "topic": "v2",
                    "created_at": "2026-03-17T00:00:00Z",
                    "provisioned": 0,
                },
            ]
        }
        mock_get.return_value = mock_resp

        result = Study.list("acme", server_url="https://test.example.com")

        from edsl.scenarios import ScenarioList
        assert isinstance(result, ScenarioList)
        assert len(result) == 2
        assert result[0]["owner"] == "acme"
        assert result[0]["project"] == "search"
        assert result[1]["provisioned"] is False

    @patch("edsl.study.study.requests.get")
    def test_list_empty(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"repos": []}
        mock_get.return_value = mock_resp

        result = Study.list("nobody", server_url="https://test.example.com")
        assert len(result) == 0


# ------------------------------------------------------------------
# Authed URL construction
# ------------------------------------------------------------------


class TestAuthedUrl:
    def test_injects_token(self):
        url = Study._authed_remote_url(
            "https://gitlab.example.com/bot/uuid-here", "glpat-token123"
        )
        assert "oauth2:glpat-token123@gitlab.example.com" in url
        assert "/bot/uuid-here" in url

    def test_preserves_port(self):
        url = Study._authed_remote_url(
            "https://gitlab.example.com:8443/bot/uuid", "tok"
        )
        assert "oauth2:tok@gitlab.example.com:8443" in url


# ------------------------------------------------------------------
# Other Base methods
# ------------------------------------------------------------------


class TestBaseMethods:
    def test_example(self):
        s = Study.example()
        assert s.name == "example_study"
        assert os.path.isdir(s.path)

    def test_code(self, study):
        code_str = study.code()
        assert "Study(" in code_str
        assert "my_study" in code_str

    def test_eval_repr(self, study):
        r = study._eval_repr_()
        assert "Study(" in r
        assert "my_study" in r

    def test_eval_repr_omits_none(self, tmp_parent):
        s = Study("bare", directory_location=tmp_parent)
        r = s._eval_repr_()
        assert "owner" not in r

    def test_summary_repr(self, study):
        s = study._summary_repr()
        assert "my_study" in s
        assert "acme" in s
