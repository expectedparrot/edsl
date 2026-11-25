"""List, search, display, and install the bundled EDSL skills."""

from __future__ import annotations

import json
import posixpath
import re
import shutil
import subprocess
import tempfile
import webbrowser
from pathlib import Path
from urllib.parse import unquote

import click

from edsl.cli_shared import EXIT_NOT_FOUND, EXIT_USAGE, error, output


SKILLS_ROOT = Path(__file__).resolve().parent
_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_LABELED_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".js", ".mjs", ".ts", ".r"}


def _script_paths(skill: dict) -> list[Path]:
    """Return supported script assets in a bundle's scripts directory."""
    scripts_root = skill["path"] / "scripts"
    if not scripts_root.is_dir():
        return []
    bundle_root = skill["path"].resolve()
    return sorted(
        path for path in scripts_root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in _SCRIPT_SUFFIXES
        and path.resolve().is_relative_to(bundle_root)
    )


def _skills() -> list[dict]:
    found = []
    for path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        metadata = match.group(1) if match else ""
        name_match = re.search(r"^name:\s*(\S+)\s*$", metadata, re.M)
        description_match = re.search(r"^description:\s*(.+)$", metadata, re.M)
        tags_match = re.search(r"^tags:\s*\[([^]]*)\]\s*$", metadata, re.M)
        name = name_match.group(1) if name_match else path.parent.name
        description = description_match.group(1).strip().strip("'\"") if description_match else ""
        tags = [tag.strip().strip("'\"") for tag in tags_match.group(1).split(",")] if tags_match else []
        found.append({"name": name, "description": description, "tags": tags, "path": path.parent})
    return found


def _resolve(skill: dict, name: str) -> dict | None:
    return next((item for item in skill["path"].rglob("*") if item.is_file() and item.name == name), None)


def _read_skill_files(skill: dict) -> list[dict]:
    root = skill["path"]
    primary = root / "SKILL.md"
    files = {primary}
    pending = [primary]
    while pending:
        current = pending.pop()
        text = current.read_text(encoding="utf-8")
        for target in _LINK.findall(text):
            if target.startswith(("http://", "https://", "#")):
                continue
            local = (current.parent / target.split("#", 1)[0]).resolve()
            if (
                local.suffix.lower() == ".md"
                and local.is_file()
                and local.is_relative_to(root.resolve())
                and local not in files
            ):
                files.add(local)
                pending.append(local)
    return [{"path": p.relative_to(root).as_posix(), "content": p.read_text(encoding="utf-8")} for p in sorted(files)]


def _searchable_files(skill: dict) -> list[Path]:
    markdown = list(skill["path"].rglob("*.md"))
    return sorted(set(markdown + _script_paths(skill)))


def _find_snippet(skill: dict, query: str, context_lines: int = 1, max_chars: int = 360) -> dict | None:
    """Return the first concise matching passage with its source location."""
    needle = query.casefold()
    if not needle:
        return None
    for path in _searchable_files(skill):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        offset = 0
        if path.name == "SKILL.md" and lines and lines[0].strip() == "---":
            closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
            if closing is not None:
                offset = closing + 1
        for index, line in enumerate(lines):
            if index < offset:
                continue
            if needle in line.casefold():
                start, end = max(0, index - context_lines), min(len(lines), index + context_lines + 1)
                start = max(start, offset)
                passage = " ".join(part.strip() for part in lines[start:end] if part.strip())
                if len(passage) > max_chars:
                    passage = passage[: max_chars - 1].rstrip() + "…"
                label = path.relative_to(skill["path"]).as_posix()
                return {
                    "path": label,
                    "line": start + 1,
                    "text": passage,
                }
    return None


def _anchor_slug(value: str) -> str:
    """Normalize Markdown headings and link fragments to the same HTML slug."""
    value = unquote(value)
    value = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"[`*_~]", "", value).casefold()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def _file_anchor(relative_path: str) -> str:
    return "skill-ref-" + _anchor_slug(relative_path)


def _render_html(name: str, description: str, files: list[dict]) -> Path:
    """Render skill Markdown and linked references to an opened temporary HTML file."""
    if shutil.which("pandoc") is None:
        error("DEPENDENCY_ERROR", "Pandoc is required for HTML skill output.", "Install Pandoc, then retry 'ep skills show <name> --html'.")

    chunks = [f"# {name}\n\n{description}\n"]
    for item in files:
        relative = item["path"]
        anchor = _file_anchor(relative)
        body = item["content"]

        def local_link(match: re.Match) -> str:
            label, target = match.group(1), match.group(2)
            if target.startswith(("http://", "https://", "mailto:")):
                return match.group(0)
            target_path, _, fragment = target.partition("#")
            if target_path:
                target_relative = posixpath.normpath(
                    posixpath.join(posixpath.dirname(relative), target_path)
                )
                target_anchor = _file_anchor(target_relative)
            else:
                target_anchor = anchor
            href = f"#{target_anchor}"
            if fragment:
                href += "-" + _anchor_slug(fragment)
            return f"[{label}]({href})"

        body = _LABELED_LINK.sub(local_link, body)
        # Add a matching local anchor before each reference heading so links with
        # a Markdown heading fragment can target it within the combined page.
        rendered_lines = []
        in_fence = False
        used_heading_slugs: dict[str, int] = {}
        for line in body.splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            heading = None if in_fence else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
            if heading:
                slug = _anchor_slug(heading.group(2))
                count = used_heading_slugs.get(slug, 0)
                used_heading_slugs[slug] = count + 1
                if count:
                    slug = f"{slug}-{count}"
                rendered_lines.append(f'<a id="{anchor}-{slug}"></a>')
            rendered_lines.append(line)
        body = "\n".join(rendered_lines)
        chunks.append(f'<a id="{anchor}"></a>\n\n## {relative}\n\n{body}')

    markdown = "\n\n---\n\n".join(chunks)
    temp = tempfile.NamedTemporaryFile(prefix=f"edsl-skill-{name}-", suffix=".html", delete=False)
    html_path = Path(temp.name)
    temp.close()
    try:
        result = subprocess.run(
            ["pandoc", "--from=gfm", "--to=html5", "--standalone", "--metadata", f"title={name}", "--output", str(html_path)],
            input=markdown,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        html_path.unlink(missing_ok=True)
        error("HTML_RENDER_ERROR", f"Could not run Pandoc: {exc}", "Confirm Pandoc is installed and available on PATH.")
    if result.returncode != 0:
        html_path.unlink(missing_ok=True)
        error("HTML_RENDER_ERROR", result.stderr.strip() or "Pandoc could not render the skill Markdown.", "Check the skill Markdown and Pandoc installation.")
    return html_path


@click.group("skills", invoke_without_command=True)
@click.pass_context
def skills(ctx: click.Context):
    """Discover and install version-matched EDSL skills."""
    if ctx.invoked_subcommand is None:
        output({"commands": ["list", "search", "show", "install"], "help": "Use 'ep skills <command> --help' for details."})


@skills.command("list")
@click.option("--human", is_flag=True, help="Print readable text instead of JSON.")
@click.option("--routing", is_flag=True, help="Include tags, references, scripts, examples, and commands to fetch them.")
def list_skills(human: bool, routing: bool):
    """List bundled EDSL skills, optionally with routing metadata."""
    items = []
    for skill in _skills():
        item = {"name": skill["name"], "description": skill["description"]}
        if routing:
            linked_references = [
                file["path"] for file in _read_skill_files(skill)
                if file["path"] != "SKILL.md" and file["path"].endswith(".md")
            ]
            scripts = [path.relative_to(skill["path"]).as_posix() for path in _script_paths(skill)]
            item.update({
                "tags": skill["tags"],
                "references": linked_references,
                "reference_count": len(linked_references),
                "scripts": scripts,
                "script_count": len(scripts),
                "show_command": f"ep skills show {skill['name']}",
                "reference_commands": {
                    reference: f"ep skills show {skill['name']} --reference {reference}"
                    for reference in linked_references
                },
                "script_commands": {
                    script: f"ep skills show {skill['name']} --script {script}"
                    for script in scripts
                },
            })
        items.append(item)
    if human:
        for item in items:
            click.echo(f"{item['name']} — {item['description']}")
            if routing:
                click.echo(f"  tags: {', '.join(item['tags']) or '(none)'}")
                refs = item["references"]
                click.echo(f"  linked references: {len(refs)}")
                for reference in refs:
                    command = item["reference_commands"][reference]
                    click.echo(f"    - {reference}: {command}")
                click.echo(f"  scripts: {len(item['scripts'])}")
                for script in item["scripts"]:
                    click.echo(f"    - {script}: {item['script_commands'][script]}")
                click.echo(f"  fetch: {item['show_command']}")
    else:
        output({"skills": items})


@skills.command("search")
@click.argument("query")
@click.option("--limit", type=click.IntRange(1, 50), default=10, show_default=True)
@click.option("--human", is_flag=True, help="Print readable text instead of JSON.")
@click.option("--snippets", is_flag=True, help="Include a matching passage with source file and line number.")
def search_skills(query: str, limit: int, human: bool, snippets: bool):
    """Search bundled skill names, descriptions, and text."""
    q = query.casefold().strip()
    ranked = []
    for skill in _skills():
        name, description = skill["name"].casefold(), skill["description"].casefold()
        searchable_files = _searchable_files(skill)
        body = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in searchable_files).casefold()
        if q == name:
            rank, match = 0, "exact_name"
        elif q in name:
            rank, match = 1, "name"
        elif q in description:
            rank, match = 2, "description"
        elif q in body:
            rank, match = 3, "content"
        else:
            continue
        row = {"name": skill["name"], "description": skill["description"], "match": match}
        if snippets:
            row["snippet"] = _find_snippet(skill, q)
        ranked.append((rank, skill["name"], row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    results = [row for _, _, row in ranked[:limit]]
    if human:
        if not results:
            click.echo("No matching EDSL skills found.")
        for item in results:
            click.echo(f"{item['name']} [{item['match']}] — {item['description']}")
            if item.get("snippet"):
                snippet = item["snippet"]
                click.echo(f"  {snippet['path']}:{snippet['line']}: {snippet['text']}")
    else:
        output({"query": query, "results": results})


@skills.command("show")
@click.argument("name")
@click.option("--reference", "reference_path", help="Return one linked reference by its bundle-relative path.")
@click.option("--script", "script_path", help="Return one bundled script by its bundle-relative path.")
@click.option("--human", is_flag=True, help="Print fetched content as readable text instead of JSON.")
@click.option("--html", "html_output", is_flag=True, help="Render linked skill Markdown to a temporary HTML file and open it.")
def show_skill(name: str, reference_path: str | None, script_path: str | None, human: bool, html_output: bool):
    """Show a skill, linked reference, or bundled script."""
    skill = next((s for s in _skills() if s["name"] == name), None)
    if skill is None:
        error("SKILL_NOT_FOUND", f"No bundled skill named '{name}'.", "Run 'ep skills list' or 'ep skills search <query>'.", EXIT_NOT_FOUND)
    if human and html_output:
        error("USAGE_ERROR", "--human and --html cannot be used together.", "Choose one output format.", EXIT_USAGE)
    selected_options = [reference_path, script_path]
    if sum(value is not None for value in selected_options) > 1:
        error("USAGE_ERROR", "--reference and --script cannot be combined.", "Choose one skill resource.", EXIT_USAGE)
    if script_path is not None:
        scripts = {
            path.relative_to(skill["path"]).as_posix(): path
            for path in _script_paths(skill)
        }
        script = scripts.get(script_path)
        if script is None:
            available = sorted(scripts)
            error(
                "SCRIPT_NOT_FOUND",
                f"No bundled script '{script_path}' in skill '{name}'.",
                "Use 'ep skills list --routing' to see fetchable scripts.",
                EXIT_NOT_FOUND,
                details=[{"available_scripts": available}],
            )
        content = script.read_text(encoding="utf-8")
        if html_output:
            error("USAGE_ERROR", "--html cannot render a script file.", "Fetch the script as text or use --html for a skill/reference.", EXIT_USAGE)
        if human:
            click.echo(content, nl=not content.endswith("\n"))
        else:
            output({"name": name, "script": script_path, "content": content})
        return
    files = _read_skill_files(skill)
    if reference_path is not None:
        selected = next((item for item in files if item["path"] == reference_path), None)
        if selected is None:
            available = [item["path"] for item in files if item["path"] != "SKILL.md"]
            error(
                "REFERENCE_NOT_FOUND",
                f"No linked reference '{reference_path}' in skill '{name}'.",
                "Use 'ep skills list --routing' to see fetchable reference commands.",
                EXIT_NOT_FOUND,
                details=[{"available_references": available}],
            )
        files = [selected]
    data = {
        "name": skill["name"],
        "description": skill["description"],
        "files": files,
    }
    if reference_path is not None:
        data["reference"] = reference_path
    if html_output:
        html_files = list(files)
        if reference_path is None:
            for script in _script_paths(skill):
                relative = script.relative_to(skill["path"]).as_posix()
                language = script.suffix.lower().lstrip(".")
                content = script.read_text(encoding="utf-8")
                html_files.append({
                    "path": relative,
                    "content": f"```{language}\n{content.rstrip()}\n```",
                })
        html_path = _render_html(skill["name"], skill["description"], html_files)
        opened = webbrowser.open_new_tab(html_path.as_uri())
        if opened:
            click.echo(f"Opened skill documentation: {html_path}")
        else:
            click.echo(f"Saved skill documentation: {html_path}\nCould not open a browser automatically; open the file path above.")
    elif human:
        click.echo(f"# {skill['name']}\n\n{skill['description']}")
        for item in files:
            click.echo(f"\n---\n\n## {item['path']}\n\n{item['content'].rstrip()}")
    else:
        output(data)


@skills.command("install")
@click.option("--target", required=True, type=click.Path(path_type=Path, file_okay=False), help="Directory in which to install each skill bundle.")
@click.option("--human", is_flag=True, help="Print readable text instead of JSON.")
def install_skills(target: Path, human: bool):
    """Install or update bundled skill files under TARGET."""
    target.mkdir(parents=True, exist_ok=True)
    installed = []
    for skill in _skills():
        destination = target / skill["name"]
        if destination.exists():
            if not destination.is_dir():
                error("USAGE_ERROR", f"Cannot install over non-directory: {destination}", "Choose a directory target without conflicting files.", EXIT_USAGE)
            shutil.copytree(skill["path"], destination, dirs_exist_ok=True)
        else:
            shutil.copytree(skill["path"], destination)
        installed.append(str(destination))
    if human:
        click.echo(f"Installed {len(installed)} skills into {target.resolve()}")
        for path in installed:
            click.echo(f"- {path}")
    else:
        output({"target": str(target.resolve()), "installed": installed})
