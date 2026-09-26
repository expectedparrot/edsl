import json

from click.testing import CliRunner

from edsl.__main__ import app


def test_present_resolves_relative_file_and_emits_host_marker(tmp_path, monkeypatch):
    artifact = tmp_path / "report.html"
    artifact.write_text("<h1>Report</h1>", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["present", "report.html", "--title", "Study report"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["path"] == str(artifact)
    assert data["title"] == "Study report"
    assert data["presentation_marker"] == f"PRESENT_FILE:{artifact}\tStudy report"


def test_present_reports_missing_file_as_structured_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["present", "missing.html"])

    assert result.exit_code == 3
    assert json.loads(result.output)["error"]["code"] == "PRESENTATION_FILE_NOT_FOUND"
