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


def test_skills_search_discovers_public_packages_by_method():
    runner = CliRunner()
    for query in ("MaxDiff", "best-worst scaling", "green"):
        result = runner.invoke(skills_command, ["search", query, "--limit", "1", "--snippets"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)["data"]
        package, = data["packages"]
        assert package["name"] == "Green"
        assert package["kind"] == "external_package"
        assert "MaxDiff" in package["methods"]
        assert package["repository"] == "https://github.com/expectedparrot/green"
        assert package["readme_url"] == "https://raw.githubusercontent.com/expectedparrot/green/HEAD/README.md"
        assert all(skill["name"] != "Green" for skill in data["results"])

    human = runner.invoke(skills_command, ["search", "MaxDiff", "--human"])
    assert human.exit_code == 0
    assert "Green [external package]" in human.output
    assert package["readme_url"] in human.output


def test_skills_search_keeps_unrelated_packages_out():
    result = CliRunner().invoke(skills_command, ["search", "edsl-shared-state", "--limit", "1"])
    assert result.exit_code == 0
    data = json.loads(result.output)["data"]
    assert [row["name"] for row in data["results"]] == ["edsl-shared-state"]
    assert data["packages"] == []


def test_directory_catalog_entries_are_unique_and_searchable():
    catalog = json.loads(Path("edsl/skills/packages.json").read_text())
    assert len({p["name"].casefold() for p in catalog}) == len(catalog)
    assert len({p["repository"] for p in catalog}) == len(catalog)
    for entry in catalog:
        assert entry["repository"].startswith("https://github.com/expectedparrot/")
        assert entry["description"]
        assert entry["methods"] and all(entry["methods"])


def test_package_search_recognizes_word_forms_across_research_methods():
    runner = CliRunner()
    for query, expected in (
        ("forecast", {"Flyvbjerg", "Vorhersage"}),
        ("forecasts", {"Flyvbjerg", "Vorhersage"}),
        ("rank ballots", {"Voting"}),
        ("coded interviews", {"Bewley"}),
        ("review manuscripts", {"Katz"}),
        ("forec", set()),
        ("forecast ballots", set()),
    ):
        result = runner.invoke(skills_command, ["search", query])
        assert result.exit_code == 0, result.output
        assert {p["name"] for p in json.loads(result.output)["data"]["packages"]} == expected


def test_inflected_skill_search_reports_the_source_passage(tmp_path, monkeypatch):
    from edsl.skills import cli

    monkeypatch.setattr(cli, "SKILLS_ROOT", tmp_path)
    (tmp_path / "packages.json").write_text("[]")
    skill = tmp_path / "edsl-demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Methods\n\nAnalysts coded the interviews independently.\n")
    result = CliRunner().invoke(skills_command, ["search", "interview coding", "--snippets"])
    assert result.exit_code == 0, result.output
    hit, = json.loads(result.output)["data"]["results"]
    assert hit["match"] == "content"
    assert hit["snippet"]["path"] == "SKILL.md"
    assert "coded the interviews" in hit["snippet"]["text"]
