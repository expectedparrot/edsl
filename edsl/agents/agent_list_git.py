"""Git-backed package persistence for AgentList objects."""

from __future__ import annotations

import json
import atexit
import shutil
import subprocess
import sys
import time
import warnings
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from edsl.base.git_accessor import GitBackedDescriptor, GitObjectSpec
from edsl.base import git_package as gitpkg

from .exceptions import AgentListError

if TYPE_CHECKING:
    from .agent_list import AgentList


FORMAT_NAME = "edsl.agent_list.git_package"
FORMAT_VERSION = 1
PACKAGE_SUFFIX = ".agent_list.ep"
TEMPORARY_PROTOTYPE_REMOTE_NAME = "origin"
_WARNED_NESTED_PACKAGE_PATHS: set[Path] = set()
_TEMPORARY_GIT_SERVER_PROCESS: Optional[subprocess.Popen] = None


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
    return {}


def _ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("AgentList git packages require the git executable.")


def _normalize_package_path(path, for_load: bool = False) -> Path:
    path = Path(path)
    if str(path).endswith(PACKAGE_SUFFIX):
        return path

    if path.suffix:
        raise ValueError(
            f"AgentList git packages must use the {PACKAGE_SUFFIX!r} suffix; "
            f"got {str(path)!r}."
        )

    candidate = path.with_name(path.name + PACKAGE_SUFFIX)
    if for_load and path.exists() and not candidate.exists():
        raise ValueError(
            f"AgentList git packages must use the {PACKAGE_SUFFIX!r} suffix; "
            f"got {str(path)!r}."
        )
    return candidate


def _clone_destination(path) -> Path:
    return _normalize_package_path(path)


def _default_unsaved_package_path() -> Path:
    return _normalize_package_path("agent_list")


def _temporary_git_server_url() -> str:
    from edsl.config import CONFIG

    return CONFIG.get("EDSL_GIT_SERVER_URL").rstrip("/")


def _expected_parrot_api_key() -> Optional[str]:
    from edsl.config import CONFIG

    token = CONFIG.get("EXPECTED_PARROT_API_KEY")
    if not token or token == "None":
        return None
    return token


def _server_objects(
    *,
    token: Optional[str],
    server_url: Optional[str],
    object_type: str,
) -> dict:
    token = token or _expected_parrot_api_key()
    if token is None:
        raise ValueError(
            "Listing git objects requires EXPECTED_PARROT_API_KEY for bearer auth."
        )

    server_url = (server_url or _temporary_git_server_url()).rstrip("/")
    url = f"{server_url}/api/v0/git-repos?object_type={object_type}"
    if _can_autostart_temporary_git_server(url):
        _ensure_temporary_git_server_for_remote(url)
    request = Request(
        url,
        method="GET",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise AgentListGitError(
            ["GET", url], stderr=f"Git object server rejected object listing: {detail}"
        ) from exc
    except URLError as exc:
        raise AgentListGitError(
            ["GET", url],
            stderr=(
                "Could not reach configured git object server. "
                f"EDSL_GIT_SERVER_URL={server_url}. {exc}"
            ),
        ) from exc

    objects = body.get("objects", body.get("repos", []))
    return {
        "status": body.get("status", "ok"),
        "server_url": body.get("server_url", server_url),
        "object_type": object_type,
        "objects": objects,
    }


def _package_display_name(path: Path) -> str:
    name = path.name
    if name.endswith(PACKAGE_SUFFIX):
        return name[: -len(PACKAGE_SUFFIX)]
    return path.stem


def _ensure_temporary_prototype_remote(path: Path, token: Optional[str] = None) -> str:
    """TEMPORARY PROTOTYPE: create a repo on the local Git server and add origin."""
    token = token or _expected_parrot_api_key()
    if token is None:
        raise ValueError(
            "No git remote configured and EXPECTED_PARROT_API_KEY is not set. "
            "Set EXPECTED_PARROT_API_KEY or add a remote explicitly."
        )

    url = f"{_temporary_git_server_url()}/api/v0/git-repos"
    payload = json.dumps(
        {"object_type": "AgentList", "display_name": _package_display_name(path)}
    ).encode()
    request = Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    body = _create_temporary_prototype_repo(request, url)
    remote_url = body["remote_url"]
    _git(path, "remote", "add", TEMPORARY_PROTOTYPE_REMOTE_NAME, remote_url)
    _record_remote_metadata(
        path,
        remote_name=TEMPORARY_PROTOTYPE_REMOTE_NAME,
        remote_url=remote_url,
        server_uuid=body.get("uuid"),
        server_url=_temporary_git_server_url(),
        display_name=body.get("display_name"),
    )
    return TEMPORARY_PROTOTYPE_REMOTE_NAME


def _create_temporary_prototype_repo(request: Request, url: str) -> dict:
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise AgentListGitError(
            ["POST", url], stderr=f"Temporary git server rejected repo creation: {detail}"
        ) from exc
    except URLError as exc:
        if _can_autostart_temporary_git_server(url):
            _autostart_temporary_git_server()
            try:
                with urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode())
            except HTTPError as retry_exc:
                detail = retry_exc.read().decode(errors="replace")
                raise AgentListGitError(
                    ["POST", url],
                    stderr=f"Temporary git server rejected repo creation: {detail}",
                ) from retry_exc
            except URLError as retry_exc:
                exc = retry_exc
        raise AgentListGitError(
            ["POST", url],
            stderr=(
                "Could not reach temporary local git server. "
                f"EDSL_GIT_SERVER_URL={_temporary_git_server_url()}. {exc}"
            ),
        ) from exc


def _can_autostart_temporary_git_server(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


def _ensure_temporary_git_server_for_remote(remote_url: str) -> None:
    if not _can_autostart_temporary_git_server(remote_url):
        return
    parsed = urlparse(remote_url)
    probe_url = f"{parsed.scheme}://{parsed.netloc}/openapi.json"
    try:
        with urlopen(probe_url, timeout=0.2) as response:
            if response.status < 500:
                return
    except Exception:
        pass
    _autostart_temporary_git_server()


def _autostart_temporary_git_server() -> None:
    """TEMPORARY PROTOTYPE: start the local FastAPI git server if it is present."""
    global _TEMPORARY_GIT_SERVER_PROCESS
    if _TEMPORARY_GIT_SERVER_PROCESS is not None:
        if _TEMPORARY_GIT_SERVER_PROCESS.poll() is None:
            _wait_for_temporary_git_server()
            return
        _TEMPORARY_GIT_SERVER_PROCESS = None

    server_dir = _temporary_git_server_directory()
    if server_dir is None:
        return

    parsed = urlparse(_temporary_git_server_url())
    host = parsed.hostname or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    port = str(parsed.port or 8000)
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "local_app:app",
        "--host",
        host,
        "--port",
        port,
        "--log-level",
        "warning",
    ]
    _TEMPORARY_GIT_SERVER_PROCESS = subprocess.Popen(
        command,
        cwd=server_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_temporary_git_server()


def _temporary_git_server_directory() -> Optional[Path]:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "git_server" / "local_app.py"
        if candidate.exists():
            return candidate.parent
    return None


def _wait_for_temporary_git_server() -> None:
    deadline = time.time() + 10
    url = f"{_temporary_git_server_url()}/openapi.json"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.2) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.1)


@atexit.register
def _stop_temporary_git_server() -> None:
    if _TEMPORARY_GIT_SERVER_PROCESS is None:
        return
    if _TEMPORARY_GIT_SERVER_PROCESS.poll() is not None:
        return
    _TEMPORARY_GIT_SERVER_PROCESS.terminate()


def _ensure_remote_metadata(path: Path, remote_name: str) -> None:
    manifest = _read_manifest_file(path)
    remotes = _manifest_remotes(manifest)
    remote_url = _remote_url(path, remote_name)
    existing = remotes.get(remote_name)
    if (
        existing
        and existing.get("remote_url") == remote_url
        and "remotes" in manifest
        and "remote" not in manifest
    ):
        return

    server_uuid = _server_uuid_from_remote_url(remote_url)
    _record_remote_metadata(
        path,
        remote_name=remote_name,
        remote_url=remote_url,
        server_uuid=server_uuid,
        server_url=_server_url_from_remote_url(remote_url),
        display_name=existing.get("display_name") if existing else None,
    )


def _record_remote_metadata(
    path: Path,
    *,
    remote_name: str,
    remote_url: str,
    server_uuid: Optional[str],
    server_url: str,
    display_name: Optional[str],
) -> None:
    if not server_uuid:
        metadata = {
            "kind": "git",
            "remote_url": remote_url,
        }
    else:
        metadata = {
            "kind": "edsl_git_server",
            "server_uuid": server_uuid,
            "server_url": server_url,
            "remote_url": remote_url,
            "object_type": "AgentList",
            "display_name": display_name,
        }
    manifest = _read_manifest_file(path)
    legacy_primary = manifest.get("remote", {}).get("name")
    remotes = _manifest_remotes(manifest)
    remotes[remote_name] = metadata
    manifest["remotes"] = remotes
    if legacy_primary and "primary_remote" not in manifest:
        manifest["primary_remote"] = legacy_primary
    manifest.setdefault("primary_remote", remote_name)
    manifest.pop("remote", None)
    _write_manifest_dict(path, manifest)
    _git(path, "add", "manifest.json")
    if _has_staged_changes(path):
        _git(
            path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            "Record AgentList remote",
        )


def _remove_remote_metadata(path: Path, remote_name: str) -> None:
    manifest = _read_manifest_file(path)
    remotes = _manifest_remotes(manifest)
    if remote_name not in remotes and manifest.get("primary_remote") != remote_name:
        return
    remotes.pop(remote_name, None)
    manifest["remotes"] = remotes
    if manifest.get("primary_remote") == remote_name:
        manifest["primary_remote"] = next(iter(remotes), None)
        if manifest["primary_remote"] is None:
            manifest.pop("primary_remote")
    manifest.pop("remote", None)
    _write_manifest_dict(path, manifest)
    _git(path, "add", "manifest.json")
    if _has_staged_changes(path):
        _git(
            path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            "Remove AgentList remote",
        )


def _remote_display_name(path: Path, remote_name: str) -> Optional[str]:
    metadata = _manifest_remotes(_read_manifest_file(path)).get(remote_name)
    if not metadata:
        return None
    value = metadata.get("display_name")
    return value if isinstance(value, str) else None


def _manifest_remotes(manifest: dict) -> dict:
    remotes = manifest.get("remotes")
    if isinstance(remotes, dict):
        return dict(remotes)

    legacy_remote = manifest.get("remote")
    if isinstance(legacy_remote, dict) and legacy_remote.get("name"):
        name = legacy_remote["name"]
        metadata = {key: value for key, value in legacy_remote.items() if key != "name"}
        if "kind" not in metadata:
            metadata["kind"] = (
                "edsl_git_server" if metadata.get("server_uuid") else "git"
            )
        return {name: metadata}

    return {}


def _server_uuid_from_remote_url(remote_url: str) -> Optional[str]:
    parsed = urlparse(remote_url)
    marker = "/api/v0/git/"
    if marker not in parsed.path:
        return None
    tail = parsed.path.split(marker, 1)[1]
    if not tail.endswith(".git"):
        return None
    return tail[: -len(".git")]


def _server_url_from_remote_url(remote_url: str) -> str:
    parsed = urlparse(remote_url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _init_package(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "agents").mkdir(exist_ok=True)
    if not (path / ".git").exists():
        _git(path, "init", "-b", "main")


def _warn_if_nested_in_outer_repo(path: Path) -> None:
    resolved_path = path.resolve()
    if resolved_path in _WARNED_NESTED_PACKAGE_PATHS:
        return

    outer_repo = _outer_git_repo(path)
    if outer_repo is None:
        return

    _WARNED_NESTED_PACKAGE_PATHS.add(resolved_path)
    warnings.warn(
        "This AgentList package is itself a Git repository and is being saved "
        f"inside another Git repository.\n\nOuter repo: {outer_repo}\n"
        f"Package: {resolved_path}\n\nGit will treat this as an embedded "
        "repository. Usually you should add the package path to the outer "
        "repo's .gitignore or intentionally manage it as a submodule.",
        AgentListGitNestedRepoWarning,
        stacklevel=3,
    )


def _outer_git_repo(path: Path) -> Optional[Path]:
    parent = path.parent if path.parent != Path("") else Path(".")
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    result = subprocess.run(
        ["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    repo = Path(result.stdout.strip()).resolve()
    resolved_path = path.resolve()
    if repo == resolved_path:
        return None
    return repo


def _ensure_package_repo(path: Path) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"No AgentList git package at {path}")
    if not (path / ".git").is_dir():
        raise ValueError(f"{path} is not a Git-backed AgentList package")


def _git(path: Path, *args: str, capture: bool = False) -> str:
    completed = _run_git(["git", "-C", str(path), *args])
    if capture:
        return completed.stdout
    return ""


def _run_git(command: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise AgentListGitError(
            command=command,
            stderr=exc.stderr or "",
            stdout=exc.stdout or "",
        ) from exc


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)


def _remote_url(path: Path, remote: str) -> str:
    return _git(path, "remote", "get-url", remote, capture=True).strip()


def _http_auth_git_args(remote_url: str, token: Optional[str] = None) -> list[str]:
    if not remote_url.startswith(("http://", "https://")):
        return []
    token = token or _expected_parrot_api_key()
    if token is None:
        raise ValueError(
            "HTTP git remote requires EXPECTED_PARROT_API_KEY for bearer auth."
        )
    return ["-c", f"http.extraHeader=Authorization: Bearer {token}"]


def _read_json_at_ref(path: Path, file_path: str, ref: str):
    text = _git(path, "show", f"{ref}:{file_path}", capture=True)
    return json.loads(text)


def _load_manifest_at_ref(path: Path, ref: str) -> dict:
    manifest = _read_json_at_ref(path, "manifest.json", ref)
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
    existing_manifest = _read_manifest_file(path)
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
    existing_remotes = _manifest_remotes(existing_manifest)
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
    _write_manifest_dict(path, manifest)


def _read_manifest_file(path: Path) -> dict:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return {}


def _write_manifest_dict(path: Path, manifest: dict) -> None:
    (path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


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


def _shared_agent_value(agent_list: "AgentList", attr: str):
    if len(agent_list) == 0:
        return None
    first = getattr(agent_list[0], attr, None)
    if first is None:
        return None
    if all(getattr(agent, attr, None) == first for agent in agent_list):
        return first
    return None


def _has_staged_changes(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "diff", "--cached", "--quiet"],
        text=True,
        capture_output=True,
    )
    return result.returncode == 1


def _status_lines(path: Path) -> list[str]:
    text = _git(path, "status", "--porcelain", capture=True)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _ensure_clean(path: Path, operation: str) -> None:
    changed = _status_lines(path)
    if changed:
        raise ValueError(
            f"Cannot {operation}: dirty working tree in {path}. "
            f"Commit or discard changes first: {changed}. "
            "Run <agent_list>.git.status() for details."
        )


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


def _current_branch(path: Path) -> Optional[str]:
    branch = _git(path, "branch", "--show-current", capture=True).strip()
    return branch or None


def _require_current_branch(path: Path) -> str:
    branch = _current_branch(path)
    if branch is None:
        raise ValueError("Cannot push or pull from a detached HEAD.")
    return branch


def _head_commit(path: Path) -> str:
    return _git(path, "rev-parse", "HEAD", capture=True).strip()


def _resolve_commit(path: Path, ref: str) -> str:
    return _git(path, "rev-parse", f"{ref}^{{commit}}", capture=True).strip()


def _upstream_branch(path: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{u}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _upstream_remote(path: Path) -> Optional[str]:
    upstream = _upstream_branch(path)
    if upstream is None or "/" not in upstream:
        return None
    return upstream.split("/", 1)[0]


def _single_remote(path: Path) -> Optional[str]:
    remotes = [
        line.strip()
        for line in _git(path, "remote", capture=True).splitlines()
        if line.strip()
    ]
    if len(remotes) == 1:
        return remotes[0]
    if len(remotes) > 1:
        raise ValueError(
            "Multiple git remotes configured; pass remote=... explicitly."
        )
    return None
