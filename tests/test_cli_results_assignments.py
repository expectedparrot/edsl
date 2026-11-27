import json

from click.testing import CliRunner
from edsl import Agent, Jobs, Model, QuestionFreeText, Results, Scenario, Survey
from edsl.__main__ import app
from edsl.results import Result


def study():
    q = QuestionFreeText(
        question_name="note", question_text="Read {{ scenario.material }}."
    )
    return Jobs(
        survey=Survey([q]),
        agents=[Agent(name="Kit"), Agent(name="Bo")],
        scenarios=[Scenario({"material": "booklet"}), Scenario({"material": "card"})],
        models=[Model("test", canned_response="OK")],
    )


def saved_row(job, a, s, wave):
    return Result(
        agent=job.agents[a],
        scenario=job.scenarios[s],
        model=job.models[0],
        iteration=wave,
        answer={"note": "OK"},
        survey=job.survey,
        indices={"agent": a, "scenario": s, "model": 0},
    )


def audit(tmp_path, job, rows, *args, expected_code):
    wanted, actual = tmp_path / "job.json", tmp_path / "answers.json"
    wanted.write_text(json.dumps(job.to_dict()))
    actual.write_text(json.dumps(Results(survey=job.survey, data=rows).to_dict()))
    result = CliRunner().invoke(
        app,
        ["results", "check-assignments", str(actual), "--against", str(wanted), *args],
    )
    assert result.exit_code == expected_code, (result.output, result.exception)
    response = json.loads(result.stdout)
    if expected_code:
        return response["error"]
    return response["data"]


def test_assignment_counts_and_material_are_independent(tmp_path):
    job = study()
    rows = [
        saved_row(job, a, s, i) for a in range(2) for s in range(2) for i in range(2)
    ]
    good = audit(tmp_path, job, list(reversed(rows)), "-n", "2", expected_code=0)
    assert good["matches"] and good["planned_rows"] == good["recorded_rows"] == 8
    rows[-1] = rows[-2]
    rows[1].scenario = Scenario({"material": "flyer"})
    diff = audit(tmp_path, job, rows, "-n", "2", expected_code=5)["details"][0]
    assert diff["counts"] == {"missing": 1, "duplicate": 1, "changed_rows": 1}
    assert diff["examples"]["missing"][0]["agent_name"] == "Bo"
    assert diff["examples"]["missing"][0]["iteration"] == 1
    assert diff["examples"]["duplicate"][0]["iteration"] == 0
    assert diff["examples"]["changed_rows"][0]["fields"]["scenario"]["material"] == {
        "expected": "booklet",
        "recorded": "flyer",
    }


def test_legacy_rows_and_scripted_substitution(tmp_path):
    job = study().zip_assign()
    rows = [saved_row(job, 0, 0, 0), saved_row(job, 1, 1, 0)]
    for row in rows:
        row.indices = None
    assert audit(tmp_path, job, rows, expected_code=0)["matches"]
    rows[1].model = Model("test", canned_response="Different")
    assert (
        audit(tmp_path, job, rows, expected_code=5)["details"][0]["counts"][
            "unresolved_rows"
        ]
        == 1
    )
    assert audit(tmp_path, job, rows, "--allow-test-model", expected_code=0)["matches"]
    job.scenarios = [job.scenarios[0], job.scenarios[0]]
    for row in rows:
        row.scenario = job.scenarios[0]
    bad = audit(
        tmp_path, job, rows, "--allow-test-model", "--limit", "1", expected_code=5
    )["details"][0]
    assert (
        bad["counts"]["unresolved_rows"] == 2
        and len(bad["examples"]["unresolved_rows"]) == 1
    )


def test_treatment_policy_sets_iterations_and_rejects_wrong_wave(tmp_path):
    job = study()
    job.set_treatment_assignment(
        {
            "version": 1,
            "unit": "agent_iteration",
            "conditions": {"A": 0, "B": 1},
            "planned_iterations": 2,
            "schedule": {
                "agent:0|iteration:0": "A",
                "agent:0|iteration:1": "B",
                "agent:1|iteration:0": "B",
                "agent:1|iteration:1": "A",
            },
        }
    )
    rows = [
        saved_row(job, 0, 0, 0),
        saved_row(job, 0, 1, 1),
        saved_row(job, 1, 1, 0),
        saved_row(job, 1, 0, 1),
    ]
    assert audit(tmp_path, job, rows, expected_code=0)["planned_rows"] == 4
    assert (
        audit(tmp_path, job, rows, "-n", "3", expected_code=5)["code"]
        == "VALIDATION_ERROR"
    )
    rows[0] = saved_row(job, 0, 1, 0)
    err = audit(tmp_path, job, rows, expected_code=5)["details"][0]
    assert err["counts"] == {"missing": 1, "unexpected": 1}


def test_offline_package_audit_respects_explicit_assignment_multiplicity(
    tmp_path, monkeypatch
):
    import socket

    job = study().assign([(1, 0, 0), (1, 0, 0), (0, 1, 0)])
    job_file = tmp_path / "intended.ep"
    results_file = tmp_path / "recorded.ep"
    job.git.save(job_file, sync_coop=False)
    rows = [saved_row(job, 1, 0, 0), saved_row(job, 0, 1, 0), saved_row(job, 1, 0, 0)]
    Results(survey=job.survey, data=rows).git.save(results_file, sync_coop=False)
    original = (job_file.read_bytes(), results_file.read_bytes())

    def refuse(*args):
        raise AssertionError("Assignment audit attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    run = CliRunner().invoke(
        app,
        ["results", "check-assignments", str(results_file), "--against", str(job_file)],
    )
    assert run.exit_code == 0, run.output
    assert json.loads(run.stdout)["data"]["planned_rows"] == 3
    assert original == (job_file.read_bytes(), results_file.read_bytes())
