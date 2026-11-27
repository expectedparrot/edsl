import warnings

from edsl.results.cost_reconciliation import reconcile_cost


def status(cost, total=1, state="completed"):
    return {
        "status": state,
        "latest_job_run_details": {
            "cost_usd": cost,
            "interview_details": {
                "total_interviews": total,
                "completed_interviews": total,
            },
        },
    }


def row(cost, cached=False):
    return {
        "answer": {"q": 42},
        "raw_model_response": {"q_cost": cost},
        "cache_used_dict": {"q": cached},
    }


def test_large_accounting_discrepancy_warns_without_raising_or_mutating(capsys):
    results = [row(0.05601)]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        actual = reconcile_cost(results, status(0.7398))
    assert actual["status"] == "mismatch"
    assert actual["remote_cost_usd"] == 0.7398
    assert "REMOTE_COST_MISMATCH" in capsys.readouterr().err
    assert results == [row(0.05601)]


def test_cached_historical_cost_does_not_create_false_discrepancy():
    assert reconcile_cost([row(9, True)], status(0))["status"] == "matched"


def test_rounding_tolerance():
    assert reconcile_cost([row(0.100001)], status(0.1))["status"] == "matched"


def test_partial_pending_and_unknown_costs_are_not_comparable():
    assert reconcile_cost([row(0.1)], status(1, total=2))["status"] == "not_comparable"
    assert (
        reconcile_cost([row(0.1)], status(1, state="running"))["status"]
        == "not_comparable"
    )
    assert (
        reconcile_cost([row(None)], status(1))["reason"]
        == "missing_response_cost_metadata"
    )


def test_retry_costs_have_different_scope():
    result = row(0.1)
    result["raw_model_response"]["q_response_metadata"] = {
        "provider_calls_attempted": 2
    }
    assert (
        reconcile_cost([result], status(1))["reason"]
        == "retries_may_have_separate_charges"
    )


def test_jobs_results_saves_answers_and_warns_without_resubmitting(
    tmp_path, monkeypatch
):
    import json
    from click.testing import CliRunner
    from edsl import Agent, Model, Results, Scenario, Survey
    from edsl.results import Result
    from edsl.__main__ import app
    from edsl.coop import Coop

    results = Results(
        survey=Survey([]),
        data=[
            Result(
                agent=Agent(),
                scenario=Scenario(),
                model=Model("test"),
                iteration=0,
                **row(0.05601),
            )
        ],
    )
    calls = []

    def remote_status(self, **kwargs):
        calls.append("status")
        return {**status(0.7398), "results_uuid": "saved-results"}

    def pull(self, *args, **kwargs):
        calls.append("pull")
        return results

    monkeypatch.setattr(Coop, "new_remote_inference_get", remote_status)
    monkeypatch.setattr(Coop, "pull", pull)
    target = tmp_path / "results.ep"
    outcome = CliRunner().invoke(
        app, ["jobs", "results", "existing-job", "--output", str(target)]
    )
    assert outcome.exit_code == 0, outcome.output
    envelope = json.loads(outcome.output)
    assert envelope["data"]["cost_reconciliation"]["status"] == "mismatch"
    assert "REMOTE_COST_MISMATCH" in envelope["warnings"][0]
    assert Results.git.load(str(target))[0].answer == {"q": 42}
    assert calls == ["status", "pull"]


def test_cost_receipt_round_trip_preserves_zero_cache_hits_and_unknowns(tmp_path):
    import json
    from click.testing import CliRunner
    from edsl import Agent, Model, Results, Scenario, Survey
    from edsl.__main__ import app
    from edsl.results import Result
    from edsl.results.cost_reconciliation import recorded_costs

    def response(prices, flags):
        return Result(
            agent=Agent(),
            scenario=Scenario(),
            model=Model("test"),
            iteration=0,
            answer={q: None if q == "skipped" else "yes" for q in prices},
            raw_model_response={f"{q}_cost": cost for q, cost in prices.items()},
            cache_used_dict=flags,
        )

    row = response(
        {"a": 0.25, "b": 0.5, "zero": 0, "skipped": None, "unpriced": None},
        {"a": False, "b": True, "zero": False, "unpriced": True},
    )
    results = Results(survey=Survey([]), data=[row])
    p = tmp_path / "study.ep"
    results.git.save(p, sync_coop=False)
    loaded = Results.git.load(p, sync_coop=False)
    assert loaded[0]["cache_used_dict"] == row["cache_used_dict"]
    assert loaded.compute_job_cost() == 0.25
    report = recorded_costs(loaded)
    assert report["actual_cost_usd"] == 0.25
    assert report["known_cached_value_usd"] == 0.5
    assert report["unpriced_cached_calls"] == 1
    assert report["unpriced_uncached_calls"] == 0
    assert recorded_costs(Results.from_jsonl(results.to_jsonl())) == report

    legacy = response({"paid": 1.2}, {})
    assert recorded_costs([legacy])["unknown_cache_status_calls"] == 1
    assert recorded_costs([legacy])["actual_cost_usd"] is None
    assert recorded_costs([legacy])["known_value_unknown_cache_status_usd"] == 1.2
    old = Results(survey=Survey([]), data=[legacy])
    old_path = tmp_path / "old.ep"
    old.git.save(old_path, sync_coop=False)
    old_from_disk = Results.git.load(old_path, sync_coop=False)
    commit = old_from_disk.git.commit
    assert "cache_used_dict" not in json.loads(old_from_disk.to_jsonl().splitlines()[-1])
    old_from_disk.git.save(old_path, sync_coop=False)
    assert Results.git.load(old_path, sync_coop=False).git.commit == commit

    # A real zero differs from an uncached call for which no provider price was stored.
    mixed = Results(survey=Survey([]), data=[row, response({"x": "NA"}, {"x": False})])
    p = tmp_path / "mixed.ep"
    mixed.git.save(p, sync_coop=False)
    runner = CliRunner()
    out = runner.invoke(app, ["results", "cost", str(p)])
    assert out.exit_code == 0, out.output
    result = json.loads(out.output)
    assert result["data"]["cost"] is None
    assert result["data"]["known_uncached_cost_usd"] == 0.25
    assert result["data"]["unpriced_uncached_calls"] == 1
    assert result["warnings"][0]["code"] == "INCOMPLETE_COST_METADATA"
    ledger = tmp_path / "ledger.jsonl"
    write = runner.invoke(
        app, ["costs", "log", "--actual-from", str(p), "--output", str(ledger)]
    )
    assert write.exit_code == 0, write.output
    assert json.loads(ledger.read_text())["actual_cost_usd"] is None
