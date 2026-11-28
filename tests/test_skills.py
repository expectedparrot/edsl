import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

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
        assert package["guide_command"] == "ep skills guide Green"
        assert package["guide_url"].endswith("/green/docs_content/workflow.md")
        assert "MaxDiff" in package["methods"]
        assert package["repository"] == "https://github.com/expectedparrot/green"
        assert package["readme_url"] == "https://raw.githubusercontent.com/expectedparrot/green/HEAD/README.md"
        assert all(skill["name"] != "Green" for skill in data["results"])

    human = runner.invoke(skills_command, ["search", "MaxDiff", "--human"])
    assert human.exit_code == 0
    assert "Green [external package]" in human.output
    assert package["readme_url"] in human.output
    assert package["guide_command"] in human.output


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
        prefix = entry["repository"].replace("github.com", "raw.githubusercontent.com") + "/HEAD/"
        assert entry["guide_url"].startswith(prefix)
        assert entry["guide_url"].endswith(".md")
        cli = entry["repository"].rsplit("/", 1)[-1]
        assert entry["installed_guide_command"] == f"{cli} guide"
        if "installed_next_command" in entry:
            assert entry["installed_next_command"] == f"{cli} next"
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


def test_package_search_recovers_supported_partial_matches():
    runner = CliRunner()
    for query, expected in (
        ("forecasting scoring probabilities", ["Vorhersage"]),
        ("staff hiring application database", ["Spence"]),
        ("sensitivity analysis", []),  # "price sensitivity" and "conjoint analysis" are separate methods.
    ):
        result = runner.invoke(skills_command, ["search", query, "--limit", "1"])
        assert result.exit_code == 0, result.output
        assert [p["name"] for p in json.loads(result.output)["data"]["packages"]] == expected


def test_partial_package_search_weights_rare_terms(tmp_path, monkeypatch):
    from edsl.skills import cli

    monkeypatch.setattr(cli, "SKILLS_ROOT", tmp_path)
    catalog = [
        {"name": name, "methods": [], "description": terms}
        for name, terms in [
            ("Alpha", "candidate panel"),
            ("Beta", "candidate attrition"),
            ("Gamma", "candidate panel"),
            ("Delta", "candidate panel"),
        ]
    ]
    (tmp_path / "packages.json").write_text(json.dumps(catalog))
    result = CliRunner().invoke(skills_command, ["search", "candidate panel attrition", "--limit", "2"])
    assert result.exit_code == 0, result.output
    assert [p["name"] for p in json.loads(result.output)["data"]["packages"]] == ["Beta", "Alpha"]


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

def test_package_guide_reads_named_package_before_install(monkeypatch):
    guide = "# Étude\n"
    fetch = Mock(return_value=Mock(content=guide.encode("utf-8")))
    monkeypatch.setattr(requests, "get", fetch)
    runner = CliRunner()
    result = runner.invoke(skills_command, ["guide", "zWiLl"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    url = "https://raw.githubusercontent.com/expectedparrot/zwill/HEAD/zwill/guides/agent-workflow.md"
    assert data == {"name": "Zwill", "guide_url": url, "content": guide,
                    "installed_guide_command": "zwill guide", "installed_next_command": "zwill next"}
    fetch.assert_called_once_with(url, timeout=20)
    assert runner.invoke(skills_command, ["guide", "Zwill", "--human"]).output == guide


def test_package_guide_unknown_name_does_not_fetch(monkeypatch):
    fetch = Mock()
    monkeypatch.setattr(requests, "get", fetch)
    result = CliRunner().invoke(skills_command, ["guide", "unknown"])
    assert result.exit_code == 3
    assert json.loads(result.output)["error"]["code"] == "PACKAGE_NOT_FOUND"
    fetch.assert_not_called()


@pytest.mark.parametrize("response", [
    Mock(raise_for_status=Mock(side_effect=requests.HTTPError("404"))),
    Mock(content=b""),
    Mock(content=b"\xff"),
    requests.Timeout("timed out"),
])
def test_package_guide_fetch_failures_include_source(monkeypatch, response):
    fetch = Mock(side_effect=response) if isinstance(response, Exception) else Mock(return_value=response)
    monkeypatch.setattr(requests, "get", fetch)
    result = CliRunner().invoke(skills_command, ["guide", "Zwill"])
    assert result.exit_code == 6
    failure = json.loads(result.output)["error"]
    assert failure["code"] == "REMOTE_ERROR"
    assert "raw.githubusercontent.com/expectedparrot/zwill/" in failure["suggestion"]

def test_stateless_package_uses_readme_and_omits_project_command(monkeypatch):
    monkeypatch.setattr(requests, "get", Mock(return_value=Mock(content=b"# Quick start")))
    result = CliRunner().invoke(skills_command, ["guide", "conversation"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["guide_url"].endswith("/README.md")
    assert data["installed_guide_command"] == "conversation guide"
    assert "installed_next_command" not in data
