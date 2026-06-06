"""Git-backed package persistence for AgentList objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import AgentListError

if TYPE_CHECKING:
    from .agent_list import AgentList


FORMAT_NAME = "edsl.agent_list.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".agent_list.ep"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()


class AgentListGitError(AgentListError):
    """Raised when an underlying git command fails."""

    def __init__(self, command: list[str], stderr: str = "", stdout: str = "") -> None:
        self.command = command
        self.stderr = stderr
        self.stdout = stdout
        details = (stderr or stdout or "").strip()
        message = f"Git command failed: {_display_git_command(command)}"
        if details:
            message = f"{message}\n{details}"
        super().__init__(message)


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)


class AgentListGitNestedRepoWarning(UserWarning):
    """Warning emitted when an AgentList Git package is nested in another Git repo."""


class AgentListGitDescriptor(GitBackedDescriptor):
    """Descriptor exposing Git package operations on AgentList classes/instances."""

    def __init__(self) -> None:
        super().__init__(_git_spec)


class AgentListGitPackage(gitpkg.GitPackage):
    """Package-level helper for a Git-backed AgentList directory."""

    def __init__(self, path: Path) -> None:
        super().__init__(
            path,
            package_suffix=PACKAGE_SUFFIX,
            object_type="AgentList",
            display_name=_package_display_name(Path(path)),
            error_cls=AgentListGitError,
        )

    def validate(self) -> dict:
        errors = _validate_package(self.path)
        return {"status": "ok" if not errors else "invalid", "errors": errors}

    def html(
        self,
        filename: str | Path | None = None,
        *,
        ref: str = "HEAD",
        title: str = "AgentList",
        include_prompts: bool = True,
    ) -> str:
        """Render this package as a standalone interactive HTML document."""
        from .agent_list_html_renderer import AgentListHTMLRenderer

        html = AgentListHTMLRenderer.from_package(self.path, ref=ref).render(
            title=title,
            include_prompts=include_prompts,
        )
        if filename is not None:
            Path(filename).write_text(html, encoding="utf-8")
        return html


def _git_spec() -> GitObjectSpec:
    return GitObjectSpec(
        object_type="AgentList",
        package_suffix=PACKAGE_SUFFIX,
        default_name="agent_list",
        error_cls=AgentListGitError,
        warning_cls=AgentListGitNestedRepoWarning,
        warned_paths=_WARNED_NESTED_PACKAGE_PATHS,
        package_cls=AgentListGitPackage,
        read=_read_agent_list,
        write=_write_agent_list,
        refresh=_refresh_instance_from_loaded,
        accessor_key="_agent_list_git_accessor",
        default_commit_message="Save AgentList",
    )


def _read_agent_list(path: Path, ref: str) -> "AgentList":
    manifest = _load_manifest_at_ref(path, ref)

    from .agent import Agent
    from .agent_list import AgentList

    agents = []
    for agent_id in manifest.get("agent_order", []):
        agent_data = gitpkg.read_json_at_ref(
            path, f"agents/{agent_id}.json", ref, error_cls=AgentListGitError
        )
        agents.append(Agent.from_dict(agent_data))

    agent_list = AgentList(agents)
    if manifest.get("codebook"):
        agent_list.set_codebook(manifest["codebook"])
        agent_list._codebook = manifest["codebook"]
    if manifest.get("instruction") is not None:
        agent_list.set_instruction(manifest["instruction"])
    if manifest.get("traits_presentation_template") is not None:
        agent_list.set_traits_presentation_template(
            manifest["traits_presentation_template"]
        )
        agent_list._traits_presentation_template = manifest[
            "traits_presentation_template"
        ]
    return agent_list


def _write_agent_list(path: Path, agent_list: "AgentList", **_kwargs) -> dict:
    (path / "agents").mkdir(exist_ok=True)
    existing_order, existing_agents = _load_existing_package_state(path)
    agent_ids = _agent_ids_for_agents(agent_list, existing_order, existing_agents)
    _write_manifest(path, agent_list, agent_ids)
    _write_agents(path, agent_list, agent_ids)
    _write_readme(path, agent_list, agent_ids)
    return {}


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = gitpkg.read_json_at_ref(
        path, "manifest.json", ref, error_cls=AgentListGitError
    )
    if manifest.get("format") != FORMAT_NAME:
        raise ValueError(f"Unsupported AgentList git package format: {manifest!r}")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported AgentList git package version: "
            f"{manifest.get('format_version')!r}"
        )
    return manifest


def _refresh_instance_from_loaded(instance: "AgentList", loaded: "AgentList") -> None:
    instance.data = loaded.data
    instance._codebook = loaded._codebook
    instance._traits_presentation_template = loaded._traits_presentation_template


def _load_existing_order(path: Path) -> list[str]:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return []
    return list(manifest.get("agent_order", []))


def _load_existing_package_state(path: Path) -> tuple[list[str], dict[str, dict]]:
    existing_order = _load_existing_order(path)
    existing_agents = {}
    for agent_id in existing_order:
        agent_path = path / "agents" / f"{agent_id}.json"
        if not agent_path.exists():
            continue
        try:
            existing_agents[agent_id] = json.loads(agent_path.read_text())
        except json.JSONDecodeError:
            continue
    return existing_order, existing_agents


def _agent_ids(count: int, existing_order: list[str]) -> list[str]:
    agent_ids = existing_order[:count]
    next_index = 1
    used = set(agent_ids)
    while len(agent_ids) < count:
        candidate = f"{next_index:06d}"
        next_index += 1
        if candidate in used:
            continue
        agent_ids.append(candidate)
        used.add(candidate)
    return agent_ids


def _agent_ids_for_agents(
    agent_list: "AgentList", existing_order: list[str], existing_agents: dict[str, dict]
) -> list[str]:
    used: set[str] = set()
    assigned: list[str] = []
    next_index = _next_agent_index(existing_order)

    for agent in agent_list:
        agent_dict = agent.to_dict(add_edsl_version=False)
        matched_id = None
        for agent_id in existing_order:
            if agent_id in used:
                continue
            if existing_agents.get(agent_id) == agent_dict:
                matched_id = agent_id
                break
        if matched_id is None:
            while True:
                candidate = f"{next_index:06d}"
                next_index += 1
                if candidate not in used and candidate not in existing_agents:
                    matched_id = candidate
                    break
        used.add(matched_id)
        assigned.append(matched_id)

    return assigned


def _next_agent_index(existing_order: list[str]) -> int:
    numeric_ids = [int(agent_id) for agent_id in existing_order if agent_id.isdigit()]
    return max(numeric_ids, default=0) + 1


def _write_manifest(path: Path, agent_list: "AgentList", agent_ids: list[str]) -> None:
    existing_manifest = gitpkg.read_manifest_file(path)
    manifest = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "edsl_class_name": "AgentList",
        "agent_order": agent_ids,
        "n_agents": len(agent_ids),
        "codebook": agent_list._codebook,
        "instruction": _shared_agent_value(agent_list, "instruction"),
        "traits_presentation_template": agent_list._traits_presentation_template,
    }
    existing_remotes = gitpkg.manifest_remotes(existing_manifest)
    if existing_remotes:
        manifest["remotes"] = existing_remotes
    if "primary_remote" in existing_manifest:
        manifest["primary_remote"] = existing_manifest["primary_remote"]
    elif "remote" in existing_manifest and existing_manifest["remote"].get("name"):
        manifest["primary_remote"] = existing_manifest["remote"]["name"]
    try:
        from edsl import __version__

        manifest["edsl_version"] = __version__
    except Exception:
        pass
    gitpkg.write_manifest_dict(path, manifest)


def _write_agents(path: Path, agent_list: "AgentList", agent_ids: list[str]) -> None:
    agents_dir = path / "agents"
    agents_dir.mkdir(exist_ok=True)
    live_files = {f"{agent_id}.json" for agent_id in agent_ids}
    for agent_id, agent in zip(agent_ids, agent_list):
        (agents_dir / f"{agent_id}.json").write_text(
            json.dumps(
                agent.to_dict(add_edsl_version=False),
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    for existing in agents_dir.glob("*.json"):
        if existing.name not in live_files:
            existing.unlink()


def _write_readme(path: Path, agent_list: "AgentList", agent_ids: list[str]) -> None:
    title = _package_display_name(path)
    trait_keys: list[str] = []
    for agent in agent_list:
        for key in agent.traits.keys():
            if key not in trait_keys:
                trait_keys.append(key)
    lines = [
        f"# {title}",
        "",
        "Git-backed EDSL AgentList package.",
        "",
        "## Contents",
        "",
        "- `manifest.json`: package metadata, ordering, and shared AgentList fields.",
        "- `agents/*.json`: one JSON file per agent, ordered by `manifest.json`.",
        "- `.git/`: normal Git repository metadata for history, branches, tags, and remotes.",
        "",
        "## Summary",
        "",
        f"- Agents: {len(agent_ids)}",
        f"- Traits: {len(trait_keys)}",
        f"- Trait keys: {', '.join(trait_keys) if trait_keys else '(none)'}",
        "",
        "## Python",
        "",
        "```python",
        "from edsl import AgentList",
        "",
        f"al = AgentList.git.load({path.name!r})",
        f"html = AgentList.git.open({path.name!r}).html()",
        "```",
        "",
    ]
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _shared_agent_value(agent_list: "AgentList", attr: str):
    if len(agent_list) == 0:
        return None
    first = getattr(agent_list[0], attr, None)
    if first is None:
        return None
    if all(getattr(agent, attr, None) == first for agent in agent_list):
        return first
    return None


def _validate_package(path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    agents_dir = path / "agents"

    if not manifest_path.exists():
        return ["missing manifest.json"]
    if not agents_dir.is_dir():
        errors.append("missing agents directory")

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return [f"invalid manifest.json: {exc.msg}"]

    if manifest.get("format") != FORMAT_NAME:
        errors.append("invalid manifest format")
    if manifest.get("format_version") != FORMAT_VERSION:
        errors.append("invalid manifest format_version")
    if manifest.get("edsl_class_name") != "AgentList":
        errors.append("invalid manifest edsl_class_name")
    if "edsl_version" not in manifest:
        errors.append("missing manifest edsl_version")

    agent_order = manifest.get("agent_order")
    if not isinstance(agent_order, list):
        errors.append("manifest agent_order must be a list")
        agent_order = []

    seen: set[str] = set()
    for agent_id in agent_order:
        if not isinstance(agent_id, str):
            errors.append(f"invalid agent id in manifest: {agent_id!r}")
            continue
        if agent_id in seen:
            errors.append(f"duplicate agent id: {agent_id}")
        seen.add(agent_id)
        agent_path = agents_dir / f"{agent_id}.json"
        if not agent_path.exists():
            errors.append(f"missing agent file: agents/{agent_id}.json")
            continue
        try:
            json.loads(agent_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid agent file agents/{agent_id}.json: {exc.msg}")

    if agents_dir.is_dir():
        expected_files = {f"{agent_id}.json" for agent_id in seen}
        for agent_file in sorted(agents_dir.glob("*.json")):
            if agent_file.name not in expected_files:
                errors.append(f"extra agent file: agents/{agent_file.name}")

    n_agents = manifest.get("n_agents")
    if n_agents is not None and n_agents != len(agent_order):
        errors.append("manifest n_agents does not match agent_order")

    remotes = manifest.get("remotes")
    if remotes is not None:
        if not isinstance(remotes, dict):
            errors.append("manifest remotes must be a dict")
        else:
            for name, metadata in remotes.items():
                if not isinstance(name, str) or not name:
                    errors.append(f"invalid remote name: {name!r}")
                if not isinstance(metadata, dict):
                    errors.append(f"remote metadata for {name!r} must be a dict")
                    continue
                if "remote_url" not in metadata:
                    errors.append(f"remote {name!r} missing remote_url")
                if metadata.get("kind") == "edsl_git_server" and not metadata.get(
                    "server_uuid"
                ):
                    errors.append(f"remote {name!r} missing server_uuid")

    primary_remote = manifest.get("primary_remote")
    if primary_remote is not None:
        if not isinstance(primary_remote, str) or not primary_remote:
            errors.append("manifest primary_remote must be a non-empty string")
        elif isinstance(remotes, dict) and primary_remote not in remotes:
            errors.append("manifest primary_remote is not in remotes")

    return errors
