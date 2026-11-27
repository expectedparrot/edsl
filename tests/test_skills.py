import json
from pathlib import Path

from click.testing import CliRunner

from edsl.skills.cli import _anchor_slug
from edsl.skills.cli import skills as skills_command


def test_html_heading_and_link_fragments_share_a_slug():
    heading = "Per-question model + system prompt (`thinking_question`)"
    fragment = "per-question-model--system-prompt-thinking_question"

    assert _anchor_slug(heading) == _anchor_slug(fragment)


def test_skills_routing_lists_fetchable_version_matched_examples():
    result = CliRunner().invoke(skills_command, ["list", "--routing"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    shared_state = next(
        item for item in data["skills"] if item["name"] == "edsl-shared-state"
    )
    path = "shared_state/machine_primitives/running_ledger.py"
    assert shared_state["example_count"] > 0
    assert shared_state["example_commands"][path] == (
        "ep skills show edsl-shared-state --example " + path
    )


def test_skills_show_fetches_an_example_source_through_the_cli():
    path = "shared_state/machine_primitives/running_ledger.py"
    result = CliRunner().invoke(
        skills_command,
        ["show", "edsl-shared-state", "--example", path],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    expected = Path("edsl/examples") / path
    assert data["example"] == path
    assert data["content"] == expected.read_text(encoding="utf-8")


def test_skills_search_indexes_example_source():
    result = CliRunner().invoke(skills_command, ["search", "fold", "--snippets"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    shared_state = next(
        item for item in data["results"] if item["name"] == "edsl-shared-state"
    )
    assert shared_state["match"] == "content"
    assert shared_state["snippet"]["path"].startswith("edsl/examples/shared_state/")


def test_search_and_link_commands_retrieve_the_identified_resource():
    import shlex

    runner = CliRunner()

    def data(args):
        result = runner.invoke(skills_command, args)
        assert result.exit_code == 0, result.output
        return json.loads(result.output)["data"]

    def fetch(command):
        args = shlex.split(command)
        assert args[:3] == ["ep", "skills", "show"]
        return data(args[2:])

    row = next(row for row in data(["search", "edsl-surveys"])["results"]
               if row["name"] == "edsl-surveys")
    entry = fetch(row["show_command"])
    assert [item["path"] for item in entry["files"]] == ["SKILL.md"]
    for path, command in entry["reference_commands"].items():
        assert fetch(command)["files"][0]["path"] == path
    assert "references/survey-reference.md" in entry["reference_commands"]

    example = next(row for row in data(["search", "fold", "--snippets"])["results"]
                   if row["name"] == "edsl-shared-state")["snippet"]
    assert "edsl/examples/" + fetch(example["show_command"])["example"] == example["path"]


def test_item_completion_script_uses_the_exposed_interview(tmp_path):
    import csv
    import subprocess
    import sys

    from edsl import Agent, Model, Question, Results, Scenario, Survey
    from edsl.results.result import Result

    survey = Survey([Question("numerical", question_name="speed", question_text="Rate speed.")])
    def interview(wave, shown, answer):
        return Result(agent=Agent(), scenario=Scenario({"wave": wave}), model=Model("test"),
                      iteration=0, survey=survey, answer={"speed": answer},
                      randomization={"exposure_order": shown})

    results = Results(survey=survey, data=[
        interview(1, ["speed"], 0), interview(2, ["speed"], None), interview(2, [], 4),
        interview(3, [], 9),
    ])
    path = tmp_path / "waves.ep"
    results.git.save(path)
    script = "scripts/item_completion.py"
    reply = CliRunner().invoke(skills_command, ["show", "edsl-results-validation", "--script", script, "--human"])
    assert reply.exit_code == 0, reply.output
    program = tmp_path / "audit.py"
    program.write_text(reply.output)
    output = tmp_path / "coverage.csv"
    subprocess.run([sys.executable, str(program), str(path), "--wave-field", "wave",
                    "--item", "speed", "--min-score", "0", "--max-score", "10",
                    "--output", str(output)], check=True)
    with output.open(newline="") as file:
        assert list(csv.reader(file)) == [
            ["wave", "item", "exposed", "answered", "mean"],
            ["1", "speed", "1", "1", "0.0"],
            ["2", "speed", "1", "0", ""],
            ["3", "speed", "0", "0", ""],
        ]
