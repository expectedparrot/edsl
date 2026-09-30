"""Exercise saved shared-state jobs through the normal CLI without providers."""

import json

import pytest
from click.testing import CliRunner

from edsl import (
    Agent,
    AgentList,
    Jobs,
    Model,
    ModelList,
    QuestionCompute,
    Results,
    Scenario,
    ScenarioList,
    Survey,
)
from edsl.__main__ import app
from edsl.object_store.store import ObjectStore
from examples.shared_state_advanced_acceptance import build_case
from examples.shared_state_acceptance import (
    CASES,
    build_case as scripted_case,
    check_case,
)


@pytest.fixture(autouse=True)
def isolate_object_store(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ObjectStore, "default_root", staticmethod(lambda: tmp_path / "objects")
    )


@pytest.fixture
def round_job(tmp_path):
    job = build_case("repeated_matrix", Model("test", canned_response="unused"))
    data = job.survey.to_dict()
    data["questions"] = [
        QuestionCompute(
            question_name="action",
            question_text="{{ 'cooperate' if label else 'defect' }}",
        ).to_dict()
    ]
    job.survey = Survey.from_dict(data)
    job.scenarios = ScenarioList([Scenario({"label": "original"})])
    path = tmp_path / "jobs.ep"
    job.save(str(path))
    return job, path


@pytest.mark.parametrize(
    "override", ["model", "model_list", "agent_list", "scenario_list", "combined"]
)
def test_component_overrides_preserve_snapshot_rounds(round_job, tmp_path, override):
    job, path = round_job
    original = job.to_dict()
    agents = AgentList.from_dict(job.agents.to_dict())
    for agent in agents:
        agent.traits["replacement"] = True
    scenarios = ScenarioList([Scenario({"label": "replacement"})])
    models = ModelList([Model("test", canned_response="replacement")])
    flags = []
    for component, obj in [
        ("agent_list", agents),
        ("scenario_list", scenarios),
        ("model_list", models),
    ]:
        if override in (component, "combined"):
            component_path = tmp_path / f"{component}.ep"
            obj.save(str(component_path))
            flags.extend([f"--{component}", str(component_path)])
    if override == "model":
        flags.extend(["--model", "test"])
    output = tmp_path / "results.ep"
    invocation = CliRunner().invoke(
        app, ["run", str(path), "--local", "--fresh", "--output", str(output), *flags]
    )
    assert invocation.exit_code == 0, invocation.output
    envelope = json.loads(invocation.output)
    assert envelope["status"] == "ok", envelope
    results = Results.load(str(output))
    assert len(results) == 6
    assert [
        sum(row.data["iteration"] == iteration for row in results)
        for iteration in range(3)
    ] == [2, 2, 2]
    state = results.shared_state["bindings"][0]["exit_snapshots"][0]["state"]["game"]
    assert state["rounds"] == {
        str(i): {"0": "cooperate", "1": "cooperate"} for i in range(1, 4)
    }
    if override in ("agent_list", "combined"):
        assert all(row.agent.traits["replacement"] for row in results)
    if override in ("scenario_list", "combined"):
        assert all(row.scenario["label"] == "replacement" for row in results)
    if override in ("model_list", "combined"):
        assert all(row.model.canned_response == "replacement" for row in results)
    assert Jobs.load(str(path)).to_dict() == original


@pytest.mark.parametrize("name", CASES)
def test_cli_saved_scripted_examples(tmp_path, name):
    _, job, _ = scripted_case(name)
    path, output = tmp_path / "jobs.ep", tmp_path / "results.ep"
    job.save(str(path))
    invocation = CliRunner().invoke(
        app,
        [
            "run",
            str(path),
            "--model",
            "test",
            "--local",
            "--fresh",
            "--output",
            str(output),
        ],
    )
    assert invocation.exit_code == 0, invocation.output
    envelope = json.loads(invocation.output)
    assert envelope["status"] == "ok", envelope
    results = Results.load(str(output))
    check_case(name, results)
    assert results.survey.to_dict() == job.survey.to_dict()


@pytest.mark.parametrize("replace_count", [1, 2])
def test_override_respects_explicit_assignments(tmp_path, replace_count):
    job = Jobs(
        survey=Survey(
            [QuestionCompute(question_name="q", question_text="{{ topic }}")]
        ),
        agents=[Agent(traits={"person": i}) for i in range(2)],
        scenarios=[Scenario({"topic": i}) for i in range(2)],
        models=[Model("test")],
    ).zip_assign()
    path, agents_path, output = (
        tmp_path / "jobs.ep",
        tmp_path / "agents.ep",
        tmp_path / "results.ep",
    )
    job.save(str(path))
    AgentList([Agent(traits={"person": i + 10}) for i in range(replace_count)]).save(
        str(agents_path)
    )
    invocation = CliRunner().invoke(
        app,
        [
            "run",
            str(path),
            "--agent_list",
            str(agents_path),
            "--local",
            "--fresh",
            "--output",
            str(output),
        ],
    )
    envelope = json.loads(invocation.output)
    if replace_count == 1:
        assert invocation.exit_code != 0
        assert envelope["status"] == "error"
        assert "Cannot change the number of agents" in envelope["error"]["message"]
        assert not output.exists()
    else:
        assert invocation.exit_code == 0, invocation.output
        assert envelope["status"] == "ok"
        results = Results.load(str(output))
        assert [(r.agent.traits["person"], r.scenario["topic"]) for r in results] == [
            (10, 0),
            (11, 1),
        ]
