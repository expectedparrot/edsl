"""Verify saved typed rows and the failure envelope consumed by auditors."""

import json

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
