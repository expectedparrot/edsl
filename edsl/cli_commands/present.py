"""Present a local artifact through agent host integrations."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import EXIT_NOT_FOUND, EXIT_USAGE, error, output


def register(app: click.Group) -> None:
    @app.command("present")
    @click.argument("path")
    @click.option("--title", default=None, help="Human-readable label for the artifact.")
    def present(path: str, title: str | None) -> None:
        """Validate and present a local file to the user."""
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            error(
                "PRESENTATION_FILE_NOT_FOUND",
                f"Presentation file does not exist: {candidate}",
                exit_code=EXIT_NOT_FOUND,
            )
        size = candidate.stat().st_size
        if size == 0:
            error(
                "PRESENTATION_FILE_EMPTY",
                f"Presentation file is empty: {candidate}",
                exit_code=EXIT_USAGE,
            )
        clean_title = " ".join((title or candidate.name).replace("\t", " ").split())
        marker = f"PRESENT_FILE:{candidate}\t{clean_title}"
        output({
            "path": str(candidate),
            "title": clean_title,
            "size": size,
            "presentation_marker": marker,
        })
