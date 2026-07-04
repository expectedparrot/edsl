import json
import shutil
import subprocess
import warnings
import zipfile
from pathlib import Path

import pytest

from edsl.agents import Agent, AgentList
from edsl.agents import AgentListGitError as ExportedAgentListGitError
from edsl.agents import AgentListGitNestedRepoWarning
from edsl.agents.exceptions import AgentListError
from edsl.agents.agent_list_git import AgentListGitError
from edsl.base.base_exception import BaseException as EDSLBaseException
from edsl.base import git_package as gitpkg


pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="AgentList git package tests require git"
)


def _local_git_server_path(tmp_path: Path) -> Path:
    candidates = [
        tmp_path.parents[3] / "git_server",
        Path(__file__).resolve().parents[2] / "git_server",
        Path(__file__).resolve().parents[3] / "edsl-git-server",
        Path("/Users/johnhorton/tools/ep/edsl-git-server"),
        Path("/Users/johnhorton/tools/ep/edsl/git_server"),
    ]
    for candidate in candidates:
        if (candidate / "local_app.py").exists():
            return candidate
    pytest.skip("Could not find local EDSL git server checkout.")


def _package_json(package_path: Path, member: str):
    with zipfile.ZipFile(package_path) as archive:
        return json.loads(archive.read(member).decode())


def _package_names(package_path: Path) -> set[str]:
    with zipfile.ZipFile(package_path) as archive:
        return set(archive.namelist())


def test_agent_list_git_error_uses_edsl_exception_hierarchy():
    assert issubclass(AgentListGitError, AgentListError)
    assert issubclass(AgentListGitError, EDSLBaseException)
    assert ExportedAgentListGitError is AgentListGitError
    assert issubclass(AgentListGitNestedRepoWarning, UserWarning)


def test_git_http_auth_env_uses_temp_config_and_cleans_up_token(tmp_path):
    token = "secret-token-for-test"
    env = gitpkg.http_auth_git_env("https://example.com/repo.git", token=token)

    assert env["GIT_CONFIG_KEY_0"] == "include.path"
    assert token not in " ".join(env.values())
    auth_config_path = Path(env["EDSL_GIT_AUTH_CONFIG"])
    assert auth_config_path.is_file()
    assert token in auth_config_path.read_text()

    gitpkg.run_git(["git", "--version"], env=env)

    assert not auth_config_path.exists()


def test_agent_list_git_save_creates_package_layout(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList(
        [
            Agent(name="alice", traits={"age": 22}),
            Agent(name="bob", traits={"age": 30}),
        ],
        codebook={"age": "Age in years"},
    )

    info = agent_list.git.save(package_path, message="initial agents")

    assert info["status"] == "ok"
    assert package_path.is_file()
    names = _package_names(package_path)
    assert ".git/HEAD" in names
    assert "manifest.json" in names
    assert "agents/000001.json" in names
    assert "agents/000002.json" in names

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["format"] == "edsl.agent_list.git_package"
    assert manifest["format_version"] == 1
    assert manifest["edsl_class_name"] == "AgentList"
    assert manifest["agent_order"] == ["000001", "000002"]
    assert manifest["codebook"] == {"age": "Age in years"}
    assert "edsl_version" in manifest

    first_agent = _package_json(package_path, "agents/000001.json")
    assert first_agent["name"] == "alice"
    assert first_agent["traits"] == {"age": 22}


def test_agent_list_git_coop_push_creates_info_then_patches(tmp_path, monkeypatch):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    push_calls = []
    patch_calls = []

    def fake_push(
        self,
        description=None,
        alias=None,
        visibility="private",
        expected_parrot_url=None,
        force=False,
    ):
        push_calls.append(
            {
                "description": description,
                "alias": alias,
                "visibility": visibility,
                "expected_parrot_url": expected_parrot_url,
                "force": force,
            }
        )
        return {
            "object_type": "agent_list",
            "uuid": "00000000-0000-0000-0000-000000000001",
            "url": "https://example.com/content/00000000-0000-0000-0000-000000000001",
            "visibility": visibility,
        }

    class FakeCoop:
        def __init__(self, url=None):
            self.url = url

        def patch(
            self, url_or_uuid, description=None, alias=None, value=None, visibility=None
        ):
            patch_calls.append(
                {
                    "url_or_uuid": url_or_uuid,
                    "description": description,
                    "alias": alias,
                    "value": value,
                    "visibility": visibility,
                }
            )
            return {
                "uuid": url_or_uuid,
                "description": description,
                "visibility": visibility,
            }

        def get_metadata(self, url_or_uuid):
            return {
                "uuid": str(url_or_uuid),
                "url": f"https://example.com/content/{url_or_uuid}",
                "last_updated_ts": "2026-07-03T12:00:00+00:00",
            }

    monkeypatch.setattr(AgentList, "push", fake_push)
    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)

    first = agent_list.git.coop_push(path=package_path, description="first")

    assert first["status"] == "ok"
    assert len(push_calls) == 1
    assert patch_calls == []
    coop_info = _package_json(package_path, "coop_info.json")
    assert coop_info["uuid"] == "00000000-0000-0000-0000-000000000001"

    second = agent_list.git.coop_push(description="updated", visibility="unlisted")

    assert second["status"] == "ok"
    assert len(push_calls) == 1
    assert patch_calls[0]["url_or_uuid"] == "00000000-0000-0000-0000-000000000001"
    assert patch_calls[0]["value"] is agent_list
    coop_info = _package_json(package_path, "coop_info.json")
    assert coop_info["description"] == "updated"
    assert coop_info["visibility"] == "unlisted"


def test_agent_list_git_package_html_shows_coop_info(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    html_path = tmp_path / "agents.html"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")
    agent_list.git._write_coop_info_and_commit(
        {
            "uuid": "agent-list-uuid",
            "url": "https://www.expectedparrot.com/content/agent-list-uuid",
            "alias_url": "https://www.expectedparrot.com/content/alice/shared-agents",
            "alias": "shared-agents",
            "description": "A shared agent list",
            "owner": "alice",
        },
        message="Add Coop info",
    )

    html = AgentList.git.open(package_path).html(
        filename=html_path, include_prompts=False
    )

    assert "Expected Parrot" in html
    assert "Expected Parrot Server" in html
    assert "remote-meta" in html
    assert "copy-mini" in html
    assert "object alias" in html
    assert "owner" in html
    assert "agent-list-uuid" in html
    assert "alice/shared-agents" in html
    assert "alias URL" in html
    assert "https://www.expectedparrot.com/content/alice/shared-agents" in html
    assert "shared-agents" in html
    assert "A shared agent list" in html
    assert "alice" in html
    assert '"href": "https://www.expectedparrot.com/content/agent-list-uuid"' in html
    assert 'target="_blank"' in html
    assert html_path.read_text(encoding="utf-8") == html


def test_agent_list_git_coop_pull_overwrites_package_files(tmp_path, monkeypatch):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")
    agent_list.git._write_coop_info_and_commit(
        {"uuid": "00000000-0000-0000-0000-000000000001"},
        message="store coop info",
    )
    remote = AgentList([Agent(name="bob", traits={"age": 30})])

    class FakeCoop:
        def __init__(self, url=None):
            self.url = url

        def get_metadata(self, url_or_uuid):
            return {
                "uuid": str(url_or_uuid),
                "url": f"https://example.com/content/{url_or_uuid}",
                "last_updated_ts": "2026-07-03T12:00:00+00:00",
            }

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)

    monkeypatch.setattr(
        AgentList,
        "pull",
        classmethod(lambda cls, url_or_uuid, expected_parrot_url=None: remote),
    )

    info = agent_list.git.coop_pull()

    assert info["status"] == "ok"
    assert agent_list == remote
    assert AgentList.git.load(package_path) == remote
    coop_info = _package_json(package_path, "coop_info.json")
    assert coop_info["uuid"] == "00000000-0000-0000-0000-000000000001"


def test_agent_list_git_coop_clone_writes_object_and_coop_info(tmp_path, monkeypatch):
    remote = AgentList([Agent(name="alice", traits={"age": 22})])

    class FakeCoop:
        def __init__(self, url=None):
            self.url = url

        def get_metadata(self, url_or_uuid):
            return {
                "uuid": str(url_or_uuid),
                "url": f"https://example.com/content/{url_or_uuid}",
                "object_type": "agent_list",
            }

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    monkeypatch.setattr(
        AgentList,
        "pull",
        classmethod(lambda cls, url_or_uuid, expected_parrot_url=None: remote),
    )

    cloned = AgentList.git.coop_clone(
        "00000000-0000-0000-0000-000000000001",
        tmp_path / "clone",
    )

    package_path = tmp_path / "clone.ep"
    assert cloned == remote
    assert AgentList.git.load(package_path) == remote
    coop_info = _package_json(package_path, "coop_info.json")
    assert coop_info["uuid"] == "00000000-0000-0000-0000-000000000001"


def test_agent_list_git_load_coop_syncs_when_remote_is_newer(tmp_path, monkeypatch):
    package_path = tmp_path / "agents.agent_list.ep"
    local = AgentList([Agent(name="local", traits={"version": 1})])
    local.git.save(package_path, message="initial agents")
    local.git._write_coop_info_and_commit(
        {
            "uuid": "00000000-0000-0000-0000-000000000001",
            "last_updated_ts": "2026-07-03T12:00:00+00:00",
        },
        message="store coop info",
    )
    remote = AgentList([Agent(name="remote", traits={"version": 2})])

    class FakeCoop:
        def __init__(self, url=None):
            self.url = url

        def get_metadata(self, url_or_uuid):
            return {
                "uuid": str(url_or_uuid),
                "url": f"https://example.com/content/{url_or_uuid}",
                "last_updated_ts": "2026-07-03T12:01:00+00:00",
            }

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    monkeypatch.setattr(
        AgentList,
        "pull",
        classmethod(lambda cls, url_or_uuid, expected_parrot_url=None: remote),
    )

    loaded = AgentList.git.load(package_path)

    assert loaded == remote
    assert (
        _package_json(package_path, "coop_info.json")["last_updated_ts"]
        == "2026-07-03T12:01:00+00:00"
    )


def test_agent_list_git_save_coop_syncs_when_remote_is_newer(tmp_path, monkeypatch):
    package_path = tmp_path / "agents.agent_list.ep"
    local = AgentList([Agent(name="local", traits={"version": 1})])
    local.git.save(package_path, message="initial agents")
    local.git._write_coop_info_and_commit(
        {
            "uuid": "00000000-0000-0000-0000-000000000001",
            "last_updated_ts": "2026-07-03T12:00:00+00:00",
        },
        message="store coop info",
    )
    stale = AgentList([Agent(name="stale", traits={"version": 0})])
    remote = AgentList([Agent(name="remote", traits={"version": 2})])

    class FakeCoop:
        def __init__(self, url=None):
            self.url = url

        def get_metadata(self, url_or_uuid):
            return {
                "uuid": str(url_or_uuid),
                "url": f"https://example.com/content/{url_or_uuid}",
                "last_updated_ts": "2026-07-03T12:01:00+00:00",
            }

    import edsl.coop as coop_module

    monkeypatch.setattr(coop_module, "Coop", FakeCoop)
    monkeypatch.setattr(
        AgentList,
        "pull",
        classmethod(lambda cls, url_or_uuid, expected_parrot_url=None: remote),
    )

    stale.git.save(package_path, message="save after coop sync")

    assert stale == remote
    assert AgentList.git.load(package_path) == remote


def test_agent_list_git_save_warns_once_inside_outer_git_repo(tmp_path):
    outer_repo = tmp_path / "project"
    outer_repo.mkdir()
    subprocess.run(["git", "-C", str(outer_repo), "init"], check=True)
    package_path = outer_repo / "data" / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        agent_list.git.save(package_path, message="initial agents")

    assert len(captured) == 0

    with warnings.catch_warnings(record=True) as second_warnings:
        warnings.simplefilter("always")
        agent_list.git.save(message="no changes")

    assert len(second_warnings) == 0


def test_agent_list_git_ignore_in_parent_updates_outer_gitignore(tmp_path):
    outer_repo = tmp_path / "project"
    outer_repo.mkdir()
    subprocess.run(["git", "-C", str(outer_repo), "init"], check=True)
    package_path = outer_repo / "data" / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    info = agent_list.git.ignore_in_parent()
    second = agent_list.git.ignore_in_parent()

    assert info == {
        "status": "ok",
        "gitignore": str(outer_repo / ".gitignore"),
        "pattern": "data/agents.agent_list.ep",
    }
    assert second["status"] == "unchanged"
    assert (outer_repo / ".gitignore").read_text().splitlines() == [
        "data/agents.agent_list.ep"
    ]


def test_agent_list_git_save_does_not_warn_outside_outer_git_repo(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])

    with warnings.catch_warnings(record=True) as captured_warnings:
        warnings.simplefilter("always")
        agent_list.git.save(package_path, message="initial agents")

    assert len(captured_warnings) == 0


def test_agent_list_git_load_round_trips_and_binds_path(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    original = AgentList(
        [
            Agent(name="alice", traits={"age": 22, "hair": "brown"}),
            Agent(name="bob", traits={"age": 30, "hair": "black"}),
        ]
    )
    original.git.save(package_path, message="initial agents")

    loaded = AgentList.git.load(package_path)

    assert loaded == original
    assert loaded.git.path == package_path


def test_agent_list_git_save_appends_missing_package_suffix(tmp_path):
    package_stem = tmp_path / "agents"
    expected_path = tmp_path / "agents.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])

    info = agent_list.git.save(package_stem, message="initial agents")
    loaded = AgentList.git.load(package_stem)

    assert info["path"] == str(expected_path)
    assert expected_path.is_file()
    assert not package_stem.exists()
    assert loaded == agent_list
    assert loaded.git.path == expected_path


def test_agent_list_git_rejects_non_package_suffix(tmp_path):
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])

    with pytest.raises(ValueError, match=r"\.ep"):
        agent_list.git.save(tmp_path / "agents.json", message="bad suffix")

    with pytest.raises(ValueError, match=r"\.ep"):
        AgentList.git.load(tmp_path / "agents.json")


def test_agent_list_git_loads_historical_commit_without_checkout(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    first = agent_list.git.save(package_path, message="initial agents")

    agent_list = AgentList(
        [
            Agent(name="alice", traits={"age": 23}),
            Agent(name="bob", traits={"age": 30}),
        ]
    )
    second = agent_list.git.save(package_path, message="updated agents")

    old = AgentList.git.load(package_path, ref=first["commit"])
    current = AgentList.git.load(package_path)

    assert old == AgentList([Agent(name="alice", traits={"age": 22})])
    assert current == agent_list
    assert current.git.commit == second["commit"]


def test_agent_list_git_mutation_save_cleans_stale_files_and_round_trips(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList(
        [
            Agent(name="alice", traits={"age": 22}),
            Agent(name="bob", traits={"age": 30}),
        ]
    )
    first = agent_list.git.save(package_path, message="initial agents")

    agent_list.pop(0)
    agent_list.append(Agent(name="carol", traits={"age": 41}))
    second = agent_list.git.save(message="mutated agents")

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["agent_order"] == ["000002", "000003"]
    names = _package_names(package_path)
    assert "agents/000001.json" not in names
    assert "agents/000002.json" in names
    assert "agents/000003.json" in names
    assert AgentList.git.load(package_path) == agent_list
    assert AgentList.git.load(package_path, ref=first["commit"]) == AgentList(
        [
            Agent(name="alice", traits={"age": 22}),
            Agent(name="bob", traits={"age": 30}),
        ]
    )
    assert second["commit"] != first["commit"]


def test_agent_list_git_duplicate_agents_reorder_and_restore_round_trip(tmp_path):
    package_path = tmp_path / "duplicates.agent_list.ep"
    duplicate = Agent(name="same", traits={"age": 22, "city": "Boston"})
    agent_list = AgentList(
        [
            duplicate,
            Agent(name="unique", traits={"age": 30, "city": "Chicago"}),
            duplicate,
        ]
    )
    first = agent_list.git.save(package_path, message="duplicates")

    agent_list.pop(1)
    agent_list.insert(0, Agent(name="new", traits={"age": 41, "city": "Seattle"}))
    second = agent_list.git.save(message="reordered duplicates")

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["agent_order"] == ["000004", "000001", "000003"]
    assert "agents/000002.json" not in _package_names(package_path)
    assert AgentList.git.load(package_path) == agent_list
    assert AgentList.git.load(package_path, ref=first["commit"]) == AgentList(
        [
            duplicate,
            Agent(name="unique", traits={"age": 30, "city": "Chicago"}),
            duplicate,
        ]
    )
    assert second["commit"] != first["commit"]


def test_agent_list_git_branch_checkout_and_commit(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    main_list = AgentList([Agent(name="alice", traits={"age": 22})])
    main_list.git.save(package_path, message="main")

    main_list.git.branch("experiment")
    main_list.git.checkout("experiment")
    experiment_list = AgentList([Agent(name="alice", traits={"age": 99})])
    experiment_list.git.save(package_path, message="experiment")

    assert AgentList.git.load(package_path, ref="experiment") == experiment_list
    assert AgentList.git.load(package_path, ref="main") == main_list
    assert set(experiment_list.git.branches()) == {"experiment", "main"}


def test_agent_list_git_tags_history_switch_and_restore(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    main_list = AgentList([Agent(name="alice", traits={"age": 22})])
    first = main_list.git.save(package_path, message="main")

    tag_info = main_list.git.tag("baseline", message="baseline agents")

    assert tag_info["status"] == "ok"
    assert tag_info["tag"] == "baseline"
    assert tag_info["commit"] == first["commit"]
    assert main_list.git.tags() == ["baseline"]
    assert main_list.git.history() == main_list.git.log()

    main_list.git.branch("experiment")
    main_list.git.switch("experiment")
    experiment_list = AgentList([Agent(name="alice", traits={"age": 99})])
    experiment_list.git.save(package_path, message="experiment")

    restore_info = experiment_list.git.restore("baseline")

    assert restore_info["status"] == "ok"
    assert restore_info["commit"] == first["commit"]
    assert experiment_list == main_list
    assert (
        subprocess.check_output(
            [
                "git",
                "-C",
                str(experiment_list.git.worktree_path),
                "branch",
                "--show-current",
            ],
            text=True,
        ).strip()
        == "experiment"
    )


def test_agent_list_git_save_does_not_create_empty_commit(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    first = agent_list.git.save(package_path, message="initial agents")
    second = agent_list.git.save(message="no changes")

    assert second["status"] == "unchanged"
    assert second["commit"] == first["commit"]

    commit_count = subprocess.check_output(
        ["git", "-C", str(agent_list.git.worktree_path), "rev-list", "--count", "HEAD"],
        text=True,
    ).strip()
    assert commit_count == "1"


def test_agent_list_git_push_and_pull_with_remote(tmp_path):
    remote_path = tmp_path / "remote.git"
    first_path = tmp_path / "first.agent_list.ep"
    second_path = tmp_path / "second.agent_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    first = AgentList([Agent(name="alice", traits={"age": 22})])
    first.git.save(first_path, message="initial agents")
    first.git.remote_add("origin", str(remote_path))

    push_info = first.git.push()

    assert push_info["status"] == "ok"
    assert push_info["remote"] == "origin"
    assert push_info["branch"] == "main"

    second = AgentList.git.clone(str(remote_path), path=second_path)
    assert second == first

    updated = AgentList(
        [
            Agent(name="alice", traits={"age": 23}),
            Agent(name="bob", traits={"age": 30}),
        ]
    )
    updated.git.save(first_path, message="updated agents")
    updated.git.push()

    pull_info = second.git.pull()

    assert pull_info["status"] == "ok"
    assert second == updated
    assert second.git.commit == updated.git.commit


def test_agent_list_git_clone_requires_destination_path(tmp_path):
    remote_path = tmp_path / "test.agent_list.ep.git"
    source_path = tmp_path / "source.agent_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    original = AgentList([Agent(name="alice", traits={"age": 22})])
    original.git.save(source_path, message="initial agents")
    original.git.remote_add("origin", str(remote_path))
    original.git.push()

    with pytest.raises(TypeError):
        AgentList.git.clone(str(remote_path))


def test_agent_list_git_clone_accepts_explicit_destination_without_suffix(tmp_path):
    remote_path = tmp_path / "remote.git"
    source_path = tmp_path / "source.agent_list.ep"
    destination_stem = tmp_path / "cloned"
    expected_destination = tmp_path / "cloned.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    original = AgentList([Agent(name="alice", traits={"age": 22})])
    original.git.save(source_path, message="initial agents")
    original.git.remote_add("origin", str(remote_path))
    original.git.push()

    cloned = AgentList.git.clone(str(remote_path), path=destination_stem)

    assert cloned == original
    assert cloned.git.path == expected_destination


def test_agent_list_git_clone_rejects_existing_destination(tmp_path):
    remote_path = tmp_path / "remote.git"
    destination = tmp_path / "cloned.agent_list.ep"
    destination.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)

    with pytest.raises(AgentListGitError, match="Destination path already exists"):
        AgentList.git.clone(str(remote_path), path=destination)


def test_agent_list_git_wraps_git_failures(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    with pytest.raises(AgentListGitError) as exc_info:
        agent_list.git.checkout("missing-branch")

    assert "git checkout missing-branch" in str(exc_info.value)
    assert "missing-branch" in str(exc_info.value)


def test_agent_list_git_status_reports_clean_and_dirty(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    clean = agent_list.git.status()
    assert clean["clean"] is True
    assert clean["branch"] == "main"
    assert clean["changed"] == []

    (agent_list.git.worktree_path / "agents" / "000001.json").write_text("{}\n")

    dirty = agent_list.git.status()
    assert dirty["clean"] is False
    assert dirty["changed"] == ["M agents/000001.json"]


def test_agent_list_git_remote_helpers(tmp_path):
    remote_path = tmp_path / "remote.git"
    package_path = tmp_path / "agents.agent_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    info = agent_list.git.remote_add("origin", str(remote_path))

    assert info == {"status": "ok", "name": "origin", "url": str(remote_path)}
    assert agent_list.git.remotes() == {"origin": str(remote_path)}
    manifest = _package_json(package_path, "manifest.json")
    assert manifest["primary_remote"] == "origin"
    assert manifest["remotes"] == {
        "origin": {"kind": "git", "remote_url": str(remote_path)}
    }


def test_agent_list_git_supports_multiple_remotes_and_push_to_named_remote(tmp_path):
    origin_path = tmp_path / "origin.git"
    github_path = tmp_path / "github.git"
    package_path = tmp_path / "agents.agent_list.ep"
    subprocess.run(["git", "init", "--bare", str(origin_path)], check=True)
    subprocess.run(["git", "init", "--bare", str(github_path)], check=True)
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    agent_list.git.remote_add("origin", str(origin_path))
    agent_list.git.remote_add("github", str(github_path))
    push_info = agent_list.git.push(remote="github")

    assert push_info["remote"] == "github"
    assert agent_list.git.remotes() == {
        "github": str(github_path),
        "origin": str(origin_path),
    }
    manifest = _package_json(package_path, "manifest.json")
    assert manifest["primary_remote"] == "origin"
    assert manifest["remotes"]["origin"] == {
        "kind": "git",
        "remote_url": str(origin_path),
    }
    assert manifest["remotes"]["github"] == {
        "kind": "git",
        "remote_url": str(github_path),
    }

    cloned = tmp_path / "github-clone"
    subprocess.run(["git", "clone", str(github_path), str(cloned)], check=True)
    assert (cloned / "manifest.json").is_file()


def test_agent_list_git_remote_set_url_remove_and_fetch(tmp_path):
    remote_path = tmp_path / "remote.git"
    replacement_path = tmp_path / "replacement.git"
    package_path = tmp_path / "agents.agent_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)
    subprocess.run(["git", "init", "--bare", str(replacement_path)], check=True)
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    agent_list.git.remote_add("origin", str(remote_path))
    fetch_info = agent_list.git.fetch(remote="origin")

    assert fetch_info["status"] == "ok"
    assert fetch_info["remote"] == "origin"

    set_info = agent_list.git.remote_set_url("origin", str(replacement_path))

    assert set_info == {"status": "ok", "name": "origin", "url": str(replacement_path)}
    assert agent_list.git.remotes() == {"origin": str(replacement_path)}
    manifest = _package_json(package_path, "manifest.json")
    assert manifest["remotes"]["origin"] == {
        "kind": "git",
        "remote_url": str(replacement_path),
    }

    remove_info = agent_list.git.remote_remove("origin")

    assert remove_info == {
        "status": "ok",
        "name": "origin",
        "url": str(replacement_path),
    }
    assert agent_list.git.remotes() == {}
    manifest = _package_json(package_path, "manifest.json")
    assert manifest["remotes"] == {}
    assert "primary_remote" not in manifest


def test_agent_list_git_pull_and_checkout_refuse_dirty_tree(tmp_path):
    remote_path = tmp_path / "remote.git"
    package_path = tmp_path / "agents.agent_list.ep"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True)
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")
    agent_list.git.remote_add("origin", str(remote_path))
    agent_list.git.push()
    agent_list.git.branch("experiment")

    (agent_list.git.worktree_path / "agents" / "000001.json").write_text("{}\n")

    with pytest.raises(ValueError, match="Run .*\\.git\\.status\\(\\)"):
        agent_list.git.checkout("experiment")
    with pytest.raises(ValueError, match="Run .*\\.git\\.status\\(\\)"):
        agent_list.git.pull()


def test_agent_list_git_save_refuses_dirty_tree_before_writing(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")
    (agent_list.git.worktree_path / "agents" / "000001.json").write_text("{}\n")

    with pytest.raises(ValueError, match="Run .*\\.git\\.status\\(\\)"):
        agent_list.git.save(message="dirty save")


def test_agent_list_git_validate_reports_package_integrity(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
    agent_list.git.save(package_path, message="initial agents")

    assert agent_list.git.validate() == {"status": "ok", "errors": []}

    (agent_list.git.worktree_path / "agents" / "000001.json").unlink()
    invalid = agent_list.git.validate()

    assert invalid["status"] == "invalid"
    assert "missing agent file: agents/000001.json" in invalid["errors"]


def test_agent_list_git_preserves_agent_file_ids_on_insert(tmp_path):
    package_path = tmp_path / "agents.agent_list.ep"
    alice = Agent(name="alice", traits={"age": 22})
    bob = Agent(name="bob", traits={"age": 30})
    agent_list = AgentList([alice, bob])
    agent_list.git.save(package_path, message="initial agents")

    alice_file = _package_json(package_path, "agents/000001.json")
    bob_file = _package_json(package_path, "agents/000002.json")

    cara = Agent(name="cara", traits={"age": 40})
    AgentList([cara, alice, bob]).git.save(package_path, message="insert cara")

    manifest = _package_json(package_path, "manifest.json")
    assert manifest["agent_order"] == ["000003", "000001", "000002"]
    assert _package_json(package_path, "agents/000001.json") == alice_file
    assert _package_json(package_path, "agents/000002.json") == bob_file
    assert _package_json(package_path, "agents/000003.json")["name"] == "cara"


def test_agent_list_git_push_auto_creates_temporary_local_server_remote(
    tmp_path, monkeypatch
):
    import socket
    import sys
    import threading
    import time

    import httpx
    import uvicorn

    git_server_path = _local_git_server_path(tmp_path)
    sys.path.insert(0, str(git_server_path))
    try:
        from local_app import create_app
    finally:
        sys.path.remove(str(git_server_path))

    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'server.db'}",
        storage_root=tmp_path / "repos",
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/openapi.json", timeout=0.2).status_code == 200:
                break
        except Exception:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("local git server did not start")

    from edsl.config import CONFIG

    monkeypatch.setattr(CONFIG, "EDSL_GIT_SERVER_URL", base_url, raising=False)
    monkeypatch.setattr(CONFIG, "EXPECTED_PARROT_API_KEY", "alice-token", raising=False)

    try:
        package_path = tmp_path / "agents.ep"
        agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
        agent_list.git.save(package_path, message="initial agents")

        push_info = agent_list.git.push()

        assert push_info["status"] == "ok"
        remotes = agent_list.git.remotes()
        assert set(remotes) == {"origin"}
        assert remotes["origin"].startswith(f"{base_url}/api/v0/git/")
        manifest = _package_json(package_path, "manifest.json")
        assert manifest["primary_remote"] == "origin"
        assert manifest["remotes"]["origin"]["server_uuid"] in remotes["origin"]
        assert manifest["remotes"]["origin"]["remote_url"] == remotes["origin"]
        assert manifest["remotes"]["origin"]["display_name"] == "agents"

        cloned = AgentList.git.clone(remotes["origin"], path=tmp_path / "clone")
        assert cloned == agent_list
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_agent_list_git_push_unsaved_agent_list_auto_saves_and_pushes(
    tmp_path, monkeypatch
):
    import socket
    import sys
    import threading
    import time

    import httpx
    import uvicorn

    git_server_path = _local_git_server_path(tmp_path)
    sys.path.insert(0, str(git_server_path))
    try:
        from local_app import create_app
    finally:
        sys.path.remove(str(git_server_path))

    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'server.db'}",
        storage_root=tmp_path / "repos",
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/openapi.json", timeout=0.2).status_code == 200:
                break
        except Exception:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("local git server did not start")

    from edsl.config import CONFIG

    monkeypatch.setattr(CONFIG, "EDSL_GIT_SERVER_URL", base_url, raising=False)
    monkeypatch.setattr(CONFIG, "EXPECTED_PARROT_API_KEY", "alice-token", raising=False)
    monkeypatch.setattr(
        CONFIG,
        "EDSL_GIT_SERVER_DIR",
        str(_local_git_server_path(tmp_path)),
        raising=False,
    )
    monkeypatch.chdir(tmp_path)

    try:
        agent_list = AgentList.example()
        push_info = agent_list.git.push()

        assert push_info["status"] == "ok"
        assert push_info["path"] == "agent_list.ep"
        assert agent_list.git.path == Path("agent_list.ep")
        manifest_path = tmp_path / "agent_list.ep"
        assert manifest_path.is_file()
        assert set(agent_list.git.remotes()) == {"origin"}
        manifest = _package_json(manifest_path, "manifest.json")
        assert (
            manifest["remotes"]["origin"]["server_uuid"]
            in agent_list.git.remotes()["origin"]
        )
        assert manifest["remotes"]["origin"]["display_name"] == "agent_list"

        cloned = AgentList.git.clone(
            agent_list.git.remotes()["origin"], path=tmp_path / "clone"
        )
        assert cloned == agent_list
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_agent_list_git_push_autostarts_temporary_local_server(tmp_path, monkeypatch):
    import socket

    from edsl.base import git_package as gitpkg
    from edsl.config import CONFIG

    if gitpkg.temporary_git_server_directory() is None:
        pytest.skip("Could not find local EDSL git server checkout.")

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base_url = f"http://127.0.0.1:{port}"

    monkeypatch.setattr(CONFIG, "EDSL_GIT_SERVER_URL", base_url, raising=False)
    monkeypatch.setattr(CONFIG, "EXPECTED_PARROT_API_KEY", "alice-token", raising=False)
    monkeypatch.setenv("LOCAL_GIT_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("LOCAL_GIT_STORAGE_ROOT", str(tmp_path / "repos"))
    monkeypatch.chdir(tmp_path)

    try:
        agent_list = AgentList.example()
        push_info = agent_list.git.push()

        assert push_info["status"] == "ok"
        assert push_info["remote"] == "origin"
        remote_url = agent_list.git.remotes()["origin"]
        assert remote_url.startswith(f"{base_url}/api/v0/git/")
        manifest = _package_json(tmp_path / "agent_list.ep", "manifest.json")
        assert manifest["remotes"]["origin"]["server_uuid"] in remote_url
        assert manifest["remotes"]["origin"]["remote_url"] == remote_url
    finally:
        process = gitpkg._TEMPORARY_GIT_SERVER_PROCESS
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        gitpkg._TEMPORARY_GIT_SERVER_PROCESS = None


def test_agent_list_git_objects_lists_canonical_server_objects(tmp_path, monkeypatch):
    import socket
    import sys
    import threading
    import time

    import httpx
    import uvicorn

    git_server_path = _local_git_server_path(tmp_path)
    sys.path.insert(0, str(git_server_path))
    try:
        from local_app import create_app
    finally:
        sys.path.remove(str(git_server_path))

    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'server.db'}",
        storage_root=tmp_path / "repos",
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            if httpx.get(f"{base_url}/openapi.json", timeout=0.2).status_code == 200:
                break
        except Exception:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("local git server did not start")

    from edsl.config import CONFIG

    monkeypatch.setattr(CONFIG, "EDSL_GIT_SERVER_URL", base_url, raising=False)
    monkeypatch.setattr(CONFIG, "EXPECTED_PARROT_API_KEY", "alice-token", raising=False)

    try:
        package_path = tmp_path / "agents.ep"
        agent_list = AgentList([Agent(name="alice", traits={"age": 22})])
        agent_list.git.save(package_path, message="initial agents")
        agent_list.git.push()

        listing = AgentList.git.objects()

        assert listing["status"] == "ok"
        assert listing["server_url"] == base_url
        assert listing["object_type"] == "AgentList"
        assert len(listing["objects"]) == 1
        obj = listing["objects"][0]
        assert obj["object_type"] == "AgentList"
        assert obj["display_name"] == "agents"
        assert obj["remote_url"] == agent_list.git.remotes()["origin"]
        assert obj["created_at"]
    finally:
        server.should_exit = True
        thread.join(timeout=5)
