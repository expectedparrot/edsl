import json
import shlex

import pytest
from click.testing import CliRunner

from edsl import Agent, AgentList, Model, ModelList, Scenario, ScenarioList
from edsl.__main__ import app
from edsl.base.git_accessor import GitBackedInstanceAccessor


@pytest.mark.parametrize(
    "group,items,patch,expected",
    [
        (
            "agents",
            lambda: AgentList([Agent(name="Alice", traits={"x": 1, "y": 2})]),
            {"traits": {"x": 4}},
            {"traits": {"x": 4, "y": 2}, "name": "Alice"},
        ),
        (
            "scenarios",
            lambda: ScenarioList([Scenario({"x": 1, "y": 2})]),
            {"x": 4},
            {"x": 4, "y": 2},
        ),
        (
            "models",
            lambda: ModelList([Model("test", canned_response="A")]),
            {"parameters": {"canned_response": "B"}},
            {"model": "test"},
        ),
    ],
)
def test_local_list_edits(tmp_path, monkeypatch, group, items, patch, expected):
    original = items()
    path = tmp_path / "original.ep"
    original.git.save(path)
    dest = tmp_path / "revised.ep"

    def reject_sync(*args, **kwargs):
        raise AssertionError("Local editing contacted Coop")

    monkeypatch.setattr(
        GitBackedInstanceAccessor, "_coop_pull_if_remote_updated", reject_sync
    )

    def run(*args, success=True):
        res = CliRunner().invoke(app, [group, "edit-item", *map(str, args)])
        assert (res.exit_code == 0) == success, res.output
        assert json.loads(res.output)["status"] == ("ok" if success else "error")

    before = path.read_bytes()
    run(path, "--index", "0", "--patch", json.dumps(patch), "-o", dest)
    assert path.read_bytes() == before
    edited = type(original).git.load(dest, sync_coop=False)
    data = edited[0].to_dict(add_edsl_version=False)
    for key, value in expected.items():
        assert data[key] == value
    if group == "models":
        assert edited[0].canned_response == "B"

    run(dest, "--insert", json.dumps(data))
    assert len(type(original).git.load(dest, sync_coop=False)) == 2
    run(dest, "--remove", "--index", "0")
    assert len(type(original).git.load(dest, sync_coop=False)) == 1
    before = dest.read_bytes()
    run(dest, "--remove", "--index", "1", success=False)
    assert dest.read_bytes() == before
    if group == "agents":
        run(dest, "--patch", '{"traitz":{"x":5}}', "--index", "0", success=False)
        assert dest.read_bytes() == before


def test_flat_agent_trait_error_suggests_a_replayable_patch(tmp_path):
    path = tmp_path / "roster.ep"
    AgentList(
        [Agent(name="Noor", traits={"region": "West", "years": 7, "role": "planner"})]
    ).git.save(path)
    original = path.read_bytes()
    command = ["agents", "edit-item", str(path), "--index", "0"]
    fields = {"region": "King's North", "name": "Nora", "traits": {"years": 8}}
    runner = CliRunner()
    result = runner.invoke(app, [*command, "--patch", json.dumps(fields)])
    assert result.exit_code == 5
    problem = json.loads(result.output)["error"]
    assert problem["code"] == "VALIDATION_ERROR"
    assert "region" in problem["message"]
    assert path.read_bytes() == original

    flag, corrected = shlex.split(problem["suggestion"].removeprefix("Use "))
    assert flag == "--patch"
    assert json.loads(corrected) == {
        "name": "Nora",
        "traits": {"region": "King's North", "years": 8},
    }
    retry = runner.invoke(app, [*command, flag, corrected])
    assert retry.exit_code == 0, retry.output
    agent = AgentList.git.load(path, sync_coop=False)[0]
    assert agent.name == "Nora"
    assert dict(agent.traits) == {
        "region": "King's North",
        "years": 8,
        "role": "planner",
    }


def test_edit_job_replaces_selected_components_locally(tmp_path, monkeypatch):
    from edsl import Jobs, QuestionFreeText, Survey

    survey = Survey(
        [QuestionFreeText(question_name="q", question_text="What about {{ topic }}?")]
    )
    path = tmp_path / "study.ep"
    revised_path = tmp_path / "revised.ep"
    scenarios = tmp_path / "scenarios.ep"
    models = tmp_path / "panel.ep"
    job = (
        survey.by(Scenario({"topic": "bus"}))
        .by(Agent(name="Ada", traits={"city": "Boston"}))
        .by(Model("test"))
    )
    job.git.save(path)
    ScenarioList([Scenario({"topic": "rail"})]).git.save(scenarios)
    ModelList([Model("test", canned_response="train")]).git.save(models)

    def reject_sync(*args, **kwargs):
        raise AssertionError("Local editing contacted Coop")

    monkeypatch.setattr(
        GitBackedInstanceAccessor, "_coop_pull_if_remote_updated", reject_sync
    )
    runner = CliRunner()
    before = path.read_bytes()
    args = [
        "jobs",
        "edit",
        str(path),
        "--scenarios",
        str(scenarios),
        "--models",
        str(models),
        "-o",
        str(revised_path),
    ]
    result = runner.invoke(app, args)
    assert json.loads(result.output)["status"] == "ok", result.output
    assert result.exit_code == 0
    edit = Jobs.git.load(revised_path, sync_coop=False)
    assert edit.survey == survey
    assert edit.agents[0].name == "Ada"
    assert edit.models[0].canned_response == "train"
    assert edit.scenarios[0]["topic"] == "rail"
    assert path.read_bytes() == before
    result = runner.invoke(app, ["jobs", "edit", str(path), "--survey", str(models)])
    assert result.exit_code == 5
    assert json.loads(result.output)["error"]["code"] == "VALIDATION_ERROR"
    assert path.read_bytes() == before
