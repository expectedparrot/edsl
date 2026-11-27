import json

import pytest
from click.testing import CliRunner

from edsl import (
    Agent,
    AgentList,
    Collection,
    JudgmentModel,
    Jobs,
    Model,
    ModelList,
    Prompt,
    Results,
    Scenario,
    ScenarioList,
    Survey,
)
from edsl.__main__ import app
from edsl.cli_shared import GIT_OBJECT_MODULES
from edsl.utilities.object_markdown import MarkdownPageError, object_markdown


def inspect(path, *args):
    return CliRunner().invoke(app, ["inspect", str(path), "--markdown", *args])


def test_agent_cards_and_page_boundaries(tmp_path):
    agents = AgentList(
        [
            Agent(
                {"city": f"City {i}", "bio": "Long introduction. " * 15},
                name=f"Person {i}",
                instruction="Use complete sentences.",
            )
            for i in range(1, 6)
        ]
    )
    path = tmp_path / "agents.ep"
    agents.git.save(path)
    result = inspect(path, "--page", "2", "--page-size", "2")
    assert result.exit_code == 0, result.output
    assert result.output.rstrip() == agents.to_markdown(page=2, page_size=2)
    assert "Agents 3–4 of 5 · Page 2 of 3" in result.output
    assert "### Agent 3 — Person 3" in result.output
    assert (
        "**city**  \nCity 3" in result.output
        and "**Instructions**  \nUse complete sentences." in result.output
    )
    assert "Person 2" not in result.output and "Person 5" not in result.output
    assert "Agents 5–5 of 5" in inspect(path, "--page", "3", "--page_size", "2").output
    for flags in (
        ["--page", "4", "--page-size", "2"],
        ["--page", "0"],
        ["--page-size", "-1"],
    ):
        error = inspect(path, *flags)
        assert (
            error.exit_code == 2
            and json.loads(error.output)["error"]["code"] == "USAGE_ERROR"
        )
    assert inspect(path, "--sample", "1").exit_code == 2
    assert inspect(path, "--save", "-").exit_code == 2
    original = CliRunner().invoke(app, ["inspect", str(path)])
    assert json.loads(original.output)["status"] == "ok"


def test_empty_collection_and_last_scenario_page():
    assert "No agents." in AgentList([]).to_markdown()
    with pytest.raises(MarkdownPageError):
        AgentList([]).to_markdown(page=2)
    scenarios = ScenarioList(
        [Scenario({"a": "first"}), Scenario({"b": "second"}), Scenario({"b": "last"})]
    )
    assert "| a " in scenarios.to_markdown() and "| b " in scenarios.to_markdown()
    assert "last" in scenarios.to_markdown(page=2, page_size=2)
    assert "first" not in scenarios.to_markdown(page=2, page_size=2)


def test_all_package_types_and_prompt(tmp_path):
    job = Jobs.example(test_model=True)
    collection = Collection("Examples").add(
        "survey", "12345678-1111-2222-3333-123456789abc"
    )
    objects = [
        job,
        job.agents,
        job.models,
        job.scenarios,
        job.survey,
        collection,
        job.survey.to_evaluation().by(JudgmentModel()),
        Results.example(),
    ]
    assert {type(obj).__name__ for obj in objects} == set(GIT_OBJECT_MODULES)
    for obj in objects:
        name = type(obj).__name__
        package = tmp_path / (name + ".ep")
        obj.git.save(package)
        serialized = tmp_path / (name + ".json")
        serialized.write_text(json.dumps(obj.to_dict()))
        for file in (package, serialized):
            result = inspect(file, "--page-size", "2")
            assert result.exit_code == 0, result.output
            assert result.output.rstrip() == object_markdown(obj, page_size=2)
    assert "**Answers**" in objects[-1].to_markdown()
    assert "12345678-1111-2222-3333-123456789abc" in collection.to_markdown()
    assert "**Service**" in job.models.to_markdown()
    assert "### Agent 1" in job.to_markdown(page=2, page_size=2)
    prompt = Prompt("First\nSecond\nThird")
    assert "Lines 3–3 of 3" in prompt.to_markdown(page=2, page_size=2)
    assert "Third" in prompt.to_markdown(page=2, page_size=2)


def test_inspect_serialized_individuals_and_stdin():
    for obj in [
        Agent({"occupation": "teacher"}),
        Scenario({"topic": "Lunch"}),
        Model("test"),
        Prompt("Hello"),
    ]:
        result = CliRunner().invoke(
            app, ["inspect", "-", "--markdown"], input=json.dumps(obj.to_dict())
        )
        assert result.exit_code == 0, result.output
        assert result.output.rstrip() == obj.to_markdown()


def test_survey_page_preserves_original_route():
    survey = Survey.example()
    assert "**2." in object_markdown(survey, page=2, page_size=1)
    assert "**1." not in object_markdown(survey, page=2, page_size=1)
    assert "Go to question 3" in object_markdown(survey, page_size=1)


def test_file_attachments_are_summarized():
    from edsl import FileStore

    file = FileStore.example()
    scenario = Scenario({"file": file})
    rendered = scenario.to_markdown()
    assert file.mime_type in rendered and file.base64_string not in rendered


def test_survey_show_can_page_with_labels(tmp_path):
    survey = Survey.example()
    path = tmp_path / "survey.ep"
    survey.git.save(path)
    args = ["surveys", "show", str(path), "--markdown", "--with-question-names"]
    page = CliRunner().invoke(app, [*args, "--page", "2", "--page-size", "1"])
    assert page.exit_code == 0, page.output
    assert "Questions 2–2 of 3" in page.output
    assert f"**2. [{survey.question_names[1]}]" in page.output
    full = CliRunner().invoke(app, args)
    assert full.output.rstrip() == survey.to_markdown(
        style="questionnaire", with_question_names=True
    )


def test_preview_skips_runtime_agent_traits():
    def dynamic_traits_function():
        raise AssertionError("Preview attempted to run a dynamic trait function")

    agent = Agent(dynamic_traits_function=dynamic_traits_function)
    assert "computed at runtime" in agent.to_markdown()


def test_long_scenario_fields_stack_and_escape():
    scenario = Scenario({"city|state": "Town <west>", "memo": "Long text. " * 10})
    rendered = scenario.to_markdown()
    assert r"**city\|state**" in rendered
    assert "Town &lt;west&gt;" in rendered
    assert "Long text. Long text." in rendered
