import json

from click.testing import CliRunner

from edsl.__main__ import app


def test_report_check_validates_compiled_study_report(tmp_path):
    writeup = tmp_path / "writeup"
    writeup.mkdir()
    (writeup / "report.md").write_text("# Findings\n", encoding="utf-8")
    (writeup / "report.html").write_text("<html><body><h1>Findings</h1></body></html>", encoding="utf-8")

    result = CliRunner().invoke(app, ["report", "check", "--root", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["passed"] is True


def test_report_check_returns_bounded_structured_issues(tmp_path):
    (tmp_path / "writeup").mkdir()

    result = CliRunner().invoke(app, ["report", "check", "--root", str(tmp_path)])

    assert result.exit_code == 5
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "REPORT_CHECK_FAILED"
    assert len(payload["error"]["details"]) == 2


def test_report_check_preflights_yaml_title_plus_body_h1(tmp_path):
    writeup = tmp_path / "writeup"
    writeup.mkdir()
    (writeup / "report.md").write_text(
        "---\ntitle: Favorite Color\n---\n\n# Summary\n\n## Methods\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["report", "check", "--root", str(tmp_path)])

    assert result.exit_code == 5
    payload = json.loads(result.output)
    issues = [item["issue"] for item in payload["error"]["details"]]
    assert "Missing or empty writeup/report.html" in issues
    assert any("YAML title plus H1" in issue and "line(s) 5" in issue for issue in issues)
