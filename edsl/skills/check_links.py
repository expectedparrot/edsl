"""Validate bundled skill links and namespaced cross-references."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
CROSS_REF = re.compile(r"\b(edsl|ep-agent):([a-z0-9][a-z0-9-]*)\b")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M)
HTML_ID = re.compile(r"\bid=[\"']([^\"']+)[\"']")
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".js", ".mjs", ".ts", ".r"}


def _anchors(path: Path) -> set[str]:
    """Collect explicit and generated Markdown heading anchors."""
    text = path.read_text(encoding="utf-8")
    anchors = set(HTML_ID.findall(text))
    in_fence = False
    headings = []
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
            if match:
                headings.append(match.group(1))
    used: dict[str, int] = {}
    for heading in headings:
        plain = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading)
        plain = re.sub(r"[`*~]", "", plain).lower()
        slug = re.sub(r"[^\w -]", "", plain, flags=re.UNICODE).strip()
        slug = slug.replace(" ", "-")
        count = used.get(slug, 0)
        used[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def check() -> list[str]:
    errors: list[str] = []
    skills = sorted(p for p in ROOT.glob("*/SKILL.md"))
    names: dict[str, list[Path]] = {}
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        match = re.search(r"^name:\s*(\S+)\s*$", text, re.M)
        name = match.group(1) if match else skill.parent.name
        names.setdefault(name, []).append(skill)
    for name, paths in names.items():
        if len(paths) > 1:
            errors.append(f"ambiguous skill name {name}: {', '.join(str(p.relative_to(ROOT)) for p in paths)}")

    for skill in skills:
        bundle = skill.parent.resolve()
        linked_scripts = set()
        for target in LINK.findall(skill.read_text(encoding="utf-8")):
            if target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            destination = target.split("#", 1)[0]
            resolved = (skill.parent / destination).resolve()
            if resolved.is_relative_to(bundle) and resolved.suffix.lower() in SCRIPT_SUFFIXES:
                linked_scripts.add(resolved)

        scripts_dir = skill.parent / "scripts"
        if scripts_dir.is_dir():
            for script in sorted(path for path in scripts_dir.rglob("*") if path.is_file()):
                if not script.resolve().is_relative_to(bundle):
                    errors.append(f"skill script escapes bundle {script.relative_to(ROOT)}")
                elif script.suffix.lower() not in SCRIPT_SUFFIXES:
                    errors.append(f"unsupported skill script extension {script.relative_to(ROOT)}")
                elif script.resolve() not in linked_scripts:
                    errors.append(
                        f"unlinked skill script {script.relative_to(ROOT)}; link it from SKILL.md"
                    )

    registry = json.loads((ROOT / "cross-references.json").read_text(encoding="utf-8"))
    external_names = registry.get("ep-agent", [])
    duplicates = sorted({name for name in external_names if external_names.count(name) > 1})
    if duplicates:
        errors.append(f"ambiguous ep-agent cross-reference names: {', '.join(duplicates)}")
    collisions = sorted(set(names) & set(external_names))
    if collisions:
        errors.append(f"ambiguous cross-reference namespace for: {', '.join(collisions)}")
    for path in ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        bundle_root = path.parent
        while bundle_root.parent != ROOT and bundle_root != ROOT:
            bundle_root = bundle_root.parent
        for target in LINK.findall(text):
            if target.startswith(("https://", "http://", "mailto:")):
                continue
            destination = target.split("#", 1)[0]
            resolved = (path.parent / destination).resolve() if destination else path
            if not resolved.is_file() or not resolved.is_relative_to(bundle_root.resolve()):
                errors.append(f"broken internal link {path.relative_to(ROOT)} -> {target}")
                continue
            if "#" in target:
                fragment = target.split("#", 1)[1]
                if fragment and fragment not in _anchors(resolved):
                    errors.append(f"broken Markdown anchor {path.relative_to(ROOT)} -> {target}")
        for namespace, name in CROSS_REF.findall(text):
            known = names if namespace == "edsl" else {n: [] for n in registry.get(namespace, [])}
            if name not in known:
                errors.append(f"unresolved cross-reference {path.relative_to(ROOT)} -> {namespace}:{name}")
    return errors


if __name__ == "__main__":
    problems = check()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(1)
    print(f"Skill links OK ({len(list(ROOT.glob('*/SKILL.md')))} skills)")
