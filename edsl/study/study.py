"""Study class — a git-backed EDSL object with remote sync via a meta-server."""

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from edsl.study.client import StudyClient, authed_remote_url
from edsl.study.descriptors import NameField, AliasField
from edsl.study.exceptions import (
    StudyError,
    StudyGitError,
)

_METADATA_FILE = ".study.json"


@dataclass
class PushResult:
    """Returned by :meth:`Study.push`."""

    uuid: str
    url: str
    branch: str
    created: bool


@dataclass
class PullResult:
    """Returned by :meth:`Study.pull`."""

    uuid: str
    url: str
    branch: str


# Default scaffold for new studies. Each entry is either:
#   {"type": "dir"}  — creates the directory with a .gitkeep
#   {"type": "file", "content": "..."}  — creates the file with that content
DEFAULT_SCAFFOLD = {
    "data": {"type": "dir"},
    "analysis": {"type": "dir"},
    "writeup": {"type": "dir"},
    "writeup/plots": {"type": "dir"},
    "writeup/tables": {"type": "dir"},
    "writeup/report.md": {
        "type": "file",
        "content": "# Report\n",
    },
    "Makefile": {
        "type": "file",
        "content": (
            ".PHONY: all clean\n"
            "\n"
            "all:\n"
            '\t@echo "Run analysis and build report"\n'
            "\n"
            "clean:\n"
            '\t@echo "Clean generated files"\n'
        ),
    },
}

_METADATA_FIELDS = ("alias", "title", "description", "visibility")


def _log(verbose: bool, msg: str):
    if verbose:
        print(msg)


def _spinner(message: str):
    """Return a rich stderr spinner context manager."""
    from rich.console import Console

    return Console(stderr=True).status(message, spinner="dots")


class Study:
    """A git-backed study directory that syncs with a remote meta-server.

    A Study wraps a local directory under git version control. It can push to
    and pull from GitLab via a meta-server, authenticated by an API key
    (``EXPECTED_PARROT_API_KEY``).

    Only ``name`` is required at construction (defaults to ``"study"``).
    Metadata like ``alias``, ``title`` (local / serialized only), ``description``, and ``visibility``
    can be set at push time or updated later. Server-side metadata updates
    (via :meth:`set_metadata`) cover alias, description, and visibility only.
    """

    name = NameField()
    alias = AliasField()

    def __init__(
        self,
        name: str = "study",
        *,
        directory_location: str | None = None,
        expected_parrot_url: str | None = None,
        scaffold: dict | bool = False,
    ):
        """
        Args:
            name: Directory basename for the study.
            directory_location: Parent directory. Defaults to a temp directory.
            expected_parrot_url: Meta-server URL. Defaults to config or built-in fallback.
            scaffold: If ``True``, populate with ``DEFAULT_SCAFFOLD``. If a dict,
                use it as a custom scaffold. If ``False`` (default), no scaffolding.
        """
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

        # Server
        self.expected_parrot_url = expected_parrot_url

        # Internal state loaded from .study.json
        self._uuid: str | None = None
        self._gitlab_url: str | None = None

        self._scaffold = scaffold
        self._init_directory()

    # ------------------------------------------------------------------
    # Alternate constructors (bypass __init__)
    # ------------------------------------------------------------------

    @classmethod
    def _new_bare(
        cls,
        name: str,
        path: str,
        expected_parrot_url: str,
        *,
        alias: str | None = None,
        uuid: str | None = None,
        gitlab_url: str | None = None,
    ) -> "Study":
        """Create a Study instance without running ``_init_directory``.

        Used by ``clone`` and ``from_repo`` which set up the directory
        themselves.
        """
        study = object.__new__(cls)
        study._field_name = name
        study._field_alias = alias
        study.title = None
        study.description = None
        study.visibility = "private"
        study._directory_location = str(Path(path).parent)
        study.path = path
        study.expected_parrot_url = expected_parrot_url
        study._uuid = uuid
        study._gitlab_url = gitlab_url
        return study

    # ------------------------------------------------------------------
    # Directory / git initialisation
    # ------------------------------------------------------------------

    def _init_directory(self):
        metadata_path = os.path.join(self.path, _METADATA_FILE)

        if not os.path.isdir(self.path):
            os.makedirs(self.path, exist_ok=True)
            self._git_run("init")
            self._ensure_git_identity()
            self._write_gitignore()
            if self._scaffold:
                tree = DEFAULT_SCAFFOLD if self._scaffold is True else self._scaffold
                self._apply_scaffold(tree)
            self._save_metadata()
        elif os.path.isfile(metadata_path):
            self._load_metadata()
        else:
            if not os.path.isdir(os.path.join(self.path, ".git")):
                self._git_run("init")
            self._ensure_git_identity()
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

    def _apply_scaffold(self, tree: dict):
        """Create directories and files from a scaffold tree.

        Args:
            tree: A dict mapping relative paths to entries. Each entry is:
                ``{"type": "dir"}`` — creates the directory with a ``.gitkeep``
                ``{"type": "file", "content": "..."}`` — creates the file
        """
        for rel_path, entry in tree.items():
            full_path = Path(self.path) / rel_path
            if entry["type"] == "dir":
                full_path.mkdir(parents=True, exist_ok=True)
                gitkeep = full_path / ".gitkeep"
                if not gitkeep.exists():
                    gitkeep.touch()
            elif entry["type"] == "file":
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(entry.get("content", ""))

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
            "expected_parrot_url": self.expected_parrot_url,
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
        self.expected_parrot_url = data.get(
            "expected_parrot_url", self.expected_parrot_url
        )

    def _update_metadata_fields(self, **kwargs):
        """Set any non-None metadata kwargs on self."""
        for field in _METADATA_FIELDS:
            value = kwargs.get(field)
            if value is not None:
                setattr(self, field, value)
        if kwargs.get("expected_parrot_url") is not None:
            self.expected_parrot_url = kwargs.get("expected_parrot_url")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def uuid(self) -> str | None:
        return self._uuid

    @property
    def is_pushed(self) -> bool:
        return self._uuid is not None

    def _sync_to_remote(
        self,
        branch: str,
        *,
        alias: str | None,
        title: str | None,
        description: str | None,
        visibility: str | None,
        verbose: bool,
        spinner_msg: str,
    ) -> PushResult:
        """Coop upload/patch, mint GitLab token, then ``git push``."""
        self._update_metadata_fields(
            alias=alias,
            title=title,
            description=description,
            visibility=visibility,
        )
        self._check_git_clean()

        was_new = self._uuid is None
        client = StudyClient(self.expected_parrot_url)
        with _spinner(spinner_msg):
            data = client.push_request(
                value=self,
                uuid=self._uuid,
                alias=self.alias,
                description=self.description,
                visibility=self.visibility or "private",
            )

        if self._uuid is None:
            self._uuid = data["uuid"]
            _log(verbose, f"Created study uuid={self._uuid}")
        self._update_metadata_fields(
            alias=data.get("alias"),
            description=data.get("description"),
            visibility=data.get("visibility"),
            expected_parrot_url=client._coop.url,
        )
        self._gitlab_url = data.get("gitlab_url", self._gitlab_url)
        self._save_metadata()

        remote = authed_remote_url(data["gitlab_url"], data["gitlab_token"])
        self._git_push_with_retry(remote, branch, verbose=verbose)
        _log(verbose, "Push complete.")

        return PushResult(
            uuid=self._uuid,
            url=self._gitlab_url,
            branch=branch,
            created=was_new,
        )

    def push(
        self,
        branch: str = "main",
        *,
        alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        verbose: bool = False,
    ) -> PushResult:
        """Push the local git repo to GitLab via the meta-server.

        On the first push, creates a UUID and GitLab project. Subsequent
        pushes just mint a new token and push.

        Returns a :class:`PushResult` with the study UUID, remote URL,
        branch, and whether this was the first push.
        """
        spinner_msg = (
            "[bold cyan]Creating study..."
            if self._uuid is None
            else "[bold cyan]Requesting push token..."
        )
        return self._sync_to_remote(
            branch,
            alias=alias,
            title=title,
            description=description,
            visibility=visibility,
            verbose=verbose,
            spinner_msg=spinner_msg,
        )

    def patch(
        self,
        branch: str = "main",
        *,
        alias: str | None = None,
        title: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        verbose: bool = False,
    ) -> PushResult:
        """Sync an already-pushed study: patch object on Coop, mint token, ``git push``.

        Same flow as :meth:`push` after the first upload; requires
        :attr:`uuid` to be set (use :meth:`push` to create the remote study).
        """
        if self._uuid is None:
            raise StudyError(
                "Study has not been pushed yet. Use push() to create it on the server."
            )
        return self._sync_to_remote(
            branch,
            alias=alias,
            title=title,
            description=description,
            visibility=visibility,
            verbose=verbose,
            spinner_msg="[bold cyan]Patching study...",
        )

    def pull(self, branch: str = "main", *, verbose: bool = False) -> PullResult:
        """Pull from GitLab via the meta-server.

        Returns a :class:`PullResult` with the study UUID, remote URL,
        and branch.
        """
        if self._uuid is None:
            raise StudyError("Study has not been pushed yet.")

        _log(verbose, "Requesting pull token...")
        client = StudyClient(self.expected_parrot_url)
        data = client.pull_request(self._uuid)

        remote = authed_remote_url(data["gitlab_url"], data["gitlab_token"])
        _log(verbose, "Fetching...")
        self._git_run("fetch", remote, branch, capture_output=True)
        self._git_run("merge", "FETCH_HEAD")
        _log(verbose, "Pull complete.")

        return PullResult(
            uuid=self._uuid,
            url=self._gitlab_url,
            branch=branch,
        )

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
        description: str | None = None,
        visibility: str | None = None,
        verbose: bool = False,
    ):
        """Update Coop object metadata for an already-pushed study.

        Only ``alias``, ``description``, and ``visibility`` are sent to the
        server. Use :meth:`push` / :meth:`patch` with ``title=`` to change the
        title stored in the study object blob and ``.study.json``.
        """
        if self._uuid is None:
            raise StudyError("Study has not been pushed yet.")

        patch = {
            "alias": alias,
            "description": description,
            "visibility": visibility,
        }
        body = {k: v for k, v in patch.items() if v is not None}
        if not body:
            raise StudyError("Provide at least one field to update.")

        _log(verbose, f"Updating metadata for {self._uuid}...")
        client = StudyClient(self.expected_parrot_url)
        client.update_metadata(self._uuid, **patch)

        self._update_metadata_fields(**body)
        self._save_metadata()
        _log(verbose, "Metadata updated.")

    @classmethod
    def clone(
        cls,
        *,
        uuid: str | None = None,
        alias: str | None = None,
        directory_location: str | None = None,
        expected_parrot_url: str | None = None,
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

        client = StudyClient(expected_parrot_url)

        with _spinner("[bold cyan]Requesting clone token...") as status:
            data = client.clone_request(uuid=uuid, alias=alias)

            token = data["token"]
            gitlab_url = data["gitlab_url"]
            repo_uuid = data["uuid"]

            authed_url = authed_remote_url(gitlab_url, token)
            dir_name = (alias or repo_uuid[:12]).replace("/", "-")

            if directory_location is None:
                directory_location = tempfile.mkdtemp(prefix=f"edsl_study_{dir_name}_")
            directory_location = str(Path(directory_location).resolve())
            clone_path = os.path.join(directory_location, dir_name)

            status.update("[bold cyan]Cloning repository...")
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

            status.update("[bold cyan]Setting up study...")
            study = cls._new_bare(
                dir_name,
                clone_path,
                expected_parrot_url,
                alias=alias,
                uuid=repo_uuid,
                gitlab_url=gitlab_url,
            )
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
        expected_parrot_url: str | None = None,
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

        _log(verbose, f"Wrapping {repo_path} as study '{name}'...")

        study = cls._new_bare(name, repo_path, expected_parrot_url)
        study._write_gitignore()
        study._save_metadata()

        _log(verbose, f"Study created at {repo_path}")
        return study

    @classmethod
    def list(
        cls,
        *,
        expected_parrot_url: str | None = None,
        verbose: bool = False,
    ):
        """List all studies for the authenticated user.

        Returns a ``ScenarioList`` with one row per study.
        """
        from edsl.scenarios import Scenario, ScenarioList

        client = StudyClient(expected_parrot_url)

        _log(verbose, f"Listing studies...")
        repos = client.list_repos()
        _log(verbose, f"Found {len(repos)} studies.")

        scenarios = [
            Scenario(
                {
                    "uuid": r["uuid"],
                    "alias": r.get("alias"),
                    "description": r.get("description"),
                    "visibility": r.get("visibility"),
                    "created_ts": r.get("created_ts"),
                }
            )
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
    # Shell command runner
    # ------------------------------------------------------------------

    def command(self, cmd: str) -> None:
        """Run a shell command in the study directory and print its output.

        Args:
            cmd: The command string to execute (e.g. ``"ls -la"``, ``"git status"``).

        Raises:
            StudyError: If the command exits with a non-zero status.
        """
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=self.path,
                capture_output=True,
                text=True,
                check=True,
            )
            print(result.stdout.rstrip())
        except subprocess.CalledProcessError as exc:
            raise StudyError(
                f"Command failed (exit {exc.returncode}): {cmd}\n"
                + (exc.stderr or exc.stdout or "").rstrip()
            )

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _ensure_git_identity(self):
        """Set a local git identity if none is configured (global or local).

        CI environments often lack a git user config, which causes commits to
        fail.  This sets repo-local ``user.name`` / ``user.email`` only when
        neither a global nor a local value is already present.
        """
        for key, fallback in [
            ("user.name", "EDSL Study"),
            ("user.email", "study@expectedparrot.com"),
        ]:
            try:
                self._git_run("config", key)
            except StudyGitError:
                self._git_run("config", key, fallback)

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

    def _git_push_with_retry(
        self, remote: str, branch: str, max_retries: int = 3, verbose: bool = False
    ):
        """Push with retries to handle GitLab token propagation delays."""
        import time

        for attempt in range(max_retries):
            try:
                self._git_run("push", remote, f"HEAD:{branch}", capture_output=True)
                return
            except StudyGitError as exc:
                is_auth_error = "Access denied" in str(
                    exc
                ) or "Authentication failed" in str(exc)
                if is_auth_error and attempt < max_retries - 1:
                    wait = 5 * (attempt + 1)
                    with _spinner(
                        "[bold cyan]Waiting for GitLab token to propagate..."
                    ) as status:
                        for remaining in range(wait, 0, -1):
                            status.update(
                                f"[bold cyan]Waiting for GitLab token to propagate... [white]{remaining}s"
                            )
                            time.sleep(1)
                else:
                    raise

    def _check_git_clean(self):
        result = self._git_run("status", "--porcelain")
        if result.stdout.strip():
            raise StudyGitError(
                "Working tree is not clean. Commit or stash changes before pushing.\n"
                + result.stdout.strip()
            )

    # ------------------------------------------------------------------
    # Serialization / representation
    # ------------------------------------------------------------------

    def to_dict(self, add_edsl_version=True) -> dict:
        d = {
            "name": self.name,
            "directory_location": self._directory_location,
            "expected_parrot_url": self.expected_parrot_url,
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
            expected_parrot_url=d.get("expected_parrot_url"),
        )
        s._update_metadata_fields(
            alias=d.get("alias"),
            title=d.get("title"),
            description=d.get("description"),
            visibility=d.get("visibility"),
        )
        return s

    @staticmethod
    def example() -> "Study":
        return Study("example_study")

    def code(self) -> str:
        parts = [f"    name={self.name!r}"]
        parts.append(f"    directory_location={self._directory_location!r}")
        parts.append(f"    expected_parrot_url={self.expected_parrot_url!r}")
        args = ",\n".join(parts)
        return f"from edsl.study import Study\nstudy = Study(\n{args},\n)"

    def __repr__(self) -> str:
        import os

        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self._eval_repr_()
        return self._summary_repr()

    def __str__(self) -> str:
        return self._eval_repr_()

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
        table.add_row("expected_parrot_url", self.expected_parrot_url)
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
