import json

import pytest
from click.testing import CliRunner

from edsl.__main__ import app
from edsl.cli_commands.study_contract import freeze, verify


@pytest.fixture
def study(tmp_path):
    (tmp_path / "plan.md").write_text("Approved: two observations and a PDF.\n")
    (tmp_path / "validator.py").write_text("EXPECTED_ROWS = 2\n")
    spec = {
        "schema_version": 1,
        "jobs": [
            {
                "id": "primary",
                "jobs_path": "jobs.ep",
                "results_path": "results.ep",
                "expected_rows": 2,
                "required_answers": ["answer"],
            }
        ],
        "deliverables": ["report.pdf"],
        "protected_sources": ["validator.py"],
    }
    source = tmp_path / "study-contract.json"
    source.write_text(json.dumps(spec))
    freeze(tmp_path, source, "User approved protocol in turn 4")
    return tmp_path, source, spec


def save_results(root, count):
    from edsl import Agent, Model, Results, Scenario, Survey
    from edsl.results import Result

    Results(
        survey=Survey([]),
        data=[
            Result(
                agent=Agent(),
                scenario=Scenario({}),
                model=Model("test"),
                iteration=i,
                answer={"answer": 42},
            )
            for i in range(count)
        ],
    ).git.save(root / "results.ep")
    (root / "jobs.ep").write_bytes(b"saved-job-placeholder")


def test_missing_job_and_requested_pdf_fail_completion(study):
    root, _, _ = study
    check = verify(root)
    assert not check["valid"]
    assert {e["code"] for e in check["errors"]} == {
        "MISSING_JOB_ARTIFACT",
        "MISSING_DELIVERABLE",
    }


def test_validator_and_mutable_spec_cannot_silently_weaken_frozen_count(study):
    root, source, spec = study
    save_results(root, 1)
    (root / "validator.py").write_text("EXPECTED_ROWS = 1\n")
    spec["jobs"][0]["expected_rows"] = 1
    source.write_text(json.dumps(spec))
    check = verify(root, "results")
    assert {e["code"] for e in check["errors"]} == {
        "PROTECTED_SOURCE_CHANGED",
        "ROW_COUNT_MISMATCH",
    }
    with pytest.raises(ValueError, match="amend"):
        freeze(root, source, "old approval")


def test_amendment_preserves_original_expectation_and_records_reason(study):
    root, source, spec = study
    original = (root / ".study-contract/0001.json").read_bytes()
    save_results(root, 1)
    spec["jobs"][0]["expected_rows"] = 1
    source.write_text(json.dumps(spec))
    updated = freeze(
        root,
        source,
        "User accepted one missing response in turn 9",
        "One failed response; report missingness",
    )
    assert updated["revision"] == 2
    assert (root / ".study-contract/0001.json").read_bytes() == original
    assert verify(root, "results")["valid"]
    assert not verify(root, "complete")["valid"]
    (root / "report.pdf").write_bytes(b"%PDF-1.4\n")
    assert verify(root)["valid"]


def test_missing_comparative_job_remains_required(study):
    root, source, spec = study
    save_results(root, 2)
    spec["jobs"].append(
        {
            **spec["jobs"][0],
            "id": "comparison",
            "jobs_path": "comparison.jobs.ep",
            "results_path": "comparison.results.ep",
        }
    )
    source.write_text(json.dumps(spec))
    freeze(root, source, "User added comparison", "Add comparative evaluation")
    check = verify(root, "results")
    assert any(e.get("job") == "comparison" for e in check["errors"])


def test_contract_revision_deletion_is_detected(study):
    root, source, spec = study
    freeze(root, source, "New approval", "Record updated scope")
    (root / ".study-contract/0001.json").unlink()
    with pytest.raises(ValueError, match="chain"):
        verify(root)


def test_cli_fails_closed_without_frozen_contract(tmp_path):
    result = CliRunner().invoke(
        app, ["study", "contract", "verify", "--root", str(tmp_path)]
    )
    assert result.exit_code == 5
    assert json.loads(result.output)["error"]["code"] == "STUDY_CONTRACT_ERROR"


def test_new_scaffold_wires_independent_checks(tmp_path):
    result = CliRunner().invoke(
        app,
        [
            "study",
            "scaffold",
            str(tmp_path),
            "--template",
            "survey",
            "--expected-rows",
            "2",
            "--model",
            "test",
            "--required-answer",
            "answer",
            "--run-description",
            "Contract test",
        ],
    )
    assert result.exit_code == 0, result.output
    spec = json.loads((tmp_path / "study-contract.json").read_text())
    assert spec["jobs"][0]["expected_rows"] == 2
    makefile = (tmp_path / "Makefile").read_text()
    assert "prepare: contract-freeze" in makefile
    assert "contract verify --root . --phase results" in makefile
    assert "contract verify --root . --phase complete" in makefile

    # Recovery/analysis must never create a fresh job when saved results vanish.
    import subprocess

    for target in ("post-run", "qa", "costs", "exports"):
        recovery = subprocess.run(
            ["make", "-C", str(tmp_path), target, "EP=unexpected-inference"],
            capture_output=True,
            text=True,
        )
        assert recovery.returncode != 0
        assert "Saved results missing" in recovery.stderr
        assert "unexpected-inference run" not in recovery.stdout
