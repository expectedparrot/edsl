"""Open a survey package in Coopr's collaborative editor."""

from __future__ import annotations

import re
import webbrowser
from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_REMOTE,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    load_git_object,
    output,
)


def register(app: click.Group) -> None:
    @app.command("edit")
    @click.argument("path", type=click.Path(exists=True, path_type=Path))
    @click.option(
        "--browser/--no-browser",
        default=True,
        help="Open the collaborative editor in a browser.",
    )
    def edit_survey(path: Path, browser: bool) -> None:
        """Push a survey package to Coopr and open its collaborative editor."""
        if not (path.is_dir() or path.suffix == ".ep"):
            error(
                "USAGE_ERROR",
                f"Edit requires a git-backed .ep package: {path}",
                suggestion="Save the Survey as a .ep package, then run 'ep edit <path>'.",
                exit_code=EXIT_USAGE,
            )

        try:
            from edsl.config import CONFIG

            obj = load_git_object(path)
            if type(obj).__name__ != "Survey":
                error(
                    "UNSUPPORTED_OBJECT",
                    f"'ep edit' supports Survey packages; received {type(obj).__name__}.",
                    suggestion="Pass a Survey .ep package.",
                    exit_code=EXIT_VALIDATION,
                )

            had_coop_info = obj.git._read_coop_info() is not None
            pushed = obj.git.coop_push(
                expected_parrot_url=CONFIG.EXPECTED_PARROT_URL,
                message=f"Push {path.name} before collaborative editing",
            )
            coop_info = pushed.get("coop_info") or {}
            survey_uuid = coop_info.get("uuid")
            if not survey_uuid:
                # Older metadata may contain only a content URL. Extract a UUID
                # when possible; the collab route requires the UUID path form.
                identifier = obj.git._coop_identifier(coop_info)
                match = re.search(
                    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                    identifier,
                )
                survey_uuid = match.group(0) if match else None
            if not survey_uuid:
                error(
                    "REMOTE_ERROR",
                    "Coopr accepted the survey, but its UUID was missing from the response.",
                    suggestion="Run 'ep metadata <path>' to inspect the remote link, then try again.",
                    exit_code=EXIT_REMOTE,
                )

            base_url = str(CONFIG.EXPECTED_PARROT_URL).rstrip("/")
            editor_url = f"{base_url}/collab/s/{survey_uuid}/"
            opened = False
            if browser:
                try:
                    opened = bool(webbrowser.open(editor_url))
                except Exception as exc:
                    error(
                        "BROWSER_ERROR",
                        f"Survey was pushed, but the browser could not be opened: {exc}",
                        suggestion=f"Open this URL manually: {editor_url}",
                        exit_code=EXIT_REMOTE,
                    )

            output(
                {
                    "object_type": "Survey",
                    "source": str(path),
                    "operation": "patch" if had_coop_info else "push",
                    "uuid": str(survey_uuid),
                    "editor_url": editor_url,
                    "browser_opened": opened,
                    "next_step": "After saving in Coopr, run 'ep pull <path>' to sync the survey back to this package.",
                }
            )
        except SystemExit:
            raise
        except Exception as exc:
            error(
                "EDIT_ERROR",
                str(exc),
                suggestion="Check the package path, Expected Parrot authentication, and remote service status.",
                exit_code=EXIT_REMOTE,
            )
