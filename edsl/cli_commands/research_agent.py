"""Read and download a user's Research Agent sessions."""

from __future__ import annotations

import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote

import click
import requests

from edsl.cli_shared import (
    EXIT_AUTH,
    EXIT_NOT_FOUND,
    EXIT_REMOTE,
    EXIT_USAGE,
    error,
    output,
    private_output,
)


_SESSION_ID = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _coop_client():
    from edsl.coop import Coop

    client = Coop()
    if not client.has_api_key:
        error(
            "AUTH_ERROR",
            "Expected Parrot API key is not configured.",
            suggestion="Run 'ep auth login' or set EXPECTED_PARROT_API_KEY.",
            exit_code=EXIT_AUTH,
        )
    return client


def _get_json(client, endpoint: str, params: dict | None = None) -> dict:
    try:
        response = client.research_agent_get(endpoint, params=params)
    except requests.RequestException as exc:
        error(
            "REMOTE_ERROR",
            f"Could not reach the Research Agent service: {exc}",
            suggestion="Check your network connection and Expected Parrot URL.",
            exit_code=EXIT_REMOTE,
        )
    _check_response(response)
    try:
        data = response.json()
    except ValueError:
        error(
            "REMOTE_ERROR",
            "Research Agent returned an invalid JSON response.",
            suggestion="Retry later or contact Expected Parrot support.",
            exit_code=EXIT_REMOTE,
        )
    if not isinstance(data, dict):
        error(
            "REMOTE_ERROR",
            "Research Agent returned an unexpected response shape.",
            suggestion="Retry later or contact Expected Parrot support.",
            exit_code=EXIT_REMOTE,
        )
    return data


def _check_response(response: requests.Response) -> None:
    if response.status_code in (401, 403):
        error(
            "AUTH_ERROR",
            "The API key is invalid or does not have access to this Research Agent session.",
            suggestion="Check 'ep auth status' and confirm that the session belongs to your account.",
            exit_code=EXIT_AUTH,
        )
    if response.status_code == 404:
        error(
            "SESSION_NOT_FOUND",
            "Research Agent session or file was not found.",
            suggestion="Check the session id and file path.",
            exit_code=EXIT_NOT_FOUND,
        )
    if not response.ok:
        error(
            "REMOTE_ERROR",
            f"Research Agent request failed ({response.status_code}).",
            suggestion="Retry later or contact Expected Parrot support.",
            exit_code=EXIT_REMOTE,
        )


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID.fullmatch(session_id):
        error(
            "USAGE_ERROR",
            f"Invalid Research Agent session UUID: {session_id}",
            suggestion="Pass a session UUID.",
            exit_code=EXIT_USAGE,
        )


def _extract_session_archive(archive_path: Path, output_dir: Path) -> int:
    """Safely extract a session ZIP into a new owner-only directory."""
    if os.path.lexists(output_dir):
        error(
            "USAGE_ERROR",
            f"Output directory already exists: {output_dir}",
            suggestion="Choose a new directory so existing files are never overwritten.",
            exit_code=EXIT_USAGE,
        )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(mode=0o700)
    root = output_dir.resolve()
    extracted_files = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                name = info.filename
                posix_path = PurePosixPath(name)
                windows_path = PureWindowsPath(name)
                if (
                    not name
                    or chr(92) in name
                    or posix_path.is_absolute()
                    or windows_path.is_absolute()
                    or windows_path.drive
                    or ".." in posix_path.parts
                ):
                    raise ValueError("Archive contains an unsafe file path.")

                target = root.joinpath(*posix_path.parts)
                if not target.resolve().is_relative_to(root):
                    raise ValueError("Archive path escapes the output directory.")

                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("Archive contains a symbolic link.")
                if info.is_dir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=True)
                    continue
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ValueError("Archive contains a non-regular file.")

                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                file_descriptor = os.open(
                    target,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(file_descriptor, "wb") as destination:
                    with archive.open(info) as source:
                        shutil.copyfileobj(source, destination, length=1024 * 64)
                extracted_files += 1
    except Exception:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise
    return extracted_files


def register(research_agent: click.Group) -> None:
    @research_agent.command("sessions")
    @click.option(
        "--filter",
        "session_filter",
        type=click.Choice(["active", "all", "archived"]),
        default="all",
        show_default=True,
        help="Which sessions to list.",
    )
    @click.option("--page", type=click.IntRange(min=1), default=1, show_default=True)
    @click.option(
        "--page-size",
        type=click.IntRange(min=1, max=200),
        default=50,
        show_default=True,
        help="Maximum number of sessions to return.",
    )
    def sessions(session_filter: str, page: int, page_size: int) -> None:
        """List one page of your Research Agent sessions."""
        client = _coop_client()
        output(
            _get_json(
                client,
                "sessions",
                {
                    "filter": session_filter,
                    "page": page,
                    "page_size": page_size,
                },
            )
        )

    @research_agent.command("files")
    @click.argument("session_id")
    def files(session_id: str) -> None:
        """List files available in a Research Agent session."""
        _validate_session_id(session_id)
        client = _coop_client()
        output(_get_json(client, f"sessions/{session_id}/files"))

    @research_agent.command("session")
    @click.argument("session_id")
    @click.option(
        "--section",
        type=click.Choice(["metadata", "history", "shares", "files"]),
        default=None,
        help="Return one section instead of the combined session view.",
    )
    def session(session_id: str, section: str | None) -> None:
        """Show session metadata, conversation, shared links, and files."""
        _validate_session_id(session_id)
        client = _coop_client()
        if section:
            data = _get_json(client, f"sessions/{session_id}/{section}")
            if section == "shares":
                _add_share_urls(data, client)
            output(data)
            return

        data = {
            "session_id": session_id,
            "metadata": _get_json(client, f"sessions/{session_id}/metadata"),
            "history": _get_json(client, f"sessions/{session_id}/history"),
            "shares": _get_json(client, f"sessions/{session_id}/shares"),
            "files": _get_json(client, f"sessions/{session_id}/files"),
        }
        _add_share_urls(data["shares"], client)
        output(data)

    @research_agent.command("download")
    @click.argument("session_id")
    @click.option("--file", "file_path", default=None, help="Relative path of one session file.")
    @click.option("--zip", "zip_archive", is_flag=True, help="Download the complete session archive.")
    @click.option("--output", "output_path", required=True, type=click.Path(), help="Destination path.")
    def download(session_id: str, file_path: str | None, zip_archive: bool, output_path: str) -> None:
        """Download a session file or its complete archive."""
        _validate_session_id(session_id)
        if bool(file_path) == bool(zip_archive):
            error(
                "USAGE_ERROR",
                "Choose exactly one of --file or --zip.",
                suggestion="Use --file PATH or --zip.",
                exit_code=EXIT_USAGE,
            )
        if file_path is not None:
            if file_path.startswith("/") or ".." in file_path.split("/"):
                error(
                    "USAGE_ERROR",
                    "Session file path must stay inside the session.",
                    suggestion="Use a relative path from the session file listing.",
                    exit_code=EXIT_USAGE,
                )
            encoded_path = "/".join(quote(part, safe="") for part in file_path.split("/"))
            endpoint = f"sessions/{session_id}/files/{encoded_path}"
            kind = "file"
        else:
            endpoint = f"sessions/{session_id}/download-zip"
            kind = "zip"

        client = _coop_client()
        try:
            response = client.research_agent_get(endpoint, stream=True)
        except requests.RequestException as exc:
            error(
                "REMOTE_ERROR",
                f"Could not reach the Research Agent service: {exc}",
                suggestion="Check your network connection and Expected Parrot URL.",
                exit_code=EXIT_REMOTE,
            )
        with response:
            _check_response(response)
            with private_output(output_path) as temp_path:
                total_bytes = 0
                with temp_path.open("wb") as target:
                    try:
                        for chunk in response.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                target.write(chunk)
                                total_bytes += len(chunk)
                    except requests.RequestException as exc:
                        error(
                            "REMOTE_ERROR",
                            f"Research Agent download interrupted: {exc}",
                            suggestion="Retry the download.",
                            exit_code=EXIT_REMOTE,
                        )
        output(
            {
                "session_id": session_id,
                "kind": kind,
                "file": file_path,
                "bytes": total_bytes,
                "output": str(Path(output_path)),
            }
        )


    @research_agent.command("pull")
    @click.argument("session_id")
    @click.option(
        "--output",
        "output_dir",
        required=True,
        type=click.Path(path_type=Path),
        help="New directory where the session files and chat history will be extracted.",
    )
    def pull(session_id: str, output_dir: Path) -> None:
        """Pull a complete session, including files and chat_history.md, locally."""
        _validate_session_id(session_id)
        client = _coop_client()
        try:
            response = client.research_agent_get(
                f"sessions/{session_id}/download-zip",
                stream=True,
            )
        except requests.RequestException as exc:
            error(
                "REMOTE_ERROR",
                f"Could not reach the Research Agent service: {exc}",
                suggestion="Check your network connection and Expected Parrot URL.",
                exit_code=EXIT_REMOTE,
            )

        archive_bytes = 0
        with response:
            _check_response(response)
            with tempfile.TemporaryDirectory(prefix="ep-session-pull-") as temp_dir:
                archive_path = Path(temp_dir) / "session.zip"
                archive_descriptor = os.open(
                    archive_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(archive_descriptor, "wb") as archive_file:
                    try:
                        for chunk in response.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                archive_file.write(chunk)
                                archive_bytes += len(chunk)
                    except requests.RequestException as exc:
                        error(
                            "REMOTE_ERROR",
                            f"Research Agent download interrupted: {exc}",
                            suggestion="Retry the pull.",
                            exit_code=EXIT_REMOTE,
                        )
                try:
                    extracted_files = _extract_session_archive(
                        archive_path, output_dir.expanduser()
                    )
                except (OSError, ValueError, zipfile.BadZipFile) as exc:
                    error(
                        "REMOTE_ERROR",
                        f"Could not safely extract the Research Agent session: {exc}",
                        suggestion="Retry the pull or contact Expected Parrot support.",
                        exit_code=EXIT_REMOTE,
                    )

        output(
            {
                "session_id": session_id,
                "kind": "full_session",
                "files_extracted": extracted_files,
                "archive_bytes": archive_bytes,
                "output": str(output_dir.expanduser()),
            }
        )


def _add_share_urls(data: dict, client) -> None:
    from edsl.config import CONFIG

    public_base = str(CONFIG.EXPECTED_PARROT_URL).rstrip("/")
    for share in data.get("shares", []):
        token = share.get("share_token")
        if token:
            share["url"] = f"{public_base}/research-agent/share/{token}"
