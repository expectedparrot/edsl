"""Stable validation commands for generated study reports."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import click

from edsl.cli_shared import EXIT_VALIDATION, error, output

ALLOWED_MARKDOWN = {"report.md", "survey.md", "planning.md", "appendix.md"}


class _ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1_count = 0
        self.blockquote_depth = 0
        self.blockquote_text = ""
        self.images: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "h1":
            self.h1_count += 1
        elif tag == "blockquote":
            if self.blockquote_depth == 0:
                self.blockquote_text = ""
            self.blockquote_depth += 1
        elif tag == "img":
            self.images.append(dict(attrs).get("src", ""))

    def handle_endtag(self, tag):
        if tag == "blockquote":
            self.blockquote_depth -= 1
            if self.blockquote_depth == 0 and not self.blockquote_text.strip():
                self.errors.append("Empty blockquote in compiled HTML")

    def handle_data(self, data):
        if self.blockquote_depth:
            self.blockquote_text += data


def check_report(root: Path) -> dict:
    writeup = root / "writeup"
    markdown = writeup / "report.md"
    compiled = writeup / "report.html"
    errors: list[str] = []
    warnings: list[str] = []
    extras = sorted(path.name for path in writeup.glob("*.md") if path.name not in ALLOWED_MARKDOWN)
    if extras:
        errors.append(f"Disallowed markdown files in writeup/: {', '.join(extras)}")
    if not markdown.is_file() or markdown.stat().st_size == 0:
        errors.append("Missing or empty writeup/report.md")
    if not compiled.is_file() or compiled.stat().st_size == 0:
        errors.append("Missing or empty writeup/report.html")
    elif compiled.is_file():
        parser = _ReportParser()
        parser.feed(compiled.read_text(encoding="utf-8"))
        errors.extend(parser.errors)
        if parser.h1_count > 1:
            errors.append(f"Compiled HTML contains {parser.h1_count} H1 headings")
        for source in parser.images:
            if source.startswith("data:"):
                continue
            if not (writeup / source).resolve().is_file():
                errors.append(f"Image not found: {source}")
    if markdown.is_file():
        for number, line in enumerate(markdown.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^>\s*\[.+?\]\s*:", line):
                errors.append(f"Line {number}: blockquote is parsed as a link reference")
    return {
        "root": str(root), "report_markdown": str(markdown), "report_html": str(compiled),
        "errors": errors, "warnings": warnings, "passed": not errors,
    }


def register(report_group: click.Group) -> None:
    @report_group.command("check")
    @click.option("--root", default=".", type=click.Path(file_okay=False))
    def report_check(root: str) -> None:
        """Validate report sources and compiled HTML with bounded diagnostics."""
        result = check_report(Path(root).expanduser().resolve())
        if result["errors"]:
            error(
                "REPORT_CHECK_FAILED", f"Report has {len(result['errors'])} error(s)",
                details=[{"issue": issue} for issue in result["errors"]], exit_code=EXIT_VALIDATION,
            )
        output(result, warnings=result["warnings"])
