"""Study class — a git-backed EDSL object with remote sync via a meta-server."""

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from edsl.base.base_class import Base
from edsl.study.descriptors import NameField, OwnerField, ProjectField, TopicField
from edsl.study.exceptions import (
    StudyAuthError,
    StudyError,
    StudyGitError,
    StudyNotRegisteredError,
    StudyServerError,
)

_DEFAULT_SERVER_URL = "https://study.expectedparrot.com"
_METADATA_FILE = ".study.json"


def _log(verbose: bool, msg: str):
    if verbose:
        print(msg)


class Study(Base):
    """A git-backed study directory that syncs with a remote meta-server.

    A Study wraps a local directory under git version control. It can register
    with a meta-server, then push/pull via GitLab using Ed25519-signed requests
    for authentication.

    Only ``name`` is required at construction. The ``owner``, ``project``, and
    ``topic`` fields can be set later but must be populated before calling
    ``register()`` or ``push()``.
    """

    name = NameField()
    owner = OwnerField()
    project = ProjectField()
    topic = TopicField()

    def __init__(
        self,
        name: str,
        *,
        owner: str | None = None,
        project: str | None = None,
        topic: str | None = None,
        directory_location: str | None = None,
        server_url: str | None = None,
    ):
        self.name = name
        self.owner = owner
        self.project = project
        self.topic = topic

        # Resolve path: directory_location / name
        if directory_location is None:
            directory_location = tempfile.mkdtemp(prefix=f"edsl_study_{name}_")
        self._directory_location = str(Path(directory_location).resolve())
        self.path = os.path.join(self._directory_location, name)

        # Resolve server URL
        if server_url is not None:
            self.server_url = server_url.rstrip("/")
        else:
            self.server_url = self._default_server_url()

        # Internal state loaded from .study.json (or generated fresh)
        self._uuid: str | None = None
        self._gitlab_url: str | None = None
        self._private_key: Ed25519PrivateKey | None = None
        self._recovery_codes: list[str] = []

        self._init_directory()

    # ------------------------------------------------------------------
    # Directory / git initialisation
    # ------------------------------------------------------------------

    def _init_directory(self):
        """Create the study directory and git repo if needed, then load or generate keys."""
        metadata_path = os.path.join(self.path, _METADATA_FILE)

        if not os.path.isdir(self.path):
            os.makedirs(self.path, exist_ok=True)
            self._git_run("init")
            self._write_gitignore()
            self._generate_keypair()
            self._save_metadata()
        elif os.path.isfile(metadata_path):
            self._load_metadata()
        else:
            # Directory exists but no metadata — fresh study in existing dir
            if not os.path.isdir(os.path.join(self.path, ".git")):
                self._git_run("init")
            self._write_gitignore()
            self._generate_keypair()
            self._save_metadata()

    def _write_gitignore(self):
        """Ensure .gitignore contains .study.json and commit it."""
        gitignore_path = os.path.join(self.path, ".gitignore")
        lines: list[str] = []
        if os.path.isfile(gitignore_path):
            with open(gitignore_path) as f:
                lines = f.read().splitlines()
        if _METADATA_FILE not in lines:
            lines.append(_METADATA_FILE)
            with open(gitignore_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            # Stage and commit the .gitignore so the repo starts clean
            try:
                self._git_run("add", ".gitignore")
                self._git_run("commit", "-m", "Initial .gitignore")
            except StudyGitError:
                # May fail if git user.name/user.email not configured
                pass

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------

    def _generate_keypair(self):
        """Generate a fresh Ed25519 keypair."""
        self._private_key = Ed25519PrivateKey.generate()

    def _public_key_bytes(self) -> bytes:
        """Return raw 32-byte public key."""
        return self._private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

    def _public_key_b64(self) -> str:
        """Return base64url-encoded public key (no padding)."""
        return base64.urlsafe_b64encode(self._public_key_bytes()).rstrip(b"=").decode()

    def _private_key_bytes(self) -> bytes:
        """Return raw 32-byte private key."""
        return self._private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )

    # ------------------------------------------------------------------
    # Metadata persistence (.study.json)
    # ------------------------------------------------------------------

    def _save_metadata(self):
        """Write .study.json into the study directory."""
        data = {
            "uuid": self._uuid,
            "gitlab_url": self._gitlab_url,
            "owner": self.owner,
            "project": self.project,
            "topic": self.topic,
            "server_url": self.server_url,
            "private_key": base64.urlsafe_b64encode(self._private_key_bytes())
            .rstrip(b"=")
            .decode(),
            "recovery_codes": self._recovery_codes,
        }
        metadata_path = os.path.join(self.path, _METADATA_FILE)
        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_metadata(self):
        """Load .study.json from the study directory."""
        metadata_path = os.path.join(self.path, _METADATA_FILE)
        with open(metadata_path) as f:
            data = json.load(f)

        self._uuid = data.get("uuid")
        self._gitlab_url = data.get("gitlab_url")
        # Load fields from metadata, preferring constructor args if they were set
        if self.owner is None:
            self.owner = data.get("owner")
        if self.project is None:
            self.project = data.get("project")
        if self.topic is None:
            self.topic = data.get("topic")
        self.server_url = data.get("server_url", self.server_url)
        self._recovery_codes = data.get("recovery_codes", [])

        # Reconstruct private key from base64url-encoded bytes
        pk_b64 = data.get("private_key", "")
        if pk_b64:
            padded = pk_b64 + "=" * (-len(pk_b64) % 4)
            pk_bytes = base64.urlsafe_b64decode(padded)
            self._private_key = Ed25519PrivateKey.from_private_bytes(pk_bytes)
        else:
            self._generate_keypair()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _require_triple(self):
        """Raise StudyError if owner, project, or topic is not yet set."""
        missing = [f for f in ("owner", "project", "topic") if getattr(self, f) is None]
        if missing:
            raise StudyError(
                f"The following fields must be set before this operation: {', '.join(missing)}"
            )

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def _sign_payload(self, request_type: str) -> tuple[int, str]:
        """Build and sign ``{type}:{uuid}:{timestamp}``."""
        if self._uuid is None:
            raise StudyNotRegisteredError(
                "Study is not registered. Call register() first."
            )
        ts = int(time.time())
        payload = f"{request_type}:{self._uuid}:{ts}".encode("utf-8")
        sig_bytes = self._private_key.sign(payload)
        sig_b64 = base64.urlsafe_b64encode(sig_bytes).rstrip(b"=").decode()
        return ts, sig_b64

    # ------------------------------------------------------------------
    # Server communication
    # ------------------------------------------------------------------

    def _request_token(self, request_type: str) -> dict:
        """Sign a request and POST to the appropriate endpoint."""
        ts, sig = self._sign_payload(request_type)

        endpoint = "/push-req" if request_type == "push" else "/pull-event"
        url = f"{self.server_url}{endpoint}"

        try:
            resp = requests.post(
                url,
                json={
                    "uuid": self._uuid,
                    "timestamp": ts,
                    "signature": sig,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if resp.status_code == 401:
            error = resp.json().get("error", "unknown")
            raise StudyAuthError(f"Authentication failed: {error}")
        if resp.status_code == 404:
            error = resp.json().get("error", "not_found")
            raise StudyServerError(f"Server returned 404: {error}")
        if not resp.ok:
            raise StudyServerError(
                f"Server returned {resp.status_code}: {resp.text}"
            )

        return resp.json()

    @staticmethod
    def _authed_remote_url(gitlab_url: str, token: str) -> str:
        """Inject ``oauth2:{token}@`` into a GitLab URL."""
        parsed = urlparse(gitlab_url)
        authed = parsed._replace(netloc=f"oauth2:{token}@{parsed.hostname}" +
                                 (f":{parsed.port}" if parsed.port else ""))
        return urlunparse(authed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def clone(
        cls,
        owner: str,
        project: str,
        topic: str,
        *,
        directory_location: str | None = None,
        server_url: str | None = None,
        verbose: bool = False,
    ) -> "Study":
        """Clone a study from the server into a new local directory.

        Looks up the (owner, project, topic) triple on the server, obtains a
        write token, and ``git clone``s the repository. The clone's fresh
        keypair is registered with the server so it can push immediately.
        This invalidates any previously registered keypair for this study.
        """
        if server_url is not None:
            url = server_url.rstrip("/")
        else:
            url = cls._default_server_url()

        _log(verbose, f"Generating keypair...")
        private_key = Ed25519PrivateKey.generate()
        pub_bytes = private_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

        _log(verbose, f"Requesting clone token from {url}...")
        try:
            resp = requests.post(
                f"{url}/clone-req",
                json={
                    "owner": owner,
                    "project": project,
                    "topic": topic,
                    "new_pub_key": pub_b64,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if resp.status_code == 404:
            error = resp.json().get("error", "not_found")
            raise StudyServerError(f"Study not found or not yet pushed: {error}")
        if not resp.ok:
            raise StudyServerError(
                f"Clone request failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        token = data["token"]
        gitlab_url = data["gitlab_url"]
        repo_uuid = data["uuid"]

        authed_url = cls._authed_remote_url(gitlab_url, token)
        dir_name = topic.replace("/", "-") if "/" in topic else topic

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
        study._field_owner = owner
        study._field_project = project
        study._field_topic = topic
        study._directory_location = directory_location
        study.path = clone_path
        study.server_url = url
        study._uuid = repo_uuid
        study._gitlab_url = gitlab_url
        study._recovery_codes = []
        study._private_key = private_key

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
        owner: str | None = None,
        project: str | None = None,
        topic: str | None = None,
        server_url: str | None = None,
        verbose: bool = False,
    ) -> "Study":
        """Wrap an existing git repository as a Study.

        The repo is adopted in-place — no files are copied. A ``.study.json``
        and ``.gitignore`` entry are created so the study can be registered
        and pushed to the server.
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
        study._field_owner = None
        study._field_project = None
        study._field_topic = None
        if owner is not None:
            study.owner = owner
        if project is not None:
            study.project = project
        if topic is not None:
            study.topic = topic

        study._directory_location = str(Path(repo_path).parent)
        study.path = repo_path
        study.server_url = url
        study._uuid = None
        study._gitlab_url = None
        study._recovery_codes = []
        study._private_key = Ed25519PrivateKey.generate()

        study._write_gitignore()
        study._save_metadata()

        _log(verbose, f"Study created at {repo_path}")
        return study

    @classmethod
    def list(
        cls,
        owner: str,
        *,
        server_url: str | None = None,
        verbose: bool = False,
    ):
        """List all studies for an owner on the server.

        Returns a ``ScenarioList`` with one row per study.
        """
        from edsl.scenarios import Scenario, ScenarioList

        if server_url is not None:
            url = server_url.rstrip("/")
        else:
            url = cls._default_server_url()

        _log(verbose, f"Listing studies for '{owner}' from {url}...")

        try:
            resp = requests.get(
                f"{url}/repos",
                params={"owner": owner},
                timeout=30,
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
                "owner": r["owner"],
                "project": r["project"],
                "topic": r["topic"],
                "created_at": r.get("created_at"),
                "provisioned": bool(r.get("provisioned")),
            })
            for r in repos
        ]
        return ScenarioList(scenarios)

    def register(self, *, verbose: bool = False):
        """Register this study with the meta-server.

        POSTs the public key and (owner, project, topic) triple to ``/register``.
        If the triple is already registered, re-keys the existing record so
        this study can push.
        """
        self._require_triple()

        _log(verbose, f"Registering {self.owner}/{self.project}/{self.topic}...")

        url = f"{self.server_url}/register"
        body = {
            "owner": self.owner,
            "project": self.project,
            "topic": self.topic,
            "pub_key": self._public_key_b64(),
        }

        try:
            resp = requests.post(url, json=body, timeout=30)
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if resp.status_code == 409:
            _log(verbose, "Triple already registered. Adopting existing...")
            self._adopt_existing(verbose=verbose)
            return

        if not resp.ok:
            raise StudyServerError(
                f"Registration failed ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        self._uuid = data["uuid"]
        self._recovery_codes = data.get("recovery_codes", [])
        self._save_metadata()
        _log(verbose, f"Registered. uuid={self._uuid}")

    def _adopt_existing(self, *, verbose: bool = False):
        """Re-key an already-registered triple with this study's keypair.

        Called when ``register()`` gets a 409. Uses ``/clone-req`` with
        ``new_pub_key`` to replace the stored key and obtain the UUID.
        Then fetches and merges the remote history so the local repo can
        push cleanly.
        """
        try:
            resp = requests.post(
                f"{self.server_url}/clone-req",
                json={
                    "owner": self.owner,
                    "project": self.project,
                    "topic": self.topic,
                    "new_pub_key": self._public_key_b64(),
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if not resp.ok:
            raise StudyServerError(
                f"Failed to adopt existing study ({resp.status_code}): {resp.text}"
            )

        data = resp.json()
        self._uuid = data["uuid"]
        self._gitlab_url = data.get("gitlab_url")
        self._save_metadata()
        _log(verbose, f"Adopted. uuid={self._uuid}")

        # Pull remote history so subsequent push is a fast-forward
        if self._gitlab_url is not None:
            _log(verbose, "Pulling remote history...")
            remote = self._authed_remote_url(data["gitlab_url"], data["token"])
            try:
                self._git_run("fetch", remote, "main", capture_output=True)
                self._git_run(
                    "merge", "FETCH_HEAD", "--allow-unrelated-histories",
                    "-m", "Merge remote history",
                )
            except StudyGitError:
                # Remote may be empty (never pushed) — that's fine
                pass

    @property
    def uuid(self) -> str | None:
        """The UUID assigned by the meta-server, or None if not yet registered."""
        return self._uuid

    @property
    def is_registered(self) -> bool:
        """Whether this study has been registered with the server."""
        return self._uuid is not None

    def push(self, branch: str = "main", *, verbose: bool = False):
        """Push the local git repo to GitLab via the meta-server.

        Automatically registers the study if it hasn't been registered yet.
        """
        if not self.is_registered:
            self.register(verbose=verbose)
        self._check_git_clean()
        _log(verbose, "Requesting push token...")
        token_data = self._request_token("push")
        if self._gitlab_url is None:
            self._gitlab_url = token_data["gitlab_url"]
            self._save_metadata()
        remote = self._authed_remote_url(token_data["gitlab_url"], token_data["token"])
        _log(verbose, "Pushing...")
        self._git_run("push", remote, f"HEAD:{branch}", capture_output=True)
        _log(verbose, "Push complete.")

    def pull(self, branch: str = "main", *, verbose: bool = False):
        """Pull from GitLab via the meta-server."""
        _log(verbose, "Requesting pull token...")
        token_data = self._request_token("pull")
        remote = self._authed_remote_url(token_data["gitlab_url"], token_data["token"])
        _log(verbose, "Fetching...")
        self._git_run("fetch", remote, branch, capture_output=True)
        self._git_run("merge", "FETCH_HEAD")
        _log(verbose, "Pull complete.")

    def view(self):
        """Open the GitLab repository page in the default browser."""
        import webbrowser

        if self._gitlab_url is None:
            raise StudyError(
                "No GitLab URL available. Push the study first."
            )
        web_url = self._gitlab_url
        if web_url.endswith(".git"):
            web_url = web_url[:-4]
        webbrowser.open(web_url)

    def recover(self, recovery_code: str, *, verbose: bool = False):
        """Recover access by replacing the keypair using a recovery code."""
        if self._uuid is None:
            raise StudyNotRegisteredError(
                "Study is not registered. Cannot recover without a UUID."
            )

        _log(verbose, "Generating new keypair...")
        new_key = Ed25519PrivateKey.generate()
        new_pub_bytes = new_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        new_pub_b64 = base64.urlsafe_b64encode(new_pub_bytes).rstrip(b"=").decode()

        url = f"{self.server_url}/recover"
        body = {
            "uuid": self._uuid,
            "recovery_code": recovery_code,
            "new_pub_key": new_pub_b64,
        }

        _log(verbose, "Sending recovery request...")
        try:
            resp = requests.post(url, json=body, timeout=30)
        except requests.RequestException as exc:
            raise StudyServerError(f"Failed to contact server: {exc}")

        if resp.status_code == 401:
            raise StudyAuthError("Recovery code is invalid or already used.")
        if not resp.ok:
            raise StudyServerError(
                f"Recovery failed ({resp.status_code}): {resp.text}"
            )

        self._private_key = new_key
        if recovery_code in self._recovery_codes:
            self._recovery_codes.remove(recovery_code)
        self._save_metadata()
        _log(verbose, "Recovery complete. New keypair active.")

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
    # Git helpers
    # ------------------------------------------------------------------

    def _git_run(self, *args, capture_output=True) -> subprocess.CompletedProcess:
        """Run a git command in the study directory."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.path,
                check=True,
                capture_output=capture_output,
                text=True,
            )
            return result
        except subprocess.CalledProcessError as exc:
            raise StudyGitError(
                f"git {' '.join(args)} failed: {exc.stderr or exc.stdout or str(exc)}"
            )

    def _check_git_clean(self):
        """Raise StudyGitError if the working tree has untracked or uncommitted changes."""
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
        """Get the default server URL from config or fallback."""
        try:
            from edsl.config import CONFIG

            return CONFIG.get("EDSL_STUDY_SERVER_URL")
        except Exception:
            return _DEFAULT_SERVER_URL

    # ------------------------------------------------------------------
    # Base abstract method implementations
    # ------------------------------------------------------------------

    def to_dict(self, add_edsl_version=True) -> dict:
        """Serialize to dict. Does NOT include the private key."""
        d = {
            "name": self.name,
            "owner": self.owner,
            "project": self.project,
            "topic": self.topic,
            "directory_location": self._directory_location,
            "server_url": self.server_url,
            "uuid": self._uuid,
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Study"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Study":
        """Reconstruct a Study from a dict. Reloads .study.json if the directory exists."""
        return cls(
            name=d["name"],
            owner=d.get("owner"),
            project=d.get("project"),
            topic=d.get("topic"),
            directory_location=d.get("directory_location"),
            server_url=d.get("server_url"),
        )

    @staticmethod
    def example() -> "Study":
        """Create an example Study in a temporary directory."""
        return Study(
            "example_study",
            owner="test",
            project="test",
            topic="v1",
        )

    def code(self) -> str:
        """Return Python code that recreates this Study."""
        parts = [f"    name={self.name!r}"]
        if self.owner is not None:
            parts.append(f"    owner={self.owner!r}")
        if self.project is not None:
            parts.append(f"    project={self.project!r}")
        if self.topic is not None:
            parts.append(f"    topic={self.topic!r}")
        parts.append(f"    directory_location={self._directory_location!r}")
        parts.append(f"    server_url={self.server_url!r}")
        args = ",\n".join(parts)
        return f"from edsl.study import Study\nstudy = Study(\n{args},\n)"

    def _eval_repr_(self) -> str:
        parts = [f"name={self.name!r}"]
        if self.owner is not None:
            parts.append(f"owner={self.owner!r}")
        if self.project is not None:
            parts.append(f"project={self.project!r}")
        if self.topic is not None:
            parts.append(f"topic={self.topic!r}")
        return f"Study({', '.join(parts)})"

    def _summary_repr(self) -> str:
        """Rich-formatted summary."""
        from rich.table import Table
        from rich.console import Console
        import io

        table = Table(title="Study", show_header=True)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("name", self.name or "(not set)")
        table.add_row("owner", self.owner or "(not set)")
        table.add_row("project", self.project or "(not set)")
        table.add_row("topic", self.topic or "(not set)")
        table.add_row("path", self.path)
        table.add_row("server_url", self.server_url)
        table.add_row("uuid", self._uuid or "(not registered)")
        table.add_row("has_private_key", str(self._private_key is not None))

        # Git status
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
