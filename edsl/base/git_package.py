"""Shared Git-backed package mechanics for EDSL objects."""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
import zipfile
from pathlib import Path
from typing import Optional, Type
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from edsl.base.base_exception import BaseException as EDSLBaseException


TEMPORARY_PROTOTYPE_REMOTE_NAME = "origin"
_TEMPORARY_GIT_SERVER_PROCESS: Optional[subprocess.Popen] = None
ARCHIVE_PACKAGE_SUFFIX = ".ep"


class GitPackageError(EDSLBaseException):
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


class GitNestedRepoWarning(UserWarning):
    """Warning emitted when an EDSL Git package is nested in another Git repo."""


class GitPackage:
    """Shared helper for a Git-backed EDSL package directory."""

    def __init__(
        self,
        path: Path,
        *,
        package_suffix: str,
        object_type: str,
        display_name: Optional[str] = None,
        error_cls: Type[Exception] = GitPackageError,
    ) -> None:
        self.package_suffix = package_suffix
        self.object_type = object_type
        self.display_name = display_name
        self.error_cls = error_cls
        raw_path = Path(path)
        if raw_path.is_dir() and (raw_path / ".git").is_dir():
            self.path = raw_path
        else:
            self.path = normalize_package_path(
                raw_path, package_suffix=package_suffix, for_load=True
            )
        self.public_path: Optional[Path] = None
        ensure_git_available()
        ensure_package_repo(self.path)

    def log(self) -> list[dict]:
        text = git(
            self.path,
            "log",
            "--pretty=format:%H%x00%s%x00%ci",
            capture=True,
            error_cls=self.error_cls,
        )
        entries = []
        for line in text.splitlines():
            commit, subject, timestamp = line.split("\x00", 2)
            entries.append(
                {"commit": commit, "message": subject, "timestamp": timestamp}
            )
        return entries

    def history(self) -> list[dict]:
        return self.log()

    def branches(self) -> list[str]:
        text = git(
            self.path,
            "branch",
            "--format=%(refname:short)",
            capture=True,
            error_cls=self.error_cls,
        )
        return [line.strip() for line in text.splitlines() if line.strip()]

    def branch(self, name: str) -> None:
        git(self.path, "branch", name, error_cls=self.error_cls)

    def checkout(self, ref: str) -> None:
        ensure_clean(self.path, "checkout", error_cls=self.error_cls)
        git(self.path, "checkout", ref, error_cls=self.error_cls)

    def switch(self, name: str) -> None:
        ensure_clean(self.path, "switch", error_cls=self.error_cls)
        git(self.path, "switch", name, error_cls=self.error_cls)

    def diff(self, *refs: str) -> str:
        return git(self.path, "diff", *refs, capture=True, error_cls=self.error_cls)

    def tags(self) -> list[str]:
        text = git(self.path, "tag", "--list", capture=True, error_cls=self.error_cls)
        return [line.strip() for line in text.splitlines() if line.strip()]

    def tag(self, name: str, message: Optional[str] = None) -> dict:
        if message is None:
            git(self.path, "tag", name, error_cls=self.error_cls)
        else:
            git(
                self.path,
                "-c",
                "user.name=EDSL",
                "-c",
                "user.email=edsl@example.invalid",
                "tag",
                "-a",
                name,
                "-m",
                message,
                error_cls=self.error_cls,
            )
        return {
            "status": "ok",
            "path": str(self.path),
            "tag": name,
            "commit": git(
                self.path,
                "rev-list",
                "-n",
                "1",
                name,
                capture=True,
                error_cls=self.error_cls,
            ).strip(),
            "message": message,
        }

    def status(self) -> dict:
        changed = status_lines(self.path, error_cls=self.error_cls)
        return {
            "status": "ok",
            "path": str(self.path),
            "branch": current_branch(self.path, error_cls=self.error_cls),
            "commit": head_commit(self.path, error_cls=self.error_cls),
            "clean": len(changed) == 0,
            "changed": changed,
        }

    def remotes(self) -> dict[str, str]:
        text = git(self.path, "remote", "-v", capture=True, error_cls=self.error_cls)
        remotes: dict[str, str] = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] not in remotes:
                remotes[parts[0]] = parts[1]
        return remotes

    def remote_add(self, name: str, url: str) -> dict:
        git(self.path, "remote", "add", name, url, error_cls=self.error_cls)
        record_remote_metadata(
            self.path,
            remote_name=name,
            remote_url=url,
            server_uuid=server_uuid_from_remote_url(url),
            server_url=server_url_from_remote_url(url),
            object_type=self.object_type,
            display_name=None,
            error_cls=self.error_cls,
        )
        return {"status": "ok", "name": name, "url": url}

    def remote_remove(self, name: str) -> dict:
        url = remote_url(self.path, name, error_cls=self.error_cls)
        git(self.path, "remote", "remove", name, error_cls=self.error_cls)
        remove_remote_metadata(self.path, name, error_cls=self.error_cls)
        return {"status": "ok", "name": name, "url": url}

    def remote_set_url(self, name: str, url: str) -> dict:
        git(self.path, "remote", "set-url", name, url, error_cls=self.error_cls)
        record_remote_metadata(
            self.path,
            remote_name=name,
            remote_url=url,
            server_uuid=server_uuid_from_remote_url(url),
            server_url=server_url_from_remote_url(url),
            object_type=self.object_type,
            display_name=remote_display_name(self.path, name),
            error_cls=self.error_cls,
        )
        return {"status": "ok", "name": name, "url": url}

    def fetch(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> dict:
        remote = (
            remote
            or upstream_remote(self.path)
            or single_remote(self.path, error_cls=self.error_cls)
        )
        if remote is None:
            raise ValueError("No git remote configured for this EDSL package.")
        url = remote_url(self.path, remote, error_cls=self.error_cls)
        auth_env = http_auth_git_env(url, token)
        if branch is None:
            git(self.path, "fetch", remote, env=auth_env, error_cls=self.error_cls)
        else:
            git(
                self.path,
                "fetch",
                remote,
                branch,
                env=auth_env,
                error_cls=self.error_cls,
            )
        return {
            "status": "ok",
            "path": str(self.path),
            "remote": remote,
            "branch": branch,
            "message": f"fetched {remote}" + (f" {branch}" if branch else ""),
        }

    def push(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> dict:
        branch = branch or require_current_branch(self.path, error_cls=self.error_cls)
        remote = (
            remote
            or upstream_remote(self.path)
            or single_remote(self.path, error_cls=self.error_cls)
        )
        if remote is None:
            remote = ensure_temporary_prototype_remote(
                self.path,
                object_type=self.object_type,
                display_name=self.display_name,
                token=token,
                error_cls=self.error_cls,
            )
        ensure_remote_metadata(
            self.path, remote, object_type=self.object_type, error_cls=self.error_cls
        )

        url = remote_url(self.path, remote, error_cls=self.error_cls)
        auth_env = http_auth_git_env(url, token)
        if upstream_branch(self.path):
            git(
                self.path,
                "push",
                remote,
                branch,
                env=auth_env,
                error_cls=self.error_cls,
            )
        else:
            git(
                self.path,
                "push",
                "-u",
                remote,
                branch,
                env=auth_env,
                error_cls=self.error_cls,
            )
        update_local_bare_remote_head(url, branch, error_cls=self.error_cls)

        return {
            "status": "ok",
            "path": str(self.path),
            "commit": head_commit(self.path, error_cls=self.error_cls),
            "branch": branch,
            "remote": remote,
            "message": f"pushed {branch} to {remote}",
        }

    def pull(
        self,
        remote: Optional[str] = None,
        branch: Optional[str] = None,
        token: Optional[str] = None,
    ) -> dict:
        ensure_clean(self.path, "pull", error_cls=self.error_cls)
        branch = branch or require_current_branch(self.path, error_cls=self.error_cls)
        remote = (
            remote
            or upstream_remote(self.path)
            or single_remote(self.path, error_cls=self.error_cls)
        )
        if remote is None:
            raise ValueError("No git remote configured for this EDSL package.")

        url = remote_url(self.path, remote, error_cls=self.error_cls)
        auth_env = http_auth_git_env(url, token)
        if upstream_branch(self.path):
            git(self.path, "pull", "--ff-only", env=auth_env, error_cls=self.error_cls)
        else:
            git(
                self.path,
                "pull",
                "--ff-only",
                remote,
                branch,
                env=auth_env,
                error_cls=self.error_cls,
            )

        return {
            "status": "ok",
            "path": str(self.path),
            "commit": head_commit(self.path, error_cls=self.error_cls),
            "branch": current_branch(self.path, error_cls=self.error_cls),
            "remote": remote,
            "message": f"pulled {branch} from {remote}",
        }

    def ignore_in_parent(self) -> dict:
        outer_repo = outer_git_repo(self.path)
        if outer_repo is None:
            raise ValueError("This EDSL package is not inside another Git repo.")

        pattern = (
            self.path.resolve().relative_to(outer_repo).as_posix().rstrip("/") + "/"
        )
        gitignore = outer_repo / ".gitignore"
        existing = gitignore.read_text().splitlines() if gitignore.exists() else []
        if pattern in existing:
            return {
                "status": "unchanged",
                "gitignore": str(gitignore),
                "pattern": pattern,
            }

        with gitignore.open("a") as f:
            if existing and existing[-1] != "":
                f.write("\n")
            f.write(pattern + "\n")
        return {"status": "ok", "gitignore": str(gitignore), "pattern": pattern}


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("EDSL git packages require the git executable.")


def normalize_package_path(
    path, *, package_suffix: str, for_load: bool = False
) -> Path:
    path = Path(path)
    if str(path).endswith(package_suffix):
        return path
    if path.suffix:
        raise ValueError(
            f"EDSL git packages must use the {package_suffix!r} suffix; got {str(path)!r}."
        )
    candidate = path.with_name(path.name + package_suffix)
    if for_load and path.exists() and not candidate.exists():
        raise ValueError(
            f"EDSL git packages must use the {package_suffix!r} suffix; got {str(path)!r}."
        )
    return candidate


def new_package_worktree(public_path: Path) -> Path:
    safe_stem = public_path.name.replace("/", "_")
    return Path(tempfile.mkdtemp(prefix=f"edsl-{safe_stem}-"))


def unpack_package_archive(
    archive_path: Path,
    *,
    package_suffix: str,
    error_cls: Type[Exception] = GitPackageError,
) -> Path:
    archive_path = normalize_package_path(
        archive_path, package_suffix=package_suffix, for_load=True
    )
    if not archive_path.is_file():
        raise FileNotFoundError(f"No EDSL package archive at {archive_path}")
    worktree = new_package_worktree(archive_path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                _validate_archive_member(member.filename)
            archive.extractall(worktree)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{archive_path} is not a valid EDSL package archive") from exc
    ensure_package_repo(worktree)
    return worktree


def pack_package_archive(
    worktree_path: Path,
    archive_path: Path,
    *,
    package_suffix: str,
) -> Path:
    archive_path = normalize_package_path(archive_path, package_suffix=package_suffix)
    ensure_package_repo(worktree_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{archive_path.name}.", suffix=".tmp", dir=str(archive_path.parent)
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(
            temp_path, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for file_path in sorted(p for p in worktree_path.rglob("*") if p.is_file()):
                member_name = file_path.relative_to(worktree_path).as_posix()
                if _exclude_from_package_archive(member_name):
                    continue
                archive.write(
                    file_path,
                    member_name,
                )
        temp_path.replace(archive_path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
    return archive_path


def _exclude_from_package_archive(member_name: str) -> bool:
    if member_name.startswith(".git/hooks/"):
        return True
    return _is_transient_git_pack_file(member_name)


def _is_transient_git_pack_file(member_name: str) -> bool:
    return member_name.startswith(".git/objects/pack/tmp_")


def _validate_archive_member(name: str) -> None:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path in EDSL package archive: {name!r}")


def ensure_package_repo(path: Path) -> None:
    if not path.is_dir():
        raise FileNotFoundError(f"No EDSL git package at {path}")
    if not (path / ".git").is_dir():
        raise ValueError(f"{path} is not a Git-backed EDSL package")


def init_package(path: Path, *, error_cls: Type[Exception] = GitPackageError) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        git(path, "init", "-b", "main", error_cls=error_cls)


def git(
    path: Path,
    *args: str,
    capture: bool = False,
    error_cls: Type[Exception] = GitPackageError,
    env: Optional[dict[str, str]] = None,
) -> str:
    completed = run_git(["git", "-C", str(path), *args], error_cls=error_cls, env=env)
    if capture:
        return completed.stdout
    return ""


def run_git(
    command: list[str],
    *,
    error_cls: Type[Exception] = GitPackageError,
    env: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    auth_config_path = env.get("EDSL_GIT_AUTH_CONFIG") if env else None
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            env={**os.environ, **env} if env else None,
        )
    except subprocess.CalledProcessError as exc:
        raise error_cls(
            command=command, stderr=exc.stderr or "", stdout=exc.stdout or ""
        ) from exc
    finally:
        if auth_config_path:
            try:
                Path(auth_config_path).unlink()
            except FileNotFoundError:
                pass


def _display_git_command(command: list[str]) -> str:
    if len(command) >= 4 and command[0] == "git" and command[1] == "-C":
        return " ".join([command[0], *command[3:]])
    return " ".join(command)


def remote_url(
    path: Path, remote: str, *, error_cls: Type[Exception] = GitPackageError
) -> str:
    return git(
        path, "remote", "get-url", remote, capture=True, error_cls=error_cls
    ).strip()


def http_auth_git_env(url: str, token: Optional[str] = None) -> dict[str, str]:
    if not url.startswith(("http://", "https://")):
        return {}
    token = token or expected_parrot_api_key()
    if token is None:
        raise ValueError(
            "HTTP git remote requires EXPECTED_PARROT_API_KEY for bearer auth."
        )
    fd, path = tempfile.mkstemp(prefix="edsl-git-auth-", suffix=".gitconfig")
    os.chmod(path, 0o600)
    with os.fdopen(fd, "w") as config:
        config.write("[http]\n")
        config.write(f"\textraHeader = Authorization: Bearer {token}\n")
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "include.path",
        "GIT_CONFIG_VALUE_0": path,
        "EDSL_GIT_AUTH_CONFIG": path,
    }


def read_json_at_ref(
    path: Path,
    file_path: str,
    ref: str,
    *,
    error_cls: Type[Exception] = GitPackageError,
):
    text = git(path, "show", f"{ref}:{file_path}", capture=True, error_cls=error_cls)
    return json.loads(text)


def read_manifest_file(path: Path) -> dict:
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text())
    except json.JSONDecodeError:
        return {}


def write_manifest_dict(path: Path, manifest: dict) -> None:
    (path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


def has_staged_changes(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "diff", "--cached", "--quiet"],
        text=True,
        capture_output=True,
    )
    return result.returncode == 1


def status_lines(
    path: Path, *, error_cls: Type[Exception] = GitPackageError
) -> list[str]:
    text = git(path, "status", "--porcelain", capture=True, error_cls=error_cls)
    return [line.strip() for line in text.splitlines() if line.strip()]


def ensure_clean(
    path: Path, operation: str, *, error_cls: Type[Exception] = GitPackageError
) -> None:
    changed = status_lines(path, error_cls=error_cls)
    if changed:
        raise ValueError(
            f"Cannot {operation}: dirty working tree in {path}. Commit or discard changes first: {changed}. "
            "Run <object>.git.status() for details."
        )


def current_branch(
    path: Path, *, error_cls: Type[Exception] = GitPackageError
) -> Optional[str]:
    branch = git(
        path, "branch", "--show-current", capture=True, error_cls=error_cls
    ).strip()
    return branch or None


def require_current_branch(
    path: Path, *, error_cls: Type[Exception] = GitPackageError
) -> str:
    branch = current_branch(path, error_cls=error_cls)
    if branch is None:
        raise ValueError("Cannot push or pull from a detached HEAD.")
    return branch


def head_commit(path: Path, *, error_cls: Type[Exception] = GitPackageError) -> str:
    return git(path, "rev-parse", "HEAD", capture=True, error_cls=error_cls).strip()


def resolve_commit(
    path: Path, ref: str, *, error_cls: Type[Exception] = GitPackageError
) -> str:
    return git(
        path, "rev-parse", f"{ref}^{{commit}}", capture=True, error_cls=error_cls
    ).strip()


def upstream_branch(path: Path) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{u}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def upstream_remote(path: Path) -> Optional[str]:
    upstream = upstream_branch(path)
    if upstream is None or "/" not in upstream:
        return None
    return upstream.split("/", 1)[0]


def single_remote(
    path: Path, *, error_cls: Type[Exception] = GitPackageError
) -> Optional[str]:
    remotes = [
        line.strip()
        for line in git(path, "remote", capture=True, error_cls=error_cls).splitlines()
        if line.strip()
    ]
    if len(remotes) == 1:
        return remotes[0]
    if len(remotes) > 1:
        raise ValueError("Multiple git remotes configured; pass remote=... explicitly.")
    return None


def clone_destination(path, *, package_suffix: str) -> Path:
    return normalize_package_path(path, package_suffix=package_suffix)


def outer_git_repo(path: Path) -> Optional[Path]:
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


def warn_if_nested_in_outer_repo(
    path: Path, *, warned_paths: set[Path], warning_cls: Type[Warning]
) -> None:
    resolved_path = path.resolve()
    if resolved_path in warned_paths:
        return
    outer_repo = outer_git_repo(path)
    if outer_repo is None:
        return
    warned_paths.add(resolved_path)
    warnings.warn(
        "This EDSL package is itself a Git repository and is being saved inside another Git repository.\n\n"
        f"Outer repo: {outer_repo}\nPackage: {resolved_path}\n\n"
        "Git will treat this as an embedded repository. Usually you should add the package path to the outer "
        "repo's .gitignore or intentionally manage it as a submodule.",
        warning_cls,
        stacklevel=3,
    )


def temporary_git_server_url() -> str:
    from edsl.config import CONFIG

    return CONFIG.get("EDSL_GIT_SERVER_URL").rstrip("/")


def expected_parrot_api_key() -> Optional[str]:
    from edsl.config import CONFIG

    token = CONFIG.get("EXPECTED_PARROT_API_KEY")
    if not token or token == "None":
        return None
    return token


def server_objects(
    *,
    token: Optional[str],
    server_url: Optional[str],
    object_type: str,
    error_cls: Type[Exception] = GitPackageError,
) -> dict:
    token = token or expected_parrot_api_key()
    if token is None:
        raise ValueError(
            "Listing git objects requires EXPECTED_PARROT_API_KEY for bearer auth."
        )
    server_url = (server_url or temporary_git_server_url()).rstrip("/")
    url = f"{server_url}/api/v0/git-repos?object_type={object_type}"
    if can_autostart_temporary_git_server(url):
        ensure_temporary_git_server_for_remote(url)
    request = Request(url, method="GET", headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise error_cls(
            ["GET", url], stderr=f"Git object server rejected object listing: {detail}"
        ) from exc
    except URLError as exc:
        raise error_cls(
            ["GET", url],
            stderr=f"Could not reach configured git object server. EDSL_GIT_SERVER_URL={server_url}. {exc}",
        ) from exc
    objects = body.get("objects", body.get("repos", []))
    return {
        "status": body.get("status", "ok"),
        "server_url": body.get("server_url", server_url),
        "object_type": object_type,
        "objects": objects,
    }


def ensure_temporary_prototype_remote(
    path: Path,
    *,
    object_type: str,
    display_name: Optional[str],
    token: Optional[str] = None,
    error_cls: Type[Exception] = GitPackageError,
) -> str:
    token = token or expected_parrot_api_key()
    if token is None:
        raise ValueError(
            "No git remote configured and EXPECTED_PARROT_API_KEY is not set. Set EXPECTED_PARROT_API_KEY or add a remote explicitly."
        )
    url = f"{temporary_git_server_url()}/api/v0/git-repos"
    payload = json.dumps(
        {"object_type": object_type, "display_name": display_name}
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
    body = create_temporary_prototype_repo(request, url, error_cls=error_cls)
    url = body["remote_url"]
    git(
        path, "remote", "add", TEMPORARY_PROTOTYPE_REMOTE_NAME, url, error_cls=error_cls
    )
    record_remote_metadata(
        path,
        remote_name=TEMPORARY_PROTOTYPE_REMOTE_NAME,
        remote_url=url,
        server_uuid=body.get("uuid"),
        server_url=temporary_git_server_url(),
        object_type=object_type,
        display_name=body.get("display_name"),
        error_cls=error_cls,
    )
    return TEMPORARY_PROTOTYPE_REMOTE_NAME


def create_temporary_prototype_repo(
    request: Request, url: str, *, error_cls: Type[Exception] = GitPackageError
) -> dict:
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise error_cls(
            ["POST", url],
            stderr=f"Temporary git server rejected repo creation: {detail}",
        ) from exc
    except URLError as exc:
        if can_autostart_temporary_git_server(url):
            autostart_temporary_git_server()
            try:
                with urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode())
            except HTTPError as retry_exc:
                detail = retry_exc.read().decode(errors="replace")
                raise error_cls(
                    ["POST", url],
                    stderr=f"Temporary git server rejected repo creation: {detail}",
                ) from retry_exc
            except URLError as retry_exc:
                exc = retry_exc
        raise error_cls(
            ["POST", url],
            stderr=f"Could not reach temporary local git server. EDSL_GIT_SERVER_URL={temporary_git_server_url()}. {exc}",
        ) from exc


def can_autostart_temporary_git_server(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


def ensure_temporary_git_server_for_remote(url: str) -> None:
    if not can_autostart_temporary_git_server(url):
        return
    parsed = urlparse(url)
    probe_url = f"{parsed.scheme}://{parsed.netloc}/openapi.json"
    try:
        with urlopen(probe_url, timeout=0.2) as response:
            if response.status < 500:
                return
    except Exception:
        pass
    autostart_temporary_git_server()


def autostart_temporary_git_server() -> None:
    global _TEMPORARY_GIT_SERVER_PROCESS
    if _TEMPORARY_GIT_SERVER_PROCESS is not None:
        if _TEMPORARY_GIT_SERVER_PROCESS.poll() is None:
            wait_for_temporary_git_server()
            return
        _TEMPORARY_GIT_SERVER_PROCESS = None
    server_dir = temporary_git_server_directory()
    if server_dir is None:
        return
    parsed = urlparse(temporary_git_server_url())
    host = parsed.hostname or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    port = str(parsed.port or 8000)
    _TEMPORARY_GIT_SERVER_PROCESS = subprocess.Popen(
        [
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
        ],
        cwd=server_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_temporary_git_server()


def temporary_git_server_directory() -> Optional[Path]:
    from edsl.config import CONFIG

    try:
        configured = CONFIG.get("EDSL_GIT_SERVER_DIR")
    except Exception:
        configured = None
    if configured and configured != "None":
        candidate = Path(configured).expanduser() / "local_app.py"
        if candidate.exists():
            return candidate.parent

    for parent in Path(__file__).resolve().parents:
        candidate = parent / "git_server" / "local_app.py"
        if candidate.exists():
            return candidate.parent
        candidate = parent / "edsl-git-server" / "local_app.py"
        if candidate.exists():
            return candidate.parent
    return None


def wait_for_temporary_git_server() -> None:
    deadline = time.time() + 10
    url = f"{temporary_git_server_url()}/openapi.json"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.2) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.1)


@atexit.register
def stop_temporary_git_server() -> None:
    if _TEMPORARY_GIT_SERVER_PROCESS is None:
        return
    if _TEMPORARY_GIT_SERVER_PROCESS.poll() is not None:
        return
    _TEMPORARY_GIT_SERVER_PROCESS.terminate()


def ensure_remote_metadata(
    path: Path,
    remote_name: str,
    *,
    object_type: str,
    error_cls: Type[Exception] = GitPackageError,
) -> None:
    manifest = read_manifest_file(path)
    remotes = manifest_remotes(manifest)
    url = remote_url(path, remote_name, error_cls=error_cls)
    existing = remotes.get(remote_name)
    if (
        existing
        and existing.get("remote_url") == url
        and "remotes" in manifest
        and "remote" not in manifest
    ):
        return
    record_remote_metadata(
        path,
        remote_name=remote_name,
        remote_url=url,
        server_uuid=server_uuid_from_remote_url(url),
        server_url=server_url_from_remote_url(url),
        object_type=object_type,
        display_name=existing.get("display_name") if existing else None,
        error_cls=error_cls,
    )


def record_remote_metadata(
    path: Path,
    *,
    remote_name: str,
    remote_url: str,
    server_uuid: Optional[str],
    server_url: str,
    object_type: str,
    display_name: Optional[str],
    error_cls: Type[Exception] = GitPackageError,
) -> None:
    if not server_uuid:
        metadata = {"kind": "git", "remote_url": remote_url}
    else:
        metadata = {
            "kind": "edsl_git_server",
            "server_uuid": server_uuid,
            "server_url": server_url,
            "remote_url": remote_url,
            "object_type": object_type,
            "display_name": display_name,
        }
    manifest = read_manifest_file(path)
    legacy_primary = manifest.get("remote", {}).get("name")
    remotes = manifest_remotes(manifest)
    remotes[remote_name] = metadata
    manifest["remotes"] = remotes
    if legacy_primary and "primary_remote" not in manifest:
        manifest["primary_remote"] = legacy_primary
    manifest.setdefault("primary_remote", remote_name)
    manifest.pop("remote", None)
    write_manifest_dict(path, manifest)
    git(path, "add", "manifest.json", error_cls=error_cls)
    if has_staged_changes(path):
        git(
            path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            "Record EDSL remote",
            error_cls=error_cls,
        )


def remove_remote_metadata(
    path: Path, remote_name: str, *, error_cls: Type[Exception] = GitPackageError
) -> None:
    manifest = read_manifest_file(path)
    remotes = manifest_remotes(manifest)
    if remote_name not in remotes and manifest.get("primary_remote") != remote_name:
        return
    remotes.pop(remote_name, None)
    manifest["remotes"] = remotes
    if manifest.get("primary_remote") == remote_name:
        manifest["primary_remote"] = next(iter(remotes), None)
        if manifest["primary_remote"] is None:
            manifest.pop("primary_remote")
    manifest.pop("remote", None)
    write_manifest_dict(path, manifest)
    git(path, "add", "manifest.json", error_cls=error_cls)
    if has_staged_changes(path):
        git(
            path,
            "-c",
            "user.name=EDSL",
            "-c",
            "user.email=edsl@example.invalid",
            "commit",
            "-m",
            "Remove EDSL remote",
            error_cls=error_cls,
        )


def remote_display_name(path: Path, remote_name: str) -> Optional[str]:
    metadata = manifest_remotes(read_manifest_file(path)).get(remote_name)
    if not metadata:
        return None
    value = metadata.get("display_name")
    return value if isinstance(value, str) else None


def manifest_remotes(manifest: dict) -> dict:
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


def server_uuid_from_remote_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    marker = "/api/v0/git/"
    if marker not in parsed.path:
        return None
    tail = parsed.path.split(marker, 1)[1]
    if not tail.endswith(".git"):
        return None
    return tail[: -len(".git")]


def server_url_from_remote_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def update_local_bare_remote_head(
    url: str,
    branch: str,
    *,
    error_cls: Type[Exception] = GitPackageError,
) -> None:
    """Point local bare test remotes at the branch we just pushed."""
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme != "file":
        return
    remote_path = Path(parsed.path if parsed.scheme == "file" else url).expanduser()
    if not remote_path.is_dir():
        return
    result = subprocess.run(
        ["git", "-C", str(remote_path), "config", "--get", "core.bare"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        return
    run_git(
        ["git", "-C", str(remote_path), "symbolic-ref", "HEAD", f"refs/heads/{branch}"],
        error_cls=error_cls,
    )
