import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

import edsl.__main__ as cli_module


def invoke(runner: CliRunner, args: list[str]) -> tuple[int, dict]:
    result = runner.invoke(cli_module.app, args)
    return result.exit_code, json.loads(result.output)


def gate_spec(*gates):
    return json.dumps({"gates": list(gates)})


def test_atomic_gate_setup_and_ordered_evidence(tmp_path: Path) -> None:
    runner = CliRunner()
    code, initialized = invoke(
        runner, ["workflow", "init", "--name", "color-survey", "--root", str(tmp_path)]
    )
    assert code == 0
    assert initialized["status"] == "ok"

    spec = gate_spec(
        {
            "name": "plan-approved",
            "description": "User approved",
            "verification": {"type": "user-approval"},
        },
        {
            "name": "report-rendered",
            "description": "HTML exists",
            "verification": {"type": "file-exists", "path": "writeup/report.html"},
        },
    )
    code, configured = invoke(
        runner, ["workflow", "gate", "set", "--root", str(tmp_path), "--json", spec]
    )
    assert code == 0
    assert [gate["name"] for gate in configured["data"]["gates"]] == [
        "plan-approved",
        "report-rendered",
    ]

    code, premature = invoke(
        runner,
        ["workflow", "gate", "verify", "report-rendered", "--root", str(tmp_path)],
    )
    assert code == 1
    assert premature["error"]["code"] == "WORKFLOW_GATE_OUT_OF_SEQUENCE"

    code, passed = invoke(
        runner,
        [
            "workflow",
            "gate",
            "attest",
            "plan-approved",
            "--evidence",
            "Approved in turn 8",
            "--by",
            "user",
            "--root",
            str(tmp_path),
        ],
    )
    assert code == 0
    assert passed["data"]["current_gate"] == "report-rendered"

    code, missing = invoke(
        runner,
        ["workflow", "gate", "verify", "report-rendered", "--root", str(tmp_path)],
    )
    assert code == 1
    assert missing["error"]["code"] == "WORKFLOW_VERIFICATION_FAILED"

    report = tmp_path / "writeup" / "report.html"
    report.parent.mkdir()
    report.write_text("<h1>Color survey</h1>")
    code, complete = invoke(
        runner,
        ["workflow", "gate", "verify", "report-rendered", "--root", str(tmp_path)],
    )
    assert code == 0
    assert complete["data"]["all_gates_passed"] is True
    assert complete["data"]["gates"][1]["evidence"]["sha256"]


def test_gate_set_is_atomic_and_freeze_prevents_replacement(tmp_path: Path) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "study", "--root", str(tmp_path)])
    valid = gate_spec({"name": "first", "verification": {"type": "agent-attestation"}})
    assert (
        invoke(
            runner,
            ["workflow", "gate", "set", "--root", str(tmp_path), "--json", valid],
        )[0]
        == 0
    )

    duplicate = gate_spec(
        {"name": "first", "verification": {"type": "agent-attestation"}},
        {"name": "first", "verification": {"type": "agent-attestation"}},
    )
    code, invalid = invoke(
        runner,
        ["workflow", "gate", "set", "--root", str(tmp_path), "--json", duplicate],
    )
    assert code == 2
    assert invalid["error"]["code"] == "WORKFLOW_SPEC_INVALID"
    status = invoke(runner, ["workflow", "status", "--root", str(tmp_path)])[1]
    assert [gate["name"] for gate in status["data"]["gates"]] == ["first"]

    assert (
        invoke(
            runner,
            [
                "workflow",
                "freeze",
                "--root",
                str(tmp_path),
                "--evidence",
                "User approved gates",
            ],
        )[0]
        == 0
    )
    code, frozen = invoke(
        runner, ["workflow", "gate", "set", "--root", str(tmp_path), "--json", valid]
    )
    assert code == 1
    assert frozen["error"]["code"] == "WORKFLOW_FROZEN"


def test_gate_set_rejects_non_object_json_with_structured_error(tmp_path: Path) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "study", "--root", str(tmp_path)])

    code, invalid = invoke(
        runner,
        ["workflow", "gate", "set", "--root", str(tmp_path), "--json", "[]"],
    )

    assert code == 2
    assert invalid["error"]["code"] == "WORKFLOW_SPEC_INVALID"


def test_command_gate_records_output_and_clear_reopens_gate(tmp_path: Path) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "commands", "--root", str(tmp_path)])
    spec = gate_spec(
        {
            "name": "checked",
            "verification": {"type": "command", "command": "printf verified"},
        }
    )
    invoke(runner, ["workflow", "gate", "set", "--root", str(tmp_path), "--json", spec])
    code, verified = invoke(
        runner, ["workflow", "gate", "verify", "checked", "--root", str(tmp_path)]
    )
    assert code == 0
    assert verified["data"]["gates"][0]["evidence"]["stdout"] == "verified"

    code, cleared = invoke(
        runner,
        [
            "workflow",
            "gate",
            "clear",
            "checked",
            "--reason",
            "Artifact changed",
            "--root",
            str(tmp_path),
        ],
    )
    assert code == 0
    assert cleared["data"]["current_gate"] == "checked"
    assert cleared["data"]["all_gates_passed"] is False


def test_clearing_earlier_gate_invalidates_downstream_passes(tmp_path: Path) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "ordered", "--root", str(tmp_path)])
    spec = gate_spec(
        {"name": "first", "verification": {"type": "agent-attestation"}},
        {"name": "second", "verification": {"type": "agent-attestation"}},
    )
    invoke(runner, ["workflow", "gate", "set", "--root", str(tmp_path), "--json", spec])
    invoke(
        runner,
        [
            "workflow",
            "gate",
            "attest",
            "first",
            "--evidence",
            "done",
            "--root",
            str(tmp_path),
        ],
    )
    invoke(
        runner,
        [
            "workflow",
            "gate",
            "attest",
            "second",
            "--evidence",
            "done",
            "--root",
            str(tmp_path),
        ],
    )

    code, cleared = invoke(
        runner,
        [
            "workflow",
            "gate",
            "clear",
            "first",
            "--reason",
            "Inputs changed",
            "--root",
            str(tmp_path),
        ],
    )
    assert code == 0
    assert cleared["data"]["passed_gates"] == []
    assert cleared["data"]["current_gate"] == "first"


def test_user_approval_requires_user_actor(tmp_path: Path) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "approval", "--root", str(tmp_path)])
    spec = gate_spec({"name": "approved", "verification": {"type": "user-approval"}})
    invoke(runner, ["workflow", "gate", "set", "--root", str(tmp_path), "--json", spec])

    code, rejected = invoke(
        runner,
        [
            "workflow",
            "gate",
            "attest",
            "approved",
            "--evidence",
            "I think so",
            "--root",
            str(tmp_path),
        ],
    )
    assert code == 1
    assert rejected["error"]["code"] == "WORKFLOW_USER_APPROVAL_REQUIRED"


def test_status_discovers_workflow_from_nested_directory(
    tmp_path: Path, monkeypatch
) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "nested", "--root", str(tmp_path)])
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)

    monkeypatch.chdir(nested)
    code, status = invoke(runner, ["workflow", "status"])

    assert code == 0
    assert status["data"]["root"] == str(tmp_path)


def test_command_timeout_uses_structured_error(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    invoke(runner, ["workflow", "init", "--name", "timeout", "--root", str(tmp_path)])
    spec = gate_spec(
        {
            "name": "checked",
            "verification": {"type": "command", "command": "slow-check"},
        }
    )
    invoke(runner, ["workflow", "gate", "set", "--root", str(tmp_path), "--json", spec])

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("slow-check", 120)

    monkeypatch.setattr("ep_workflow.state.subprocess.run", time_out)
    code, failed = invoke(
        runner, ["workflow", "gate", "verify", "checked", "--root", str(tmp_path)]
    )

    assert code == 1
    assert failed["error"]["code"] == "WORKFLOW_VERIFICATION_FAILED"
    assert "timed out" in failed["error"]["message"]
