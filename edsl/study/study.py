"""Study class — a git-backed EDSL object with remote sync via a meta-server."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests

from edsl.base.base_class import Base
from edsl.study.descriptors import NameField, AliasField
from edsl.study.exceptions import (
    StudyAuthError,
    StudyError,
    StudyGitError,
    StudyServerError,
)

_DEFAULT_SERVER_URL = "https://study.expectedparrot.com"
_METADATA_FILE = ".study.json"


def _log(verbose: bool, msg: str):
    if verbose:
        print(msg)


class Study(Base):
    """A git-backed study directory that syncs with a remote meta-server.

    A Study wraps a local directory under git version control. It can push to
    and pull from GitLab via a meta-server, authenticated by an API key
    (``EXPECTED_PARROT_API_KEY``).

    Only ``name`` is required at construction (defaults to ``"study"``).
    Metadata like ``alias``, ``title``, ``description``, and ``visibility``
    can be set at push time or updated later.
    """

    name = NameField()
    alias = AliasField()

    def __init__(
        self,
        name: str = "study",
        *,
        directory_location: str | None = None,
        server_url: str | None = None,
    ):
        self.name = name
        self.alias = None
        self.title = None
        self.description = None
        self.visibility = "private"

        # Resolve path
        if directory_location is None:
            directory_location = tempfile.mkdtemp(prefix=f"edsl_study_{name}_")
        self._directory_location = str(Path(directory_location).resolve())
        self.path = os.path.join(self._directory_location, name)

        # Resolve server URL
        if server_url is not None:
            self.server_url = server_url.rstrip("/")
        else:
            self.server_url = self._default_server_url()

        # Internal state loaded from .study.json
        self._uuid: str | None = None
        self._gitlab_url: str | None = None

        self._init_directory()

    # ------------------------------------------------------------------
    # Directory / git initialisation
    # ------------------------------------------------------------------

    def _init_directory(self):
        metadata_path = os.path.join(self.path, _METADATA_FILE)

        if not os.path.isdir(self.path):
            os.makedirs(self.path, exist_ok=True)
            self._git_run("init")
            self._write_gitignore()
            self._save_metadata()
        elif os.path.isfile(metadata_path):
            self._load_metadata()
        else:
            if not os.path.isdir(os.path.join(self.path, ".git")):
                self._git_run("init")
            self._write_gitignore()
            self._save_metadata()

    def _write_gitignore(self):
        gitignore_path = os.path.join(self.path, ".gitignore")
        lines: list[str] = []
        if os.path.isfile(gitignore_path):
            with open(gitignore_path) as f:
                lines = f.read().splitlines()
        if _METADATA_FILE not in lines:
            lines.append(_METADATA_FILE)
            with open(gitignore_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            try:
                self._git_run("add", ".gitignore")
                self._git_run("commit", "-m", "Initial .gitignore")
            except StudyGitError:
                pass

    # ------------------------------------------------------------------
    # Metadata persistence (.study.json)
    # ------------------------------------------------------------------

    def _save_metadata(self):
        data = {
            "uuid": self._uuid,
            "gitlab_url": self._gitlab_url,
            "alias": self.alias,
            "title": self.title,
            "description": self.description,
            "visibility": self.visibility,
            "server_url": self.server_url,
        }
        metadata_path = os.path.join(self.path, _METADATA_FILE)
        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_metadata(self):
        metadata_path = os.path.join(self.path, _METADATA_FILE)
        with open(metadata_path) as f:
            data = json.load(f)

        self._uuid = data.get("uuid")
        self._gitlab_url = data.get("gitlab_url")
        self.alias = data.get("alias")
        self.title = data.get("title")
        self.description = data.get("description")
        self.visibility = data.get("visibility", "private")
        self.server_url = data.get("server_url", self.server_url)

    # ------------------------------------------------------------------
    # Auth (Coop pattern)
    # ------------------------------------------------------------------

    @property
    def _headers(self) -> dict:
        """Build authorization headers using the Expected Parrot API key."""
        api_key = self._get_api_key()
        return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def _get_api_key() -> str:
        """Retrieve the API key from the environment."""
        key = os.environ.get("EXPECTED_PARROT_API_KEY")
        if not key:
            try:
                from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler
                key = ExpectedParrotKeyHandler().get_ep_api_key()
            except Exception:
                pass
        if not key:
            raise StudyAuthError(
                "No API key found. Set EXPECTED_PARROT_API_KEY or run edsl.login()."
            )
        # Strip surrounding quotes if present (from .env files)
        return key.strip("'\"")

    # ------------------------------------------------------------------
    # Server communication
    # ------------------------------------------------------------------

    def _server_post(self, endpoint: str, body: dict) -> requests.Response:
        """POST to the server with bearer auth."""
        try:
            return requests.post(
                f"{self.server_url}{endpoint}",
                json=body,
                headers=self._headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

    @staticmethod
    def _authed_remote_url(gitlab_url: str, token: str) -> str:
        """Inject ``oauth2:{token}@`` into a GitLab URL."""
        parsed = urlparse(gitlab_url)
        authed = parsed._replace(
            netloc=f"oauth2:{token}@{parsed.hostname}"
            + (f":{parsed.port}" if parsed.port else "")
        )
        return urlunparse(authed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def uuid(self) -> str | None:
        return self._uuid

    @property
    def is_pushed(self) -> bool:
        return self._uuid is not None

    def push(
        self,
        branch: str = "main",
        *,
        alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        verbose: bool = False,
    ):
        """Push the local git repo to GitLab via the meta-server.

        On the first push, creates a UUID and GitLab project. Subsequent
        pushes just mint a new token and push.
        """
        # Update local metadata from kwargs
        if alias is not None:
            self.alias = alias
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if visibility is not None:
            self.visibility = visibility

        self._check_git_clean()

        body = {
            "uuid": self._uuid,
            "alias": self.alias,
            "title": self.title,
            "description": self.description,
            "visibility": self.visibility or "private",
        }

        _log(verbose, "Requesting push token...")
        resp = self._server_post("/push-req", body)

        if resp.status_code == 409:
            raise StudyServerError("Alias already taken.")
        if resp.status_code == 403:
            raise StudyServerError("Not authorized to push to this study.")
        if not resp.ok:
            raise StudyServerError(
                f"Push request failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()

        if self._uuid is None:
            self._uuid = data["uuid"]
            _log(verbose, f"Created study uuid={self._uuid}")
        self._gitlab_url = data.get("gitlab_url", self._gitlab_url)
        self._save_metadata()

        remote = self._authed_remote_url(data["gitlab_url"], data["token"])
        _log(verbose, "Pushing...")
        self._git_run("push", remote, f"HEAD:{branch}", capture_output=True)
        _log(verbose, "Push complete.")

    def pull(self, branch: str = "main", *, verbose: bool = False):
        """Pull from GitLab via the meta-server."""
        if self._uuid is None:
            raise StudyError("Study has not been pushed yet.")

        _log(verbose, "Requesting pull token...")
        resp = self._server_post("/pull-event", {"uuid": self._uuid})

        if not resp.ok:
            raise StudyServerError(
                f"Pull request failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        remote = self._authed_remote_url(data["gitlab_url"], data["token"])
        _log(verbose, "Fetching...")
        self._git_run("fetch", remote, branch, capture_output=True)
        self._git_run("merge", "FETCH_HEAD")
        _log(verbose, "Pull complete.")

    def view(self):
        """Open the GitLab repository page in the default browser."""
        import webbrowser

        if self._gitlab_url is None:
            raise StudyError("No GitLab URL available. Push the study first.")
        web_url = self._gitlab_url
        if web_url.endswith(".git"):
            web_url = web_url[:-4]
        webbrowser.open(web_url)

    def set_metadata(
        self,
        *,
        alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        verbose: bool = False,
    ):
        """Update metadata on the server for an already-pushed study."""
        if self._uuid is None:
            raise StudyError("Study has not been pushed yet.")

        body = {}
        if alias is not None:
            body["alias"] = alias
        if title is not None:
            body["title"] = title
        if description is not None:
            body["description"] = description
        if visibility is not None:
            body["visibility"] = visibility

        if not body:
            raise StudyError("Provide at least one field to update.")

        _log(verbose, f"Updating metadata for {self._uuid}...")
        try:
            resp = requests.patch(
                f"{self.server_url}/repos/{self._uuid}",
                json=body,
                headers=self._headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if not resp.ok:
            raise StudyServerError(
                f"Metadata update failed ({resp.status_code}): {resp.text}"
            )

        # Update local state
        if alias is not None:
            self.alias = alias
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if visibility is not None:
            self.visibility = visibility
        self._save_metadata()
        _log(verbose, "Metadata updated.")

    @classmethod
    def clone(
        cls,
        *,
        uuid: str | None = None,
        alias: str | None = None,
        directory_location: str | None = None,
        server_url: str | None = None,
        verbose: bool = False,
    ) -> "Study":
        """Clone a study from the server.

        Provide either ``uuid`` or ``alias`` (not both). Alias lookup is
        scoped to the authenticated user's studies. Owner gets write access;
        others get read-only (visibility permitting).
        """
        if uuid is None and alias is None:
            raise StudyError("Provide uuid or alias.")
        if uuid is not None and alias is not None:
            raise StudyError("Provide uuid or alias, not both.")

        if server_url is not None:
            url = server_url.rstrip("/")
        else:
            url = cls._default_server_url()

        api_key = cls._get_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}

        body = {}
        if uuid is not None:
            body["uuid"] = uuid
        if alias is not None:
            body["alias"] = alias

        _log(verbose, f"Requesting clone token from {url}...")
        try:
            resp = requests.post(
                f"{url}/clone-req", json=body, headers=headers, timeout=30
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if resp.status_code == 404:
            error = resp.json().get("error", "not_found")
            raise StudyServerError(f"Study not found or not yet pushed: {error}")
        if resp.status_code == 403:
            raise StudyServerError("Not authorized to access this study.")
        if not resp.ok:
            raise StudyServerError(
                f"Clone request failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        token = data["token"]
        gitlab_url = data["gitlab_url"]
        repo_uuid = data["uuid"]

        authed_url = cls._authed_remote_url(gitlab_url, token)

        # Use alias or uuid fragment as directory name
        dir_name = (alias or repo_uuid[:12]).replace("/", "-")

        if directory_location is None:
            directory_location = tempfile.mkdtemp(prefix=f"edsl_study_{dir_name}_")
        directory_location = str(Path(directory_location).resolve())
        clone_path = os.path.join(directory_location, dir_name)

        _log(verbose, f"Cloning into {clone_path}...")
        try:
            subprocess.run(
                ["git", "clone", authed_url, clone_path],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise StudyGitError(
                f"git clone failed: {exc.stderr or exc.stdout or str(exc)}"
            )

        study = object.__new__(cls)
        study._field_name = dir_name
        study._field_alias = alias
        study.title = None
        study.description = None
        study.visibility = "private"
        study._directory_location = directory_location
        study.path = clone_path
        study.server_url = url
        study._uuid = repo_uuid
        study._gitlab_url = gitlab_url

        study._write_gitignore()
        study._save_metadata()

        _log(verbose, f"Clone complete. uuid={repo_uuid}")
        return study

    @classmethod
    def from_repo(
        cls,
        repo_path: str,
        *,
        name: str | None = None,
        server_url: str | None = None,
        verbose: bool = False,
    ) -> "Study":
        """Wrap an existing git repository as a Study.

        The repo is adopted in-place. A ``.study.json`` is created so the
        study can be pushed to the server.
        """
        repo_path = str(Path(repo_path).resolve())

        if not os.path.isdir(os.path.join(repo_path, ".git")):
            raise StudyError(f"Not a git repository: {repo_path}")

        if name is None:
            name = os.path.basename(repo_path)

        if server_url is not None:
            url = server_url.rstrip("/")
        else:
            url = cls._default_server_url()

        _log(verbose, f"Wrapping {repo_path} as study '{name}'...")

        study = object.__new__(cls)
        study._field_name = name
        study._field_alias = None
        study.title = None
        study.description = None
        study.visibility = "private"
        study._directory_location = str(Path(repo_path).parent)
        study.path = repo_path
        study.server_url = url
        study._uuid = None
        study._gitlab_url = None

        study._write_gitignore()
        study._save_metadata()

        _log(verbose, f"Study created at {repo_path}")
        return study

    @classmethod
    def list(
        cls,
        *,
        server_url: str | None = None,
        verbose: bool = False,
    ):
        """List all studies for the authenticated user.

        Returns a ``ScenarioList`` with one row per study.
        """
        from edsl.scenarios import Scenario, ScenarioList

        if server_url is not None:
            url = server_url.rstrip("/")
        else:
            url = cls._default_server_url()

        api_key = cls._get_api_key()
        headers = {"Authorization": f"Bearer {api_key}"}

        _log(verbose, f"Listing studies from {url}...")
        try:
            resp = requests.get(
                f"{url}/repos", headers=headers, timeout=30
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if not resp.ok:
            raise StudyServerError(
                f"List request failed ({resp.status_code}): {resp.text}"
            )

        repos = resp.json().get("repos", [])
        _log(verbose, f"Found {len(repos)} studies.")
        scenarios = [
            Scenario({
                "uuid": r["uuid"],
                "alias": r.get("alias"),
                "title": r.get("title"),
                "description": r.get("description"),
                "visibility": r.get("visibility"),
                "created_at": r.get("created_at"),
                "provisioned": bool(r.get("provisioned")),
            })
            for r in repos
        ]
        return ScenarioList(scenarios)

    def add_file(
        self,
        source_path: str,
        destination_path: str | None = None,
        *,
        verbose: bool = False,
    ) -> str:
        """Copy a file into the study directory."""
        src = Path(source_path).resolve()
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        if src.is_dir():
            raise StudyError(f"source_path must be a file, not a directory: {src}")

        if destination_path is not None:
            dest_dir = Path(self.path) / destination_path
            dest_dir.mkdir(parents=True, exist_ok=True)
        else:
            dest_dir = Path(self.path)

        dest = dest_dir / src.name
        shutil.copy2(str(src), str(dest))
        _log(verbose, f"Added {src.name} -> {dest}")
        return str(dest)

    # ------------------------------------------------------------------
    # Inspection (read-only shell / git commands)
    # ------------------------------------------------------------------

    def pwd(self) -> str:
        """Return the absolute path to the study directory."""
        return self.path

    def ls(self, path: str = ".", all: bool = False) -> "list[str]":
        """List files in the study directory (or a subdirectory).

        Args:
            path: Relative path within the study. Defaults to root.
            all: If True, include hidden files (dotfiles).

        Returns:
            Sorted list of filenames.
        """
        target = Path(self.path) / path
        if not target.is_dir():
            raise StudyError(f"Not a directory: {target}")
        entries = sorted(target.iterdir())
        if not all:
            entries = [e for e in entries if not e.name.startswith(".")]
        return [e.name for e in entries]

    def tree(self, path: str = ".", max_depth: int | None = None) -> str:
        """Return a tree-style listing of the study directory.

        Excludes ``.git`` and ``.study.json``. Uses ``tree`` if available,
        otherwise falls back to a simple Python implementation.

        Args:
            path: Relative path within the study. Defaults to root.
            max_depth: Maximum depth to display.
        """
        target = Path(self.path) / path
        if not target.is_dir():
            raise StudyError(f"Not a directory: {target}")

        # Try the system tree command
        cmd = ["tree", str(target), "-I", ".git|.study.json", "--noreport"]
        if max_depth is not None:
            cmd.extend(["-L", str(max_depth)])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.rstrip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # Fallback: simple Python tree
        return self._python_tree(target, max_depth=max_depth)

    @staticmethod
    def _python_tree(root: Path, prefix: str = "", max_depth: int | None = None, _depth: int = 0) -> str:
        SKIP = {".git", ".study.json"}
        if max_depth is not None and _depth > max_depth:
            return ""
        lines = [str(root.name) + "/"] if _depth == 0 else []
        entries = sorted(
            [e for e in root.iterdir() if e.name not in SKIP],
            key=lambda e: (not e.is_dir(), e.name),
        )
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir() and (max_depth is None or _depth + 1 < max_depth):
                extension = "    " if is_last else "│   "
                subtree = Study._python_tree(
                    entry, prefix=prefix + extension,
                    max_depth=max_depth, _depth=_depth + 1,
                )
                if subtree:
                    lines.append(subtree)
        return "\n".join(lines)

    def status(self) -> str:
        """Return ``git status`` output."""
        result = self._git_run("status")
        return result.stdout.rstrip()

    def log(self, n: int = 10) -> str:
        """Return recent git log (oneline format).

        Args:
            n: Number of commits to show.
        """
        result = self._git_run("log", "--oneline", f"-{n}")
        return result.stdout.rstrip()

    def diff(self, staged: bool = False) -> str:
        """Return ``git diff`` output.

        Args:
            staged: If True, show staged (cached) changes instead of unstaged.
        """
        args = ["diff"]
        if staged:
            args.append("--cached")
        result = self._git_run(*args)
        return result.stdout.rstrip()

    def branches(self) -> "list[str]":
        """Return list of local branch names."""
        result = self._git_run("branch", "--format=%(refname:short)")
        return [b for b in result.stdout.strip().splitlines() if b]

    def current_branch(self) -> str:
        """Return the name of the current branch."""
        result = self._git_run("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def du(self) -> str:
        """Return disk usage of the study directory (excluding .git).

        Returns a human-readable size string.
        """
        total = 0
        git_dir = Path(self.path) / ".git"
        for f in Path(self.path).rglob("*"):
            if f.is_file() and not str(f).startswith(str(git_dir)):
                total += f.stat().st_size
        # Human-readable
        for unit in ("B", "KB", "MB", "GB"):
            if total < 1024:
                return f"{total:.1f} {unit}"
            total /= 1024
        return f"{total:.1f} TB"

    def wc(self, path: str = ".") -> dict:
        """Count files, directories, and total lines in the study.

        Args:
            path: Relative path within the study. Defaults to root.

        Returns:
            Dict with ``files``, ``dirs``, ``lines`` keys.
        """
        target = Path(self.path) / path
        files = dirs = lines = 0
        git_dir = Path(self.path) / ".git"
        for entry in target.rglob("*"):
            if str(entry).startswith(str(git_dir)):
                continue
            if entry.name == _METADATA_FILE:
                continue
            if entry.is_dir():
                dirs += 1
            elif entry.is_file():
                files += 1
                try:
                    lines += len(entry.read_text(errors="ignore").splitlines())
                except (OSError, UnicodeDecodeError):
                    pass
        return {"files": files, "dirs": dirs, "lines": lines}

    def cat(self, path: str) -> str:
        """Return the contents of a file in the study.

        Args:
            path: Relative path within the study.
        """
        target = Path(self.path) / path
        if not target.is_file():
            raise StudyError(f"Not a file: {target}")
        return target.read_text()

    def head(self, path: str, n: int = 10) -> str:
        """Return the first ``n`` lines of a file.

        Args:
            path: Relative path within the study.
            n: Number of lines.
        """
        target = Path(self.path) / path
        if not target.is_file():
            raise StudyError(f"Not a file: {target}")
        with open(target) as f:
            return "".join(f.readline() for _ in range(n))

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _git_run(self, *args, capture_output=True) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=self.path,
                check=True,
                capture_output=capture_output,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise StudyGitError(
                f"git {' '.join(args)} failed: {exc.stderr or exc.stdout or str(exc)}"
            )

    def _check_git_clean(self):
        result = self._git_run("status", "--porcelain")
        if result.stdout.strip():
            raise StudyGitError(
                "Working tree is not clean. Commit or stash changes before pushing.\n"
                + result.stdout.strip()
            )

    # ------------------------------------------------------------------
    # Config helper
    # ------------------------------------------------------------------

    @staticmethod
    def _default_server_url() -> str:
        try:
            from edsl.config import CONFIG
            return CONFIG.get("EDSL_STUDY_SERVER_URL")
        except Exception:
            return _DEFAULT_SERVER_URL

    # ------------------------------------------------------------------
    # Base abstract method implementations
    # ------------------------------------------------------------------

    def to_dict(self, add_edsl_version=True) -> dict:
        d = {
            "name": self.name,
            "directory_location": self._directory_location,
            "server_url": self.server_url,
            "uuid": self._uuid,
            "alias": self.alias,
            "title": self.title,
            "description": self.description,
            "visibility": self.visibility,
        }
        if add_edsl_version:
            from edsl import __version__
            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Study"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Study":
        s = cls(
            name=d.get("name", "study"),
            directory_location=d.get("directory_location"),
            server_url=d.get("server_url"),
        )
        # Restore metadata that from_dict wouldn't set
        if d.get("alias"):
            s.alias = d["alias"]
        if d.get("title"):
            s.title = d["title"]
        if d.get("description"):
            s.description = d["description"]
        if d.get("visibility"):
            s.visibility = d["visibility"]
        return s

    @staticmethod
    def example() -> "Study":
        return Study("example_study")

    def code(self) -> str:
        parts = [f"    name={self.name!r}"]
        parts.append(f"    directory_location={self._directory_location!r}")
        parts.append(f"    server_url={self.server_url!r}")
        args = ",\n".join(parts)
        return f"from edsl.study import Study\nstudy = Study(\n{args},\n)"

    def _eval_repr_(self) -> str:
        parts = [f"name={self.name!r}"]
        if self.alias:
            parts.append(f"alias={self.alias!r}")
        return f"Study({', '.join(parts)})"

    def _summary_repr(self) -> str:
        from rich.table import Table
        from rich.console import Console
        import io

        table = Table(title="Study", show_header=True)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("name", self.name or "(not set)")
        table.add_row("alias", self.alias or "(not set)")
        table.add_row("title", self.title or "(not set)")
        table.add_row("description", self.description or "(not set)")
        table.add_row("visibility", self.visibility or "private")
        table.add_row("path", self.path)
        table.add_row("server_url", self.server_url)
        table.add_row("uuid", self._uuid or "(not pushed)")

        try:
            result = self._git_run("status", "--porcelain")
            git_status = "clean" if not result.stdout.strip() else "dirty"
        except StudyGitError:
            git_status = "unknown"
        table.add_row("git_status", git_status)

        string_io = io.StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        console.print(table, end="")
        return string_io.getvalue()
