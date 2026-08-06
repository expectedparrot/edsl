"""Click integration for ``ep workflow``."""

from __future__ import annotations

import json
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_NOT_FOUND, EXIT_USAGE, error, output

from .state import (
    WorkflowError,
    attest,
    clear,
    freeze,
    initialize,
    load_status,
    resolve_root,
    repair_gates,
    set_gates,
    validate_spec,
    verify,
    verify_remaining,
)


def _fail(exc: WorkflowError) -> None:
    exit_code = (
        EXIT_NOT_FOUND
        if exc.code == "WORKFLOW_NOT_FOUND"
        else EXIT_USAGE if "SPEC" in exc.code else EXIT_ERROR
    )
    error(exc.code, exc.message, suggestion=exc.suggestion, details=exc.details, exit_code=exit_code)


def _spec(spec_path: str | None, inline_json: str | None) -> dict:
    if bool(spec_path) == bool(inline_json):
        raise WorkflowError(
            "WORKFLOW_SPEC_INVALID", "Provide exactly one of --spec or --json"
        )
    try:
        if inline_json:
            return json.loads(inline_json)
        if spec_path == "-":
            return json.loads(click.get_text_stream("stdin").read())
        return json.loads(Path(str(spec_path)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(
            "WORKFLOW_SPEC_INVALID", f"Cannot read gate specification: {exc}"
        ) from exc


def register(workflow_group: click.Group, gate_group: click.Group) -> None:
    @workflow_group.command("setup")
    @click.option("--name", required=True)
    @click.option("--spec", "spec_path", default=None, type=click.Path())
    @click.option("--json", "inline_json", default=None)
    @click.option("--evidence", required=True)
    @click.option("--root", default=".", type=click.Path(file_okay=False))
    def workflow_setup(name, spec_path, inline_json, evidence, root):
        """Initialize, bulk-set, and freeze a workflow in one command."""
        try:
            specification = _spec(spec_path, inline_json)
            validate_spec(specification)
            resolved = resolve_root(root, require=False)
            resolved.mkdir(parents=True, exist_ok=True)
            initialize(resolved, name)
            set_gates(resolved, specification)
            status = freeze(resolved, evidence)
            output(
                {
                    "root": str(resolved),
                    "name": status["name"],
                    "frozen": status["frozen"],
                    "gate_count": len(status["gates"]),
                    "current_gate": status["current_gate"],
                }
            )
        except WorkflowError as exc:
            _fail(exc)

    @workflow_group.command("init")
    @click.option("--name", required=True)
    @click.option("--root", default=".", type=click.Path(file_okay=False))
    def workflow_init(name, root):
        """Initialize workflow state in a task directory."""
        try:
            resolved = resolve_root(root, require=False)
            resolved.mkdir(parents=True, exist_ok=True)
            config = initialize(resolved, name)
            output({"root": str(resolved), "workflow": config})
        except WorkflowError as exc:
            _fail(exc)

    @workflow_group.command("status")
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def workflow_status(root):
        """Show current gate progress and evidence."""
        try:
            output(load_status(resolve_root(root)))
        except WorkflowError as exc:
            _fail(exc)

    @workflow_group.command("verify")
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def workflow_verify(root):
        """Verify all consecutive remaining objective gates."""
        try:
            output(verify_remaining(resolve_root(root)))
        except WorkflowError as exc:
            _fail(exc)

    @workflow_group.command("freeze")
    @click.option("--evidence", required=True)
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def workflow_freeze(evidence, root):
        """Freeze the approved gate definition."""
        try:
            output(freeze(resolve_root(root), evidence))
        except WorkflowError as exc:
            _fail(exc)

    @workflow_group.command("repair")
    @click.option("--spec", "spec_path", default=None, type=click.Path())
    @click.option("--json", "inline_json", default=None)
    @click.option("--reason", required=True)
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def workflow_repair(spec_path, inline_json, reason, root):
        """Repair unpassed verifier definitions while preserving frozen gate semantics."""
        try:
            output(repair_gates(resolve_root(root), _spec(spec_path, inline_json), reason))
        except WorkflowError as exc:
            _fail(exc)

    @gate_group.command("set")
    @click.option("--spec", "spec_path", default=None, type=click.Path())
    @click.option("--json", "inline_json", default=None)
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def gate_set(spec_path, inline_json, root):
        """Atomically replace the proposed ordered gate set."""
        try:
            resolved = resolve_root(root)
            gates = set_gates(resolved, _spec(spec_path, inline_json))
            output(
                {
                    "root": str(resolved),
                    "gates": gates,
                    "current_gate": gates[0]["name"],
                }
            )
        except WorkflowError as exc:
            _fail(exc)

    @gate_group.command("attest")
    @click.argument("gate_name")
    @click.option("--evidence", required=True)
    @click.option("--by", default="agent", show_default=True)
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def gate_attest(gate_name, evidence, by, root):
        """Pass the current human or agent attestation gate."""
        try:
            output(attest(resolve_root(root), gate_name, evidence, by))
        except WorkflowError as exc:
            _fail(exc)

    @gate_group.command("verify")
    @click.argument("gate_name", required=False)
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def gate_verify(gate_name, root):
        """Run the current gate's objective verifier."""
        try:
            resolved = resolve_root(root)
            if gate_name is None:
                status = load_status(resolved)
                gate_name = status["current_gate"]
                if gate_name is None:
                    output({**status, "already_complete": True})
                    return
            output(verify(resolved, gate_name))
        except WorkflowError as exc:
            _fail(exc)

    @gate_group.command("clear")
    @click.argument("gate_name")
    @click.option("--reason", required=True)
    @click.option("--root", default=None, type=click.Path(file_okay=False))
    def gate_clear(gate_name, reason, root):
        """Clear a passed gate while preserving the audit event."""
        try:
            output(clear(resolve_root(root), gate_name, reason))
        except WorkflowError as exc:
            _fail(exc)
