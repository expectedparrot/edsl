import json
from pathlib import Path

from click.testing import CliRunner

from edsl.skills.cli import _anchor_slug
from edsl.skills.cli import skills as skills_command


def test_html_heading_and_link_fragments_share_a_slug():
    heading = "Per-question model + system prompt (`thinking_question`)"
    fragment = "per-question-model--system-prompt-thinking_question"

    assert _anchor_slug(heading) == _anchor_slug(fragment)


def test_skills_routing_lists_linked_worked_example_reference():
    result = CliRunner().invoke(skills_command, ["list", "--routing"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    shared_state = next(
        item for item in data["skills"] if item["name"] == "edsl-shared-state"
    )
    path = "references/examples.md"
    assert path in shared_state["references"]
    assert shared_state["reference_commands"][path] == (
        "ep skills show edsl-shared-state --reference " + path
    )


def test_skills_show_fetches_worked_examples_as_a_reference():
    path = "references/examples.md"
    result = CliRunner().invoke(
        skills_command,
        ["show", "edsl-shared-state", "--reference", path],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    expected = Path("edsl/skills/edsl-shared-state") / path
    assert data["reference"] == path
    assert data["files"][0]["content"] == expected.read_text(encoding="utf-8")


def test_skills_search_indexes_worked_example_references():
    result = CliRunner().invoke(skills_command, ["search", "fold", "--snippets"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    shared_state = next(
        item for item in data["results"] if item["name"] == "edsl-shared-state"
    )
    assert shared_state["match"] == "content"
    assert shared_state["snippet"]["path"] == "references/examples.md"
