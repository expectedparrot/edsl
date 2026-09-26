"""Package utility commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.base.git_package import ARCHIVE_PACKAGE_SUFFIX, unpack_package_archive
from edsl.cli_shared import EXIT_ERROR, error, output, read_package_manifest


def register(app: click.Group) -> None:
    def _unpack_package(path: str) -> None:
        """Extract a .ep package archive into a temporary directory."""
        package_path = Path(path)
        try:
            manifest = read_package_manifest(package_path)
            extract_path = unpack_package_archive(
                package_path,
                package_suffix=ARCHIVE_PACKAGE_SUFFIX,
            )
            output(
                {
                    "package": str(package_path),
                    "path": str(extract_path),
                    "temp": True,
                    "object_type": manifest.get("edsl_class_name")
                    or manifest.get("object_type"),
                    "manifest": manifest,
                    "next_step": f"cd {extract_path}",
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "UNPACK_ERROR",
                f"Failed to unpack package: {e}",
                suggestion="Pass a valid .ep git-backed EDSL package archive.",
                exit_code=EXIT_ERROR,
            )

    @app.command("unpack")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    def unpack(path: str) -> None:
        """Unpack a .ep package into a temporary inspection directory.

        \b
        Examples:
          ep unpack survey.ep
          ep unpack agents.ep
          cd $(ep unpack survey.ep | jq -r .data.path)
        """
        _unpack_package(path)

    @app.command("unzip")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    def unzip(path: str) -> None:
        """Alias for `ep unpack`.

        \b
        Examples:
          ep unzip survey.ep
          ep unzip results.ep
        """
        _unpack_package(path)
