"""Verify saved typed rows and the failure envelope consumed by auditors."""

import json
import zipfile

from click.testing import CliRunner

from edsl import Scenario, ScenarioList
from edsl.__main__ import app


def test_check_rows_evaluates_every_row_and_reports_only_requested_fields(tmp_path):
    path = tmp_path / "data.ep"
    records = [(2, 2, False), (None, 4, True), (3, 2, True), ("4", 5, False)]
    ScenarioList(
        [
            Scenario(
                {
                    "key": f"site-{i}",
                    "n": n,
                    "cap": cap,
                    "has.waiver": waived,
                    "private": "canary",
                }
            )
            for i, (n, cap, waived) in enumerate(records)
        ]
    ).git.save(path, sync_coop=False)
    source = path.read_bytes()
    cmd = [
        "scenarios",
        "check-rows",
        str(path),
        "--require",
        "bounds",
        "n is not None and 0 <= n <= cap",
        "--require",
        "exempt",
        'row["has.waiver"] or n == cap',
    ]
    runner = CliRunner()
    limit = runner.invoke(app, [*cmd, "--limit", "1", "--id-field", "key"])
    assert limit.exit_code == 5, limit.output
    assert "canary" not in limit.output
    report = json.loads(limit.output)["error"]["details"][0]
    assert report == {
        "rows": 4,
        "failed_count": 3,
        "skipped_by_rule": {"bounds": 0, "exempt": 0},
        "failures_by_rule": {"bounds": 3, "exempt": 1},
        "failed": [{"row_index": 1, "rules": ["bounds"], "id": "site-1"}],
        "truncated": True,
    }
    full = runner.invoke(app, [*cmd, "--limit", "0"])
    report = json.loads(full.output)["error"]["details"][0]
    assert not report["truncated"]
    assert report["failed"][-1] == {
        "row_index": 3,
        "rules": ["bounds", "exempt"],
        "evaluation_errors": {"bounds": "TypeError"},
    }
    assert path.read_bytes() == source


def test_row_check_rejects_invalid_rules_and_explains_bad_fields(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps(ScenarioList([Scenario({"age": 21})]).to_dict()))
    runner = CliRunner()
    cmd = ["scenarios", "check-rows", str(path), "--require", "adult"]
    for args in [["age >= 21"], ["age >= 18", "--id-field", "age"]]:
        result = runner.invoke(app, [*cmd, *args])
        assert (
            result.exit_code == 0
            and json.loads(result.output)["data"]["failed_count"] == 0
        )
    for args in [
        ["age >="],
        ["age.bit_length()"],
        ["True", "--require", "adult", "True"],
        ["True", "--id-field", "missing"],
    ]:
        result = runner.invoke(app, [*cmd, *args])
        assert result.exit_code == 2 and json.loads(result.output)["status"] == "error"
    for expression, kind in [
        ("unknown >= 18", "NameNotDefined"),
        ("age", "ExpectedBoolean"),
    ]:
        result = runner.invoke(app, [*cmd, expression])
        assert result.exit_code == 5
        failures = json.loads(result.output)["error"]["details"][0]["failed"]
        assert failures[0]["evaluation_errors"] == {"adult": kind}


def test_conditional_rules_are_skipped_only_when_the_guard_is_false(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(
        json.dumps(
            ScenarioList(
                [Scenario({"limit": n, "n": 2}) for n in [None, 1, 2]]
            ).to_dict()
        )
    )
    runner = CliRunner()
    cmd = [
        "scenarios",
        "check-rows",
        str(path),
        "--require-if",
        "capacity",
        "limit is not None",
        "n <= limit",
    ]
    checked = runner.invoke(app, cmd)
    assert checked.exit_code == 5
    detail = json.loads(checked.output)["error"]["details"][0]
    assert detail["skipped_by_rule"] == {"capacity": 1}
    assert detail["failed"] == [{"row_index": 1, "rules": ["capacity"]}]
    invalid = runner.invoke(app, [*cmd, "--require", "capacity", "True"])
    assert invalid.exit_code == 2
    bad_guard = runner.invoke(app, [*cmd[:-2], "n", "True"])
    errors = json.loads(bad_guard.output)["error"]["details"][0]["failed"]
    assert all(
        item["evaluation_errors"]["capacity"] == "ExpectedBoolean" for item in errors
    )


def test_show_exports_ordered_json_rows_and_reopens_as_a_native_package(tmp_path):
    from click.testing import CliRunner
    from edsl import ScenarioList
    from edsl.__main__ import app
    import json

    source = tmp_path / "source.ep"
    rows = [{"id": "003", "value": None}, {"id": "007", "value": [True, 0]}]
    ScenarioList(rows).git.save(source)
    runner = CliRunner()
    args = ["scenarios", "show", str(source)]
    page = json.loads(
        runner.invoke(app, args + ["--offset", "1", "--limit", "1"]).output
    )["data"]
    assert page["rows"] == rows[1:] and not page["has_more"] and page["total_rows"] == 2
    exported = tmp_path / "rows.json"
    result = runner.invoke(app, args + ["--limit", "0", "-o", str(exported)])
    assert result.exit_code == 0 and json.loads(exported.read_text()) == rows
    saved = tmp_path / "saved.ep"
    assert (
        runner.invoke(
            app, ["scenarios", "create", "--from-json", str(exported), "-o", str(saved)]
        ).exit_code
        == 0
    )
    assert [dict(row) for row in ScenarioList.git.load(saved, sync_coop=False)] == rows
    assert runner.invoke(app, args + ["-o", str(source)]).exit_code == 2
    empty = json.loads(runner.invoke(app, args + ["--offset", "9"]).output)["data"]
    assert empty["rows"] == [] and not empty["has_more"]


def test_show_explains_how_to_rebuild_a_non_git_package_from_csv(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "buildable.ep"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "manifest.json",
            json.dumps({"edsl_class_name": "ScenarioList", "n_scenarios": 1}),
        )
        archive.writestr("scenarios/000001.json", json.dumps({"frame": "compact"}))
    original = source.read_bytes()
    runner = CliRunner()
    result = runner.invoke(app, ["scenarios", "show", source.name])
    assert result.exit_code == 5, result.output
    issue = json.loads(result.output)["error"]
    assert issue["code"] == "VALIDATION_ERROR"
    assert "not a Git-backed EDSL package" in issue["message"]

    create = "ep scenarios create --from-csv SOURCE.csv --output rebuilt.ep"
    show = "ep scenarios show rebuilt.ep --limit 1"
    assert create in issue["suggestion"] and show in issue["suggestion"]
    assert "total_rows" in issue["suggestion"]
    (tmp_path / "SOURCE.csv").write_text("frame\ncompact\nlongtail\n")
    created = runner.invoke(app, create.split()[1:])
    assert created.exit_code == 0, created.output
    reopened = runner.invoke(app, show.split()[1:])
    assert reopened.exit_code == 0, reopened.output
    data = json.loads(reopened.output)["data"]
    assert data["total_rows"] == 2 and data["rows"] == [{"frame": "compact"}]
    assert source.read_bytes() == original


def test_validate_rejects_a_manifest_only_package_with_actionable_json(
    tmp_path, monkeypatch
):
    from click.testing import CliRunner
    from edsl.__main__ import app
    from edsl.base import git_package
    import json
    import zipfile

    path = tmp_path / "sample.ep"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps({"edsl_class_name": "ScenarioList"}))
    worktree = tmp_path / "unpacked"

    def temporary_worktree(_):
        worktree.mkdir()
        return worktree

    monkeypatch.setattr(git_package, "new_package_worktree", temporary_worktree)
    result = CliRunner().invoke(
        app, ["validate", "--file", str(path), "--type", "scenario_list"]
    )
    issue = json.loads(result.output)["error"]
    assert result.exit_code == 5 and issue["code"] == "INVALID_PACKAGE"
    assert str(path) in issue["message"] and str(worktree) not in issue["message"]
    assert "scenarios create --from-json" in issue["suggestion"]
    assert not worktree.exists() and path.exists()
