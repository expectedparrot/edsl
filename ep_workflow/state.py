"""Filesystem state and verification for ep workflows."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKFLOW_DIR = ".ep-workflow"
VALID_TYPES = {"agent-attestation", "user-approval", "file-exists", "command"}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, suggestion: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.suggestion = suggestion


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def resolve_root(root: str | None, *, require: bool = True) -> Path:
    if root:
        candidate = Path(root).expanduser().resolve()
        if require and not (candidate / WORKFLOW_DIR / "workflow.json").is_file():
            raise WorkflowError(
                "WORKFLOW_NOT_FOUND", f"No workflow found at {candidate}"
            )
        return candidate
    candidate = Path.cwd().resolve()
    for directory in (candidate, *candidate.parents):
        if (directory / WORKFLOW_DIR / "workflow.json").is_file():
            return directory
    if require:
        raise WorkflowError(
            "WORKFLOW_NOT_FOUND",
            "No .ep-workflow found in this directory or its parents",
        )
    return candidate


def workflow_path(root: Path) -> Path:
    return root / WORKFLOW_DIR


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def append_event(root: Path, event_type: str, payload: dict[str, Any]) -> Path:
    events = workflow_path(root) / "events"
    events.mkdir(parents=True, exist_ok=True)
    numbers = [
        int(path.name.split("_", 1)[0])
        for path in events.iterdir()
        if path.name.split("_", 1)[0].isdigit()
    ]
    number = max(numbers, default=0) + 1
    event = {"version": 1, "type": event_type, "at": utc_now(), **payload}
    while True:
        path = events / f"{number:05d}_{event_type}.json"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            break
        except FileExistsError:
            number += 1
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(event, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def initialize(root: Path, name: str) -> dict[str, Any]:
    location = workflow_path(root)
    if (location / "workflow.json").exists():
        raise WorkflowError("WORKFLOW_EXISTS", f"Workflow already exists at {location}")
    config = {"version": 1, "name": name, "gates": []}
    atomic_json(location / "workflow.json", config)
    append_event(root, "workflow-initialized", {"name": name})
    return config


def read_config(root: Path) -> dict[str, Any]:
    try:
        return json.loads(
            (workflow_path(root) / "workflow.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(
            "WORKFLOW_INVALID", f"Cannot read workflow configuration: {exc}"
        ) from exc


def read_events(root: Path) -> list[dict[str, Any]]:
    events_dir = workflow_path(root) / "events"
    records = []
    for path in sorted(events_dir.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise WorkflowError(
                "WORKFLOW_INVALID", f"Invalid event {path.name}: {exc}"
            ) from exc
    return records


def validate_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        raise WorkflowError(
            "WORKFLOW_SPEC_INVALID", "Gate specification must be a JSON object"
        )
    gates = spec.get("gates")
    if not isinstance(gates, list) or not gates:
        raise WorkflowError(
            "WORKFLOW_SPEC_INVALID",
            "Specification must contain a non-empty gates array",
        )
    normalized = []
    names: set[str] = set()
    for index, raw in enumerate(gates, 1):
        if not isinstance(raw, dict):
            raise WorkflowError(
                "WORKFLOW_SPEC_INVALID", f"Gate {index} must be an object"
            )
        name = raw.get("name")
        if not isinstance(name, str) or not SLUG.fullmatch(name):
            raise WorkflowError(
                "WORKFLOW_SPEC_INVALID", f"Gate {index} has an invalid kebab-case name"
            )
        if name in names:
            raise WorkflowError("WORKFLOW_SPEC_INVALID", f"Duplicate gate name: {name}")
        names.add(name)
        description = raw.get("description", "")
        if not isinstance(description, str):
            raise WorkflowError(
                "WORKFLOW_SPEC_INVALID", f"Gate {name} description must be a string"
            )
        verification = raw.get("verification")
        if (
            not isinstance(verification, dict)
            or verification.get("type") not in VALID_TYPES
        ):
            raise WorkflowError(
                "WORKFLOW_SPEC_INVALID",
                f"Gate {name} needs a supported verification type",
            )
        kind = verification["type"]
        if kind == "file-exists" and not (
            isinstance(verification.get("path"), str) and verification["path"].strip()
        ):
            raise WorkflowError(
                "WORKFLOW_SPEC_INVALID",
                f"Gate {name} file-exists verification needs path",
            )
        if kind == "command" and not (
            isinstance(verification.get("command"), str)
            and verification["command"].strip()
        ):
            raise WorkflowError(
                "WORKFLOW_SPEC_INVALID",
                f"Gate {name} command verification needs command",
            )
        normalized.append(
            {"name": name, "description": description, "verification": verification}
        )
    return normalized


def set_gates(root: Path, spec: dict[str, Any]) -> list[dict[str, Any]]:
    status = load_status(root)
    if status["frozen"]:
        raise WorkflowError(
            "WORKFLOW_FROZEN", "Cannot replace gates after the workflow is frozen"
        )
    if status["passed_gates"]:
        raise WorkflowError(
            "WORKFLOW_IN_PROGRESS", "Clear passed gates before replacing the gate set"
        )
    gates = validate_spec(spec)
    config = read_config(root)
    config["gates"] = gates
    atomic_json(workflow_path(root) / "workflow.json", config)
    append_event(root, "gates-set", {"gates": [gate["name"] for gate in gates]})
    return gates


def load_status(root: Path) -> dict[str, Any]:
    config = read_config(root)
    gates = config.get("gates", [])
    names = [gate["name"] for gate in gates]
    passed: list[str] = []
    evidence: dict[str, Any] = {}
    frozen = False
    freeze_evidence = None
    for event in read_events(root):
        if event.get("type") == "workflow-frozen":
            frozen = True
            freeze_evidence = event.get("evidence")
        elif event.get("type") == "gate-passed" and event.get("gate") in names:
            gate = str(event["gate"])
            if gate not in passed:
                passed.append(gate)
                evidence[gate] = event.get("evidence")
        elif event.get("type") == "gate-cleared" and event.get("gate") in passed:
            gate = str(event["gate"])
            passed.remove(gate)
            evidence.pop(gate, None)
    current = next((name for name in names if name not in passed), None)
    return {
        "root": str(root),
        "name": config.get("name"),
        "frozen": frozen,
        "freeze_evidence": freeze_evidence,
        "gates": [
            {
                **gate,
                "passed": gate["name"] in passed,
                "evidence": evidence.get(gate["name"]),
            }
            for gate in gates
        ],
        "passed_gates": passed,
        "current_gate": current,
        "all_gates_passed": bool(names) and len(passed) == len(names),
    }


def freeze(root: Path, evidence: str) -> dict[str, Any]:
    status = load_status(root)
    if status["frozen"]:
        raise WorkflowError("WORKFLOW_FROZEN", "Workflow is already frozen")
    if not status["gates"]:
        raise WorkflowError(
            "WORKFLOW_EMPTY", "Define gates before freezing the workflow"
        )
    append_event(root, "workflow-frozen", {"evidence": evidence})
    return load_status(root)


def _current_gate(root: Path, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    status = load_status(root)
    gate = next((gate for gate in status["gates"] if gate["name"] == name), None)
    if gate is None:
        raise WorkflowError("WORKFLOW_GATE_NOT_FOUND", f"Gate is not declared: {name}")
    if gate["passed"]:
        raise WorkflowError("WORKFLOW_GATE_PASSED", f"Gate is already passed: {name}")
    if status["current_gate"] != name:
        raise WorkflowError(
            "WORKFLOW_GATE_OUT_OF_SEQUENCE",
            f"Cannot pass {name} before {status['current_gate']}",
        )
    return status, gate


def attest(root: Path, name: str, evidence: str, by: str) -> dict[str, Any]:
    _, gate = _current_gate(root, name)
    kind = gate["verification"]["type"]
    if kind not in {"agent-attestation", "user-approval"}:
        raise WorkflowError(
            "WORKFLOW_GATE_REQUIRES_VERIFICATION",
            f"Gate {name} must be verified automatically",
        )
    if kind == "user-approval" and by != "user":
        raise WorkflowError(
            "WORKFLOW_USER_APPROVAL_REQUIRED",
            f"Gate {name} must be attested with --by user",
        )
    append_event(
        root,
        "gate-passed",
        {
            "gate": name,
            "method": "attestation",
            "by": by,
            "evidence": {"text": evidence, "verification_type": kind},
        },
    )
    return load_status(root)


def verify(root: Path, name: str) -> dict[str, Any]:
    _, gate = _current_gate(root, name)
    verification = gate["verification"]
    kind = verification["type"]
    if kind in {"agent-attestation", "user-approval"}:
        raise WorkflowError(
            "WORKFLOW_GATE_REQUIRES_ATTESTATION",
            f"Gate {name} requires evidence-bearing attestation",
        )
    if kind == "file-exists":
        path = (root / verification["path"]).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise WorkflowError(
                "WORKFLOW_VERIFICATION_FAILED",
                "Verification path escapes workflow root",
            ) from exc
        if not path.is_file():
            raise WorkflowError(
                "WORKFLOW_VERIFICATION_FAILED",
                f"Required file does not exist: {verification['path']}",
            )
        evidence = {
            "verification_type": kind,
            "path": verification["path"],
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
    else:
        try:
            result = subprocess.run(
                verification["command"],
                cwd=root,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkflowError(
                "WORKFLOW_VERIFICATION_FAILED",
                "Verification command timed out after 120 seconds",
            ) from exc
        if result.returncode:
            raise WorkflowError(
                "WORKFLOW_VERIFICATION_FAILED",
                f"Verification command failed with exit code {result.returncode}",
            )
        evidence = {
            "verification_type": kind,
            "command": verification["command"],
            "exit_code": result.returncode,
            "stdout": result.stdout[-2000:],
            "stderr": result.stderr[-2000:],
        }
    append_event(
        root,
        "gate-passed",
        {
            "gate": name,
            "method": "verification",
            "by": "ep-workflow",
            "evidence": evidence,
        },
    )
    return load_status(root)


def verify_remaining(root: Path) -> dict[str, Any]:
    """Verify every consecutive objective gate and return one bounded summary."""
    verified: list[dict[str, Any]] = []
    while True:
        status = load_status(root)
        current = status["current_gate"]
        if current is None:
            return {
                "root": str(root),
                "verified": verified,
                "passed_gates": status["passed_gates"],
                "current_gate": None,
                "all_gates_passed": status["all_gates_passed"],
            }
        gate = next(gate for gate in status["gates"] if gate["name"] == current)
        kind = gate["verification"]["type"]
        if kind in {"agent-attestation", "user-approval"}:
            if verified:
                return {
                    "root": str(root),
                    "verified": verified,
                    "passed_gates": status["passed_gates"],
                    "current_gate": current,
                    "all_gates_passed": False,
                    "stopped": "attestation-required",
                }
            raise WorkflowError(
                "WORKFLOW_GATE_REQUIRES_ATTESTATION",
                f"Gate {current} requires evidence-bearing attestation",
            )
        verify(root, current)
        verified.append({"name": current, "verification_type": kind})


def clear(root: Path, name: str, reason: str) -> dict[str, Any]:
    status = load_status(root)
    if name not in status["passed_gates"]:
        raise WorkflowError("WORKFLOW_GATE_NOT_PASSED", f"Gate is not passed: {name}")
    names = [gate["name"] for gate in status["gates"]]
    start = names.index(name)
    invalidated = [gate for gate in names[start:] if gate in status["passed_gates"]]
    for gate in invalidated:
        append_event(
            root,
            "gate-cleared",
            {
                "gate": gate,
                "reason": reason,
                "invalidated_by": name if gate != name else None,
            },
        )
    return load_status(root)
