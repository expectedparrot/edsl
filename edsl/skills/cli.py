"""List, search, display, and install the bundled EDSL skills."""

from __future__ import annotations

import json
import math
import posixpath
import re
import shutil
import subprocess
import tempfile
import webbrowser
from collections import Counter
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

import click

from edsl.cli_shared import EXIT_NOT_FOUND, EXIT_USAGE, error, output


SKILLS_ROOT = Path(__file__).resolve().parent
EXAMPLES_ROOT = SKILLS_ROOT.parent / "examples"
EXAMPLES_MANIFEST = SKILLS_ROOT / "examples.json"
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


def _example_paths(skill: dict) -> dict[str, Path]:
    """Return example sources explicitly assigned to this skill."""
    if not EXAMPLES_MANIFEST.is_file():
        return {}
    manifest = json.loads(EXAMPLES_MANIFEST.read_text(encoding="utf-8"))
    result: dict[str, Path] = {}
    root = EXAMPLES_ROOT.resolve()
    for directory in manifest.get(skill["name"], []):
        base = (EXAMPLES_ROOT / directory).resolve()
        if not base.is_relative_to(root) or not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.name == "__init__.py":
                continue
            if path.suffix.lower() not in {".py", ".md"}:
                continue
            resolved = path.resolve()
            if resolved.is_relative_to(root):
                result[resolved.relative_to(root).as_posix()] = resolved
    return result


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
    examples = list(_example_paths(skill).values())
    return sorted(set(markdown + _script_paths(skill) + examples))


def _words(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[^\W_]+", text.casefold()))


class _SearchQuery:
    """Match English word forms within a single catalog field or source line."""

    def __init__(self, text: str):
        from snowballstemmer import stemmer

        self.text = text.casefold().strip()
        self.words = _words(text)
        self.keywords = set(self.words) - {"a", "an", "and", "for", "in", "of", "the", "to", "with"}
        # One stemmer and vocabulary cache per search, shared across all documents.
        self.stem = lru_cache(maxsize=8192)(stemmer("english").stemWord)
        self.stems = {self.stem(word) for word in self.keywords}

    def matches_words(self, words: tuple[str, ...]) -> bool:
        return bool(self.stems) and self.stems.issubset(self.stem(word) for word in words)

    def matches(self, text: str) -> bool:
        return self.matches_words(_words(text))


def _find_snippet(skill: dict, query: _SearchQuery, *, literal: bool, context_lines: int = 1, max_chars: int = 360) -> dict | None:
    """Return the first concise matching passage with its source location."""
    if not query.text:
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
            if query.text in line.casefold() or (not literal and query.matches(line)):
                start, end = max(0, index - context_lines), min(len(lines), index + context_lines + 1)
                start = max(start, offset)
                passage = " ".join(part.strip() for part in lines[start:end] if part.strip())
                if len(passage) > max_chars:
                    passage = passage[: max_chars - 1].rstrip() + "…"
                try:
                    label = path.relative_to(skill["path"]).as_posix()
                except ValueError:
                    label = f"edsl/examples/{path.relative_to(EXAMPLES_ROOT).as_posix()}"
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
            examples = sorted(_example_paths(skill))
            item.update({
                "tags": skill["tags"],
                "references": linked_references,
                "reference_count": len(linked_references),
                "scripts": scripts,
                "script_count": len(scripts),
                "examples": examples,
                "example_count": len(examples),
                "show_command": f"ep skills show {skill['name']}",
                "reference_commands": {
                    reference: f"ep skills show {skill['name']} --reference {reference}"
                    for reference in linked_references
                },
                "script_commands": {
                    script: f"ep skills show {skill['name']} --script {script}"
                    for script in scripts
                },
                "example_commands": {
                    example: f"ep skills show {skill['name']} --example {example}"
                    for example in examples
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
                click.echo(f"  examples: {len(item['examples'])}")
                for example in item["examples"]:
                    click.echo(f"    - {example}: {item['example_commands'][example]}")
                click.echo(f"  fetch: {item['show_command']}")
    else:
        output({"skills": items})


def _partial_package_matches(query: _SearchQuery, catalog: list[dict]) -> list[dict]:
    """Rank multi-term overlap across package fields by TF-IDF cosine similarity."""
    # "EDSL" identifies the catalog as a whole and adds no evidence of intent.
    terms = query.stems - {"edsl"}
    if len(terms) < 2:
        return []
    documents = []
    frequencies = Counter()
    for package in catalog:
        fields = [package["name"], *package["methods"], package["description"]]
        counts = Counter()
        same_field_match = False
        for field in fields:
            stems = [query.stem(word) for word in _words(field)]
            counts.update(stems)
            if len(terms.intersection(stems)) >= 2:
                same_field_match = True
        if same_field_match:
            documents.append((package, counts))
        frequencies.update(counts.keys())
    idf = {
        term: 1 + math.log((1 + len(catalog)) / (1 + freq))
        for term, freq in frequencies.items()
    }
    ranked = []
    for package, counts in documents:
        overlap = terms.intersection(counts)
        if len(overlap) * 2 < len(terms):
            continue
        weights = {term: (1 + math.log(count)) * idf[term] for term, count in counts.items()}
        # Query length is constant across candidates, so its norm cancels for ranking.
        score = sum(weights[term] * idf[term] for term in sorted(overlap))
        norm = math.sqrt(sum(weight * weight for weight in weights.values()))
        ranked.append((score / norm, package))
    return [package for _, package in sorted(ranked, key=lambda item: (-item[0], item[1]["name"]))]


def _package_matches(query: _SearchQuery, limit: int) -> list[dict]:
    """Search the public directory snapshot shipped with this EDSL version."""
    if not query.keywords:
        return []
    catalog = json.loads((SKILLS_ROOT / "packages.json").read_text(encoding="utf-8"))
    ranked = []
    for package in catalog:
        methods = [_words(method) for method in package["methods"]]
        description = _words(package["description"])
        if query.words == _words(package["name"]):
            rank = 0
        elif query.words in methods:
            rank = 1
        elif any(query.keywords.issubset(method) for method in methods):
            rank = 2
        elif query.keywords.issubset(description):
            rank = 3
        elif any(query.matches_words(method) for method in methods):
            rank = 4
        elif query.matches_words(description):
            rank = 5
        else:
            continue
        ranked.append((rank, package["name"], package))
    matches = [package for _, _, package in sorted(ranked, key=lambda item: item[:2])]
    if not matches:
        matches = _partial_package_matches(query, catalog)
    return [{**package, "kind": "external_package"} for package in matches[:limit]]


@skills.command("search")
@click.argument("query")
@click.option("--limit", type=click.IntRange(1, 50), default=10, show_default=True,
              help="Maximum matches in each of the skill and package lists.")
@click.option("--human", is_flag=True, help="Print readable text instead of JSON.")
@click.option("--snippets", is_flag=True, help="Include a matching passage with source file and line number.")
def search_skills(query: str, limit: int, human: bool, snippets: bool):
    """Search bundled skills and public research packages by name or method."""
    search = _SearchQuery(query)
    q = search.text
    ranked = []
    for skill in _skills():
        name, description = skill["name"].casefold(), skill["description"].casefold()
        searchable_files = _searchable_files(skill)
        body = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in searchable_files).casefold()
        if q == name:
            rank, match = 0, "exact_name"
        elif q in name:
            rank, match = 1, "name"
        elif search.matches(name):
            rank, match = 2, "name"
        elif q in description:
            rank, match = 3, "description"
        elif search.matches(description):
            rank, match = 4, "description"
        elif q in body:
            rank, match = 5, "content"
        elif any(search.matches(line) for line in body.splitlines()):
            rank, match = 6, "content"
        else:
            continue
        row = {"name": skill["name"], "description": skill["description"], "match": match}
        if snippets:
            row["snippet"] = _find_snippet(skill, search, literal=q in body)
        ranked.append((rank, skill["name"], row))
    ranked.sort(key=lambda item: (item[0], item[1]))
    results = [row for _, _, row in ranked[:limit]]
    packages = _package_matches(search, limit)
    if human:
        if not results and not packages:
            click.echo("No matching EDSL skills or research packages found.")
        for item in results:
            click.echo(f"{item['name']} [{item['match']}] — {item['description']}")
            if item.get("snippet"):
                snippet = item["snippet"]
                click.echo(f"  {snippet['path']}:{snippet['line']}: {snippet['text']}")
        for package in packages:
            click.echo(f"{package['name']} [external package] — {package['description']}")
            click.echo(f"  README: {package['readme_url']}")
    else:
        output({"query": query, "results": results, "packages": packages})


@skills.command("show")
@click.argument("name")
@click.option("--reference", "reference_path", help="Return one linked reference by its bundle-relative path.")
@click.option("--script", "script_path", help="Return one bundled script by its bundle-relative path.")
@click.option("--example", "example_path", help="Return one version-matched EDSL example by its examples-relative path.")
@click.option("--human", is_flag=True, help="Print fetched content as readable text instead of JSON.")
@click.option("--html", "html_output", is_flag=True, help="Render linked skill Markdown to a temporary HTML file and open it.")
def show_skill(name: str, reference_path: str | None, script_path: str | None, example_path: str | None, human: bool, html_output: bool):
    """Show a skill, linked reference, bundled script, or version-matched example."""
    skill = next((s for s in _skills() if s["name"] == name), None)
    if skill is None:
        error("SKILL_NOT_FOUND", f"No bundled skill named '{name}'.", "Run 'ep skills list' or 'ep skills search <query>'.", EXIT_NOT_FOUND)
    if human and html_output:
        error("USAGE_ERROR", "--human and --html cannot be used together.", "Choose one output format.", EXIT_USAGE)
    selected_options = [reference_path, script_path, example_path]
    if sum(value is not None for value in selected_options) > 1:
        error("USAGE_ERROR", "--reference, --script, and --example cannot be combined.", "Choose one skill resource.", EXIT_USAGE)
    if example_path is not None:
        example = _example_paths(skill).get(example_path)
        if example is None:
            available = sorted(_example_paths(skill))
            error(
                "EXAMPLE_NOT_FOUND",
                f"No bundled example '{example_path}' for skill '{name}'.",
                "Use 'ep skills list --routing' to see fetchable examples.",
                EXIT_NOT_FOUND,
                details=[{"available_examples": available}],
            )
        if html_output:
            error("USAGE_ERROR", "--html cannot render a source example.", "Fetch the source as text or use --html for skill Markdown.", EXIT_USAGE)
        content = example.read_text(encoding="utf-8")
        if human:
            click.echo(content, nl=not content.endswith("\n"))
        else:
            output({"name": name, "example": example_path, "content": content})
        return
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
        "examples": sorted(_example_paths(skill)),
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
@click.option("--skill", "skill_names", multiple=True, help="Install only this skill; repeat to install more than one. Defaults to all bundled skills.")
@click.option("--link", is_flag=True, help="Link skill directories to this EDSL installation.")
@click.option("--human", is_flag=True, help="Print readable text instead of JSON.")
def install_skills(target: Path, skill_names: tuple[str, ...], link: bool, human: bool):
    """Install or update selected bundled skill files under TARGET."""
    available = _skills()
    by_name = {skill["name"]: skill for skill in available}
    selected_names = list(dict.fromkeys(skill_names))
    unknown = [name for name in selected_names if name not in by_name]
    if unknown:
        error(
            "SKILL_NOT_FOUND",
            f"No bundled skill named '{unknown[0]}'.",
            "Run 'ep skills list' to see available skills, then repeat --skill for each skill to install.",
            EXIT_NOT_FOUND,
            details=[{"unknown_skills": unknown, "available_skills": sorted(by_name)}],
        )
    selected = [by_name[name] for name in selected_names] if selected_names else available

    target.mkdir(parents=True, exist_ok=True)
    for skill in selected:
        dest = target / skill["name"]
        if dest.is_symlink() and dest.readlink() == skill["path"] and link:
            continue
        if dest.is_symlink() or (link and dest.exists()):
            error("SKILL_CONFLICT", f"Skill already exists at {dest}.",
                  "Move the existing entry to a backup directory and rerun the command.",
                  exit_code=EXIT_USAGE)

    installed = []
    for skill in selected:
        destination = target / skill["name"]
        if link:
            if not destination.is_symlink():
                destination.symlink_to(skill["path"], target_is_directory=True)
        elif destination.exists():
            if not destination.is_dir():
                error("USAGE_ERROR", f"Cannot install over non-directory: {destination}", "Choose a directory target without conflicting files.", EXIT_USAGE)
            shutil.copytree(skill["path"], destination, dirs_exist_ok=True)
        else:
            shutil.copytree(skill["path"], destination)
        installed.append(str(destination))
    if link and not selected_names:
        # Clean up only links into this installation whose bundle was removed.
        for dest in target.iterdir():
            if (
                dest.is_symlink()
                and dest.name not in by_name
                and dest.readlink() == SKILLS_ROOT / dest.name
                and not (dest / "SKILL.md").exists()
            ):
                dest.unlink()
    if human:
        click.echo(f"Installed {len(installed)} skills into {target.resolve()}")
        for path in installed:
            click.echo(f"- {path}")
    else:
        output({"target": str(target.resolve()), "installed": installed})
