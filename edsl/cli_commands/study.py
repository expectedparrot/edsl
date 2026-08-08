"""Allocate and scaffold reproducible research studies."""

from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path

import click

from edsl.cli_shared import EXIT_USAGE, error, output
from edsl.cli_commands.study_resources.scaffold import create_project


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise click.BadParameter("topic must contain a letter or digit", param_hint="--topic")
    return slug


def _study_suffix(index: int) -> str:
    value = ""
    while True:
        index, remainder = divmod(index, 26)
        value = chr(ord("a") + remainder) + value
        if index == 0:
            return value
        index -= 1


def _orientation(root: Path, topic: str, summary_limit: int) -> dict:
    root = root.resolve()
    topic_slug = _slugify(topic)
    topic_dir = root / "sessions" / f"topic_{topic_slug}"
    studies = sorted(p.name for p in topic_dir.glob("study_*") if p.is_dir()) if topic_dir.is_dir() else []
    summaries = []
    for name in reversed(studies):
        study = topic_dir / name
        selected = study / "chat_summary.md"
        if not selected.is_file():
            selected = study / "writeup" / "report.md"
        if selected.is_file():
            summaries.append({
                "path": str(selected.relative_to(root)),
                "preview": " ".join(selected.read_text(encoding="utf-8", errors="replace").split())[:240],
            })
        if len(summaries) >= summary_limit:
            break
    recommended = topic_dir / f"study_{_study_suffix(len(studies))}"
    return {
        "workspace_root": str(root),
        "topic": topic_slug,
        "topic_path": str(topic_dir.relative_to(root)),
        "topic_exists": topic_dir.is_dir(),
        "existing_studies": studies,
        "prior_summaries": summaries,
        "recommended_study": str(recommended.relative_to(root)),
    }


@click.group(invoke_without_command=True)
@click.pass_context
def study(ctx):
    """Allocate and scaffold reproducible study workspaces."""
    if ctx.invoked_subcommand is None:
        output({"commands": ["start", "scaffold"], "help": "Use 'ep study <command> --help' for details."})


@study.command("start")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd, show_default="current directory")
@click.option("--topic", required=True, help="Human topic name or stable topic slug.")
@click.option("--summary-limit", type=click.IntRange(0, 20), default=5, show_default=True)
@click.option("--create/--no-create", default=True, help="Create the neutral study directory and plan placeholder.")
def start(root: Path, topic: str, summary_limit: int, create: bool):
    """Choose the next study path and optionally create its neutral scaffold."""
    data = _orientation(root, topic, summary_limit)
    study_path = root.resolve() / data["recommended_study"]
    if create:
        study_path.mkdir(parents=True, exist_ok=False)
        (study_path / "plan.md").write_text("", encoding="utf-8")
    data["created"] = create
    data["study_root"] = str(study_path)
    data["next_action"] = "Write plan.md and obtain approval before method-specific scaffolding."
    output(data)


@study.command("scaffold")
@click.argument("path", type=click.Path(path_type=Path))
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Resolve a relative PATH from this workspace root.")
@click.option("--type", "study_type", type=click.Choice(["edsl", "simulation"]), default="edsl")
@click.option("--template", type=click.Choice(["survey", "agent-list", "qualitative-analysis", "digital-twins"]))
@click.option("--expected-rows", type=int)
@click.option("--required-answer", multiple=True)
@click.option("--expected-agents", type=int)
@click.option("--required-trait", multiple=True)
@click.option("--group-trait")
@click.option("--expected-group-size", type=int)
@click.option("--required-source-domain")
@click.option("--model")
@click.option("--run-description")
@click.option("--with-scenarios", is_flag=True, help="Create and wire a ScenarioList for repeated stimuli.")
@click.option("--job", "jobs", multiple=True)
@click.option("--sim", "sims", multiple=True)
def scaffold(path: Path, root: Path | None, study_type: str, template: str | None, expected_rows: int | None,
             required_answer: tuple[str, ...], expected_agents: int | None,
             required_trait: tuple[str, ...], group_trait: str | None,
             expected_group_size: int | None, required_source_domain: str | None,
             model: str | None, run_description: str | None, with_scenarios: bool, jobs: tuple[str, ...],
             sims: tuple[str, ...]):
    """Install deterministic build, validation, workflow, and report assets."""
    try:
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            resolved_path = (root.resolve() / path) if root is not None and not path.is_absolute() else path
            create_project(
                str(resolved_path), list(jobs) or None, study_type=study_type, sims=list(sims) or None,
                template=template, expected_rows=expected_rows,
                required_answers=list(required_answer), expected_agents=expected_agents,
                required_traits=list(required_trait), group_trait=group_trait,
                expected_group_size=expected_group_size,
                required_source_domain=required_source_domain, model=model,
                run_description=run_description,
                with_scenarios=with_scenarios,
            )
        payload = json.loads(capture.getvalue())
    except (ValueError, json.JSONDecodeError) as exc:
        error("STUDY_SCAFFOLD_ERROR", str(exc), suggestion="Run 'ep study scaffold --help' and supply the template invariants.", exit_code=EXIT_USAGE)
        return
    output(payload.get("data", payload), warnings=payload.get("warnings", []))


def register(app):
    app.add_command(study)
