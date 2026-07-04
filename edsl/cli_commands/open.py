"""Open command for the EDSL CLI."""

from __future__ import annotations

import html
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    error,
    load_openable_json,
    output,
    read_package_manifest,
)


def register(app: click.Group) -> None:
    # ---------------------------------------------------------------------------
    # edsl open
    # ---------------------------------------------------------------------------

    @app.command("open")
    @click.argument("path", type=click.Path(exists=True))
    @click.option("--output", "-o", "output_path", default=None, help="Path to write the generated HTML.")
    @click.option("--browser/--no-browser", default=True, help="Open the generated HTML in a browser.")
    def open_object(path, output_path, browser):
        """Open an EDSL object as an HTML artifact in a browser."""
        source_path = Path(path)
        html_path = _html_output_path(source_path, output_path)

        try:
            obj = _load_openable_object(source_path)
            _write_object_html(obj, html_path)
        except SystemExit:
            raise
        except Exception as e:
            error(
                "OPEN_ERROR",
                f"Failed to render {path} as HTML: {e}",
                suggestion="Use a saved Survey, AgentList, or Jobs JSON file, or a supported .ep package.",
                exit_code=EXIT_ERROR,
            )

        url = html_path.resolve().as_uri()
        opened = False
        if browser:
            try:
                opened = bool(webbrowser.open(url))
            except Exception as e:
                error(
                    "BROWSER_ERROR",
                    f"Failed to open browser: {e}",
                    suggestion=f"Open this file manually: {html_path}",
                    exit_code=EXIT_ERROR,
                )

        output({
            "source": str(source_path),
            "html_path": str(html_path),
            "url": url,
            "opened": opened,
            "object_type": _openable_object_type(obj),
        })


    def _html_output_path(source_path: Path, output_path: Optional[str]) -> Path:
        if output_path:
            return Path(output_path)
        safe_stem = source_path.name.replace("/", "_")
        handle = tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            prefix=f"edsl-{safe_stem}-",
            suffix=".html",
        )
        handle.close()
        return Path(handle.name)


    def _load_openable_object(path: Path):
        if path.is_dir():
            return _load_openable_package(path)
        if path.suffix == ".ep":
            return _load_openable_package(path)
        return load_openable_json(path)


    def _load_openable_package(path: Path):
        manifest = read_package_manifest(path)
        class_name = manifest.get("edsl_class_name") or manifest.get("object_type")
        if class_name == "Survey":
            from edsl.surveys import Survey

            return Survey.git.open(path)
        if class_name == "AgentList":
            from edsl.agents import AgentList

            return AgentList.git.open(path)
        if class_name == "Jobs":
            from edsl.jobs import Jobs

            return Jobs.git.open(path)
        if class_name == "Results":
            from edsl.results import Results

            return Results.git.open(path)
        if class_name == "ScenarioList":
            from edsl.scenarios import ScenarioList

            return ScenarioList.git.open(path)
        if class_name == "ModelList":
            from edsl.language_models import ModelList

            return ModelList.git.open(path)
        error(
            "UNSUPPORTED_OBJECT",
            f"Object package type does not support HTML rendering: {class_name or 'unknown'}",
            suggestion="Currently supported package types: Survey, AgentList, Jobs, Results, ScenarioList, ModelList.",
            exit_code=EXIT_USAGE,
        )


    def _write_object_html(obj, html_path: Path) -> None:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        renderer = getattr(obj, "to_html", None) or getattr(obj, "html", None)
        if renderer is not None:
            renderer(filename=str(html_path))
        else:
            repr_html = getattr(obj, "_repr_html_", None)
            if repr_html is not None:
                body = repr_html()
            else:
                to_dataset = getattr(obj, "to_dataset", None)
                dataset = to_dataset() if to_dataset is not None else None
                body = dataset._repr_html_() if hasattr(dataset, "_repr_html_") else None
            if body is None:
                error(
                    "UNSUPPORTED_OBJECT",
                    f"Object type does not support HTML rendering: {_openable_object_type(obj)}",
                    exit_code=EXIT_USAGE,
                )
            html_path.write_text(
                _standalone_html_document(
                    title=f"EDSL {_openable_object_type(obj)}",
                    body=body,
                ),
                encoding="utf-8",
            )
        if not html_path.exists():
            error(
                "OPEN_ERROR",
                f"HTML renderer did not create expected file: {html_path}",
                exit_code=EXIT_ERROR,
            )


    def _standalone_html_document(title: str, body: str) -> str:
        return (
            "<!doctype html>\n"
            "<html>\n"
            "<head>\n"
            '  <meta charset="utf-8">\n'
            f"  <title>{html.escape(title)}</title>\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            "</body>\n"
            "</html>\n"
        )


    def _openable_object_type(obj) -> str:
        return getattr(obj, "object_type", type(obj).__name__)
