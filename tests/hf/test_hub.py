"""Hub integration is mocked; live publication requires explicit opt-in."""

import os
import shutil
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

hf = pytest.importorskip("datasets")
hub = pytest.importorskip("huggingface_hub")
from huggingface_hub.errors import EntryNotFoundError, HfHubHTTPError

from edsl import Agent, AgentList, Scenario, ScenarioList
from edsl.hf import HFClassMismatchError, HFSchemaError
from edsl.hf.card import read_card, write_card


@pytest.fixture
def remote(tmp_path, monkeypatch):
    repo = tmp_path / "remote"
    repo.mkdir()
    api = Mock()
    api.create_repo.return_value = "https://huggingface.co/datasets/test/study"
    api.repo_info.return_value = SimpleNamespace(sha="pinned-commit")
    monkeypatch.setattr(hub, "HfApi", Mock(return_value=api))

    def download(repo_id, filename, **kwargs):
        assert kwargs["revision"] == "pinned-commit"
        if not (repo / filename).exists():
            raise EntryNotFoundError("No card")
        return str(repo / filename)

    def upload(**kwargs):
        assert kwargs["parent_commit"] == "pinned-commit"
        for pattern in kwargs["delete_patterns"]:
            for old in repo.glob(pattern):
                old.unlink()
        shutil.copytree(kwargs["folder_path"], repo, dirs_exist_ok=True)

    download_mock = Mock(side_effect=download)
    upload_mock = Mock(side_effect=upload)
    snapshot = Mock(return_value=str(repo))
    monkeypatch.setattr(hub, "hf_hub_download", download_mock)
    monkeypatch.setattr(hub, "upload_folder", upload_mock)
    monkeypatch.setattr(hub, "snapshot_download", snapshot)
    return SimpleNamespace(
        path=repo,
        api=api,
        download=download_mock,
        upload=upload_mock,
        snapshot=snapshot,
    )


def test_upload_download_multiconfig_revision(remote):
    agents = AgentList([Agent({"age": 30}, name="Alice")])
    scenarios = ScenarioList([Scenario({"text": "hello"})])
    url = agents.to_hf(
        "test/study", token="test-token", commit_message="Publish agents"
    )
    assert url == "https://huggingface.co/datasets/test/study"
    remote.api.create_repo.assert_called_once_with(
        "test/study", repo_type="dataset", private=True, exist_ok=True
    )
    assert remote.upload.call_args.kwargs["token"] == "test-token"
    assert remote.upload.call_args.kwargs["commit_message"] == "Publish agents"
    card, _ = read_card(remote.path / "README.md")
    card["license"] = "mit"
    write_card(remote.path / "README.md", card, "\nEdited card.\n")
    scenarios.to_hf("test/study")
    card, prose = read_card(remote.path / "README.md")
    assert set(card["edsl"]["objects"]) == {"agents", "scenarios"}
    assert card["license"] == "mit"
    assert prose == "\nEdited card.\n"
    assert AgentList.from_hf("test/study", revision="v1", token="test-token") == agents
    remote.api.repo_info.assert_called_with(
        "test/study", repo_type="dataset", revision="v1"
    )
    assert remote.snapshot.call_args.kwargs == {
        "repo_type": "dataset",
        "token": "test-token",
        "revision": "pinned-commit",
        "allow_patterns": ["README.md", "agents/*.parquet"],
    }
    assert ScenarioList.from_hf("test/study") == scenarios
    # Replacing one config removes its stale shards and leaves the other alone.
    agents.to_hf("test/study")
    assert ScenarioList.load_hf(remote.path) == scenarios
    assert remote.upload.call_args.kwargs["delete_patterns"] == [
        "agents/train-*-of-*.parquet"
    ]


@pytest.mark.parametrize("cls", [AgentList, ScenarioList])
def test_fallback_non_edsl(cls, remote, monkeypatch):
    loader = Mock(return_value=[{"x": 1, "value": None}, {"x": 2, "value": "text"}])
    monkeypatch.setattr(hf, "load_dataset", loader)
    result = cls.from_hf(
        "test/ordinary", config_name="custom", revision="release", token="test-token"
    )
    loader.assert_called_once_with(
        "test/ordinary",
        name="custom",
        split="train",
        trust_remote_code=False,
        revision="pinned-commit",
        token="test-token",
    )
    assert len(result) == 2
    assert dict(result[0].traits if cls is AgentList else result[0]) == {
        "x": 1,
        "value": None,
    }
    remote.snapshot.assert_not_called()


def test_class_errors_and_source_registration(remote):
    AgentList([Agent({"x": 1})]).save_hf(remote.path)
    with pytest.raises(HFClassMismatchError):
        ScenarioList.from_hf("test/study", config_name="agents")
    with pytest.raises(HFClassMismatchError):
        ScenarioList.from_source("huggingface", "test/study", config_name="agents")
    scenarios = ScenarioList([Scenario({"x": 1})])
    scenarios.save_hf(remote.path)
    assert ScenarioList.from_source("huggingface", "test/study") == scenarios


def test_hub_errors_are_not_swallowed(remote):
    error = HfHubHTTPError("Authentication failed", response=Mock(headers={}))
    remote.api.repo_info.side_effect = error
    with pytest.raises(HfHubHTTPError) as caught:
        ScenarioList.from_hf("test/study")
    assert caught.value is error


def test_bad_export_has_no_remote_side_effects(remote):
    with pytest.raises(HFSchemaError):
        ScenarioList([Scenario({"x": 1}), Scenario({"x": "bad"})]).to_hf("test/study")
    remote.api.create_repo.assert_not_called()
    remote.upload.assert_not_called()


@pytest.mark.skipif(
    os.environ.get("EDSL_HF_LIVE_TEST") != "1", reason="opt-in HF Hub test"
)
def test_live_roundtrip():
    repo = os.environ["EDSL_HF_LIVE_REPO"]
    config = "edsl-test-" + uuid4().hex[:12]
    token = os.environ.get("HF_TOKEN")
    agents = AgentList([Agent({"age": 30}, name="Alice")])
    agents.to_hf(repo, config_name=config, token=token)
    assert AgentList.from_hf(repo, config_name=config, token=token) == agents
