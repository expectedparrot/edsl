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
