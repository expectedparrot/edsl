"""Compare eight portable, scripted examples locally and through a local runner.

Run from the repository root; see examples/shared_state_acceptance.md.
Scripted answers replace only model questions. State steps, flow rules, and
schedules come from the original examples. Default mode makes no model calls;
--live explicitly enables paid calls, with two small cases selected by default.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from importlib import import_module
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    ModelList,
    QuestionCompute,
    Survey,
)
from edsl.runner import Runner
from edsl.runner.serialization import serialize_job, deserialize_results

CASES = (
    "activity_poll",
    "ultimatum",
    "survey_quota",
    "posted_price_market",
    "second_price_auction",
    "uniform_price_auction",
    "appointment_booking",
    "balanced_assignment",
)


def build_case(name):
    state_id = f"acceptance-{name}-{uuid4()}"
    if name == "activity_poll":
        from examples import shared_state_activity_poll as example

        survey = example.build_survey(state_id)
        agents = example.participants(n=8)
        schedule = InterviewSchedule.grouped_round_robin("family_id", "turn")
        answers = {"activity": "{{ agent.preferred_activity }}"}
    elif name == "ultimatum":
        from examples import economic_game_ultimatum as example

        survey, complete = example.build_survey(state_id)
        agents = example.players(count=4)
        schedule = InterviewSchedule.grouped_round_robin(
            "pair_id", "turn", finalize_when=complete
        )
        answers = {
            "offer": "{{ 40 }}",
            "decision": "{{ 'accept' if shared_state.game.offer >= 30 else 'reject' }}",
        }
    else:
        example = import_module(f"examples.{name}")
        built = example.build_survey(state_id=state_id)
        survey = built[0]
        schedule = built[2] if len(built) == 3 else "serial"
        # Strip local Python answer callbacks. All behavior crossing the wire
        # must be represented by the survey, state machine, and agent data.
        agents = AgentList(
            [Agent(name=a.name, traits=dict(a.traits)) for a in example.demo_agents()]
        )
        answers = {
            "survey_quota": {
                "respondent_type": "{{ agent.group }}",
                "experience": "Shorter waiting times.",
            },
            "posted_price_market": {"quantity": "{{ agent.desired_quantity }}"},
            "second_price_auction": {"bid_0": "{{ agent.bids[0] }}"},
            "uniform_price_auction": {
                "bid_0": "{{ agent.bids[0] }}",
                "bid_1": "{{ agent.bids[1] }}",
            },
            "appointment_booking": {
                "slot": "{{ shared_state.booking.options[0] }}",
                "confirmation": "{{ agent.decision }}",
            },
            "balanced_assignment": {
                "age_group": "{{ agent.age_group }}",
                "experience": "{{ agent.experience }}",
                "response": "A clear proposal.",
            },
        }[name]
    data = survey.to_dict()
    for index, question in enumerate(survey.questions):
        if question.question_name in answers:
            data["questions"][index] = QuestionCompute(
                question_name=question.question_name,
                question_text=answers[question.question_name],
            ).to_dict()
    scripted = Survey.from_dict(data)
    jobs = []
    for variant in (survey, scripted):
        job = variant.by(agents).by(Model("test"))
        job.run_config.parameters.interview_schedule = schedule
        jobs.append(job)
    return jobs[0], jobs[1], schedule


def outcomes(results):
    """Compare substantive answers/state, excluding generated IDs/timestamps."""
    rows = sorted(
        [
            {
                "agent": r.agent.name,
                "traits": dict(r.agent.traits),
                "answer": dict(r.answer),
            }
            for r in results
        ],
        key=lambda row: json.dumps([row["agent"], row["traits"]], sort_keys=True),
    )
    snapshots = sorted(
        [
            snapshot
            for binding in results.shared_state["bindings"]
            for snapshot in binding["exit_snapshots"]
        ],
        key=lambda item: json.dumps(item["scope"], sort_keys=True),
    )
    # Version/provenance identifiers differ between local and distributed runs.
    states = [{"scope": item["scope"], "state": item["state"]} for item in snapshots]
    return {"answers": rows, "states": states}


def check_case(name, results):
    assert not results.has_unfixed_exceptions, "Result contains unresolved exceptions"
    rows = [r.answer for r in results]
    states = outcomes(results)["states"]
    if name == "activity_poll":
        counts = Counter(row["activity"] for row in rows)
        assert sorted(counts.values()) == [2, 2, 2, 2]
        return dict(counts)
    if name == "ultimatum":
        assert len(states) == 2
        assert all(
            s["state"]["game"]["offer"] == 40
            and s["state"]["game"]["decision"] == "accept"
            for s in states
        )
        return {"pairs": 2, "offer": 40, "decisions": "accept"}
    if name == "survey_quota":
        counts = Counter(
            r["respondent_type"] for r in rows if r.get("quota_gate") == "admitted"
        )
        assert dict(counts) == {"A": 10, "B": 10}
        return {
            "admitted": dict(counts),
            "screened_out": len(rows) - sum(counts.values()),
        }
    if name == "posted_price_market":
        state = states[0]["state"]["market"]
        assert state["stock"] == 0 and state["seller_cash"] == 140
        assert sum(state["cash"].values()) + state["seller_cash"] == 800
        return {"stock": 0, "seller_cash": 140}
    if name in ("second_price_auction", "uniform_price_auction"):
        book = states[0]["state"]["auction"]["auction"]
        price = 70 if name == "second_price_auction" else 65
        assert book["settled"] and book["price"] == price
        assert sum(book["cash"].values()) + book["seller_cash"] == 600
        return {"price": price, "allocations": book["allocations"]}
    if name == "appointment_booking":
        counts = Counter(row.get("booking_outcome") for row in rows)
        assert (
            counts["confirmed"] == 3 and counts["released"] == 1 and counts[None] == 1
        )
        return {"confirmed": 3, "released": 1, "unavailable": 1}
    counts = Counter(row["assigned_arm"] for row in rows)
    assert dict(counts) == {"Control": 6, "Treatment": 6}
    return dict(counts)


def check_live(name, results):
    assert not results.has_unfixed_exceptions
    states = outcomes(results)["states"]
    if name not in ("activity_poll", "ultimatum"):
        from examples.shared_state_acceptance_checks import check_application

        assert len(states) == 1, "Expected one shared study/market scope"
        return check_application(name, results, states[0]["state"])
    if name == "activity_poll":
        from examples.shared_state_activity_poll import ACTIVITIES

        assert len(results) == 8
        votes = {row.agent.name: row.answer["activity"] for row in results}
        assert all(vote in ACTIVITIES for vote in votes.values())
        assert states[0]["state"]["poll"]["votes"] == votes
        return {"votes": votes, "counts": dict(Counter(votes.values()))}
    assert name == "ultimatum" and len(results) == 4 and len(states) == 2
    pairs = {}
    for row in results:
        pair = pairs.setdefault(row.agent.traits["pair_id"], {})
        pair.update({k: v for k, v in row.answer.items() if v is not None})
    for entry in states:
        state = entry["state"]["game"]
        pair = pairs[entry["scope"]]
        assert 0 <= state["offer"] <= 100
        assert state["offer"] == pair["offer"]
        assert state["decision"] == pair["decision"]
        assert state["decision"] in ("accept", "reject")
    return pairs


def run_remote(job, base, directory, timeout, *, mock_llm=True):
    import os
    import requests

    headers = (
        {"X-API-Key": os.environ["COOPR_RUNNER_TEST_KEY"]}
        if os.environ.get("COOPR_RUNNER_TEST_KEY")
        else {}
    )
    response = requests.post(
        base.rstrip("/") + "/jobs",
        json={"job": serialize_job(job), "mock_llm": mock_llm},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    submission = response.json()
    (directory / "submission.json").write_text(json.dumps(submission, indent=2) + "\n")
    jid = submission["job_id"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = requests.get(
            f"{base.rstrip('/')}/jobs/{jid}", headers=headers, timeout=10
        )
        response.raise_for_status()
        status = response.json()
        if status["status"] in {
            "completed",
            "completed_with_failures",
            "failed",
            "cancelled",
        }:
            (directory / "status.json").write_text(json.dumps(status, indent=2) + "\n")
            if status["status"] != "completed":
                errors = requests.get(
                    f"{base.rstrip('/')}/jobs/{jid}/errors", headers=headers, timeout=10
                )
                errors.raise_for_status()
                (directory / "errors.json").write_text(
                    json.dumps(errors.json(), indent=2) + "\n"
                )
                raise RuntimeError(f"Runner job {jid} ended as {status['status']}")
            break
        time.sleep(0.5)
    else:
        raise TimeoutError(
            f"Runner job {jid} remains active; inspect its saved submission"
        )
    response = requests.get(
        f"{base.rstrip('/')}/jobs/{jid}/results", headers=headers, timeout=30
    )
    response.raise_for_status()
    payload = response.json()
    (directory / "runner-response.json").write_text(
        json.dumps(payload, indent=2) + "\n"
    )
    return jid, deserialize_results(payload["results"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner-url", default="http://localhost:8001")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--case", action="append", choices=CASES)
    selection.add_argument("--all", action="store_true", help="Run all eight examples")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Make paid model calls; defaults to activity_poll and ultimatum",
    )
    parser.add_argument("--model", help="Required with --live")
    parser.add_argument("--service", default="openai")
    args = parser.parse_args()
    cases = (
        CASES
        if args.all
        else args.case or (("activity_poll", "ultimatum") if args.live else CASES)
    )
    if args.live and not args.model:
        parser.error("--live requires --model")
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for name in cases:
        directory = args.output / name
        directory.mkdir()
        record = {"case": name, "status": "failed"}
        try:
            with redirect_stdout(sys.stderr):
                live, scripted, schedule = build_case(name)
                if args.live:
                    parameters = (
                        {"maxOutputTokens": 256, "thinking_budget": 0}
                        if args.service == "google"
                        else {"max_tokens": 256}
                    )
                    if args.service == "google" and args.model.startswith("gemini-3"):
                        # Gemini 3.8 rejects the older sampling controls and
                        # thinking budget. Its output cap includes reasoning.
                        parameters = {
                            "maxOutputTokens": 1024,
                            "thinking_budget": None,
                            "temperature": None,
                            "topP": None,
                            "topK": None,
                        }
                    live.models = ModelList(
                        [Model(args.model, service_name=args.service, **parameters)]
                    )
                    live.save(str(directory / "live.jobs.ep"))
                    jid, remote = run_remote(
                        live, args.runner_url, directory, args.timeout, mock_llm=False
                    )
                    record["job_id"] = jid
                    remote.save(str(directory / "coopr.results.ep"))
                    record["actual"] = check_live(name, remote)
                    record.update(model=args.model, mode="live")
                else:
                    live.save(str(directory / "live.jobs.ep"))
                    scripted.save(str(directory / "scripted.jobs.ep"))
                    local = (
                        Runner(interview_schedule=schedule)
                        .submit(scripted, cache=False)
                        .results()
                    )
                    local.save(str(directory / "local.results.ep"))
                    record["expected"] = check_case(name, local)
                    jid, remote = run_remote(
                        scripted, args.runner_url, directory, args.timeout
                    )
                    record["job_id"] = jid
                    remote.save(str(directory / "coopr.results.ep"))
                    record["actual"] = check_case(name, remote)
                    assert outcomes(local) == outcomes(
                        remote
                    ), "Local and coopr answers/final state differ"
                record.update(status="passed", rows=len(remote))
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
        print(json.dumps(record), file=sys.stderr, flush=True)
        (args.output / "summary.json").write_text(json.dumps(records, indent=2) + "\n")
    lines = [
        "# Shared-state example acceptance",
        "",
        (
            f"Live model: {args.service}/{args.model}; local coopr/PostgreSQL. Paid model calls; semantic invariants checked."
            if args.live
            else "Scripted inputs; local SQLite versus local coopr/PostgreSQL. No model calls."
        ),
        "",
        "| Example | Result | Rows | Outcome/error |",
        "| --- | --- | ---: | --- |",
    ]
    for r in records:
        detail = r.get("actual", r.get("error"))
        lines.append(
            f"| {r['case']} | {r['status']} | {r.get('rows', '')} | {json.dumps(detail)} |"
        )
    lines += [
        "",
        "This checks the runner HTTP path. Hosted submission, billing, and cloud uploads remain separate acceptance steps.",
        "",
        (
            "Each case includes the live Jobs package, diagnostic artifacts, and coopr Results where execution succeeded."
            if args.live
            else "Each case includes scripted and live-question Jobs packages, local/coopr Results packages where execution succeeded, and the runner submission ID."
        ),
    ]
    (args.output / "report.md").write_text("\n".join(lines) + "\n")
    failed = sum(r["status"] != "passed" for r in records)
    print(
        json.dumps(
            {
                "status": "error" if failed else "ok",
                "passed": len(records) - failed,
                "failed": failed,
                "report": str(args.output / "report.md"),
            }
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
