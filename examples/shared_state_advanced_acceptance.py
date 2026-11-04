"""Small live coopr examples for adaptive questions, rounds, and atomic claims.

Run with --live --output NEW_DIRECTORY. Saves every prompt, answer, and state read.
Uses the existing local coopr worker's OpenAI credentials; no keys are stored here.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import redirect_stdout
from importlib import import_module
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

from edsl import Agent, AgentList, InterviewSchedule, Model
from edsl.runner.serialization import deserialize_results
from examples.shared_state_acceptance import run_remote

CASES = (
    "pairwise_comparisons",
    "price_elicitation",
    "team_formation",
    "message_board",
    "repeated_matrix",
    "work_pool",
)


def build_case(name, model):
    if name in ("message_board", "repeated_matrix", "work_pool"):
        from examples.shared_state_gemini_game_smoke import GAMES

        survey, agents, schedule = GAMES[name]()
        if name == "message_board":
            schedule = InterviewSchedule.rounds(
                count=2,
                group_by="board_id",
                within_round="serial",
                state_visibility="live",
                order_by="turn",
            )
    else:
        module = import_module(f"examples.{name}")
        options = (
            {"budget": 6, "explore_every": 2, "items": module.DEFAULT_ITEMS[:3]}
            if name == "pairwise_comparisons"
            else {}
        )
        survey, _, schedule = module.build_survey(
            state_id=f"live-{name}-{uuid4()}", **options
        )
        people = (
            module.demo_agents(count=8)
            if name == "pairwise_comparisons"
            else module.demo_agents()
        )
        agents = AgentList(
            [
                Agent(
                    name=a.name,
                    traits=dict(a.traits),
                    instruction=a.instruction,
                    traits_presentation_template=a.traits_presentation_template,
                )
                for a in people
            ]
        )
    job = survey.by(agents).by(model)
    job.run_config.parameters.interview_schedule = schedule
    return job


def binding(results):
    assert len(results.shared_state["bindings"]) == 1
    return results.shared_state["bindings"][0]


def view_at_question(results, row, question):
    """Resolve the exact historical read captured with the question presentation."""
    metadata = row.data["question_to_attributes"][question]["presentation"]
    assert metadata["source"] == "prompt"
    refs = metadata["shared_state_reads"]
    assert len(refs) == 1
    events = {
        e["read_id"]: e for e in binding(results)["events"] if e["kind"] == "read"
    }
    event = events[refs[0]["read_id"]]
    assert event["version"] == refs[0]["version"]
    return event["value"]


def prompt(row, question):
    return row.data["prompt"][f"{question}_user_prompt"].text


def check_case(name, results):
    assert not results.has_unfixed_exceptions, "Unresolved interview exceptions"
    expected = {
        "pairwise_comparisons": 8,
        "price_elicitation": 4,
        "team_formation": 8,
        "message_board": 6,
        "repeated_matrix": 6,
        "work_pool": 2,
    }
    assert len(results) == expected[name], "Missing or extra result rows"
    snapshots = binding(results)["exit_snapshots"]
    if name == "price_elicitation":
        return check_prices(results, snapshots)
    assert len(snapshots) == 1
    state = snapshots[0]["state"]
    if name == "pairwise_comparisons":
        state = state["comparisons"]
        assert state["comparisons"] == len(state["responses"]) == 6
        assert sum(state["pair_counts"].values()) == 6
        assert abs(sum(state["ratings"].values())) < 1e-9
        counts = Counter()
        for row in results:
            rid, answer = row.agent.traits["respondent_id"], row.answer.get(
                "preference"
            )
            assert answer == state["responses"].get(rid)
            if answer is None:
                continue
            assignment = state["assignments"][rid]
            options = row.get_question_options("preference")
            assert (
                options
                == assignment["options"]
                == view_at_question(results, row, "preference")["options"]
            )
            assert len(options) == 2 and answer in options
            counts[assignment["pair_id"]] += 1
        assert {k: v for k, v in state["pair_counts"].items() if v} == dict(counts)
        modes = Counter(a["mode"] for a in state["assignments"].values())
        assert modes["explore"] > 0 and modes["adaptive"] > 0
        return {
            "comparisons": 6,
            "stopped": 2,
            "assignment_modes": dict(modes),
            "ratings": state["ratings"],
        }
    if name == "team_formation":
        return check_teams(results, state["teams"])
    state = state["game"]
    if name == "message_board":
        messages = []
        for row in sorted(
            results, key=lambda r: (r.data["iteration"], r.agent.traits["turn"])
        ):
            view = view_at_question(results, row, "message")
            assert view["messages"] == messages
            shown = ast.literal_eval(
                re.search(
                    r"Existing messages: (\[.*\])\.", prompt(row, "message"), re.S
                )[1]
            )
            assert shown == messages
            messages.append(
                {
                    "author": row.agent.name,
                    "message": row.answer["message"].strip(),
                    "reply_to": None,
                }
            )
        assert [
            {k: e[k] for k in ("author", "message", "reply_to")}
            for e in state["messages"]
        ] == messages
        return {
            "rounds": 2,
            "messages": len(messages),
            "last_message": messages[-1]["message"],
        }
    if name == "repeated_matrix":
        rounds = {}
        for iteration in range(3):
            current = [row for row in results if row.data["iteration"] == iteration]
            assert len(current) == 2
            for row in current:
                view = view_at_question(results, row, "action")
                assert (
                    view["rounds"] == rounds
                ), "Current-round action leaked into snapshot"
                shown = ast.literal_eval(
                    re.search(
                        r"Previous play: (.*?)\. Standard payoffs",
                        prompt(row, "action"),
                        re.S,
                    )[1]
                )
                assert shown == rounds
                assert row.answer["action"] in ("cooperate", "defect")
            rounds[str(iteration + 1)] = {
                r.agent.traits["seat"]: r.answer["action"] for r in current
            }
        assert state["rounds"] == rounds and state["players"] == {
            "0": "Row",
            "1": "Column",
        }
        return {"rounds": rounds, "snapshot_visibility": "verified"}
    assert name == "work_pool"
    assert state["available"] == []
    assert {c["id"] for c in state["claims"].values()} == {"W1", "W2"}
    assert (
        set(state["claims"])
        == set(state["completed"])
        == {r.agent.name for r in results}
    )
    for row in results:
        claim = state["claims"][row.agent.name]
        assert view_at_question(results, row, "result")["my_claim"] == claim
        shown = ast.literal_eval(
            re.search(r"assignment is (\{.*?\})\.", prompt(row, "result"), re.S)[1]
        )
        assert shown == claim
        assert state["completed"][row.agent.name] == {
            "item": claim,
            "result": {"note": row.answer["result"]},
        }
    return {"claims": state["claims"], "completed": len(state["completed"])}


def check_prices(results, snapshots):
    states = {s["scope"][1]: s["state"]["pricing"] for s in snapshots}
    assert len(states) == 4
    report = []
    for row in results:
        low, high, history = 0, 100, []
        for i in range(7):
            answer, price = row.answer.get(f"buy_{i}"), row.answer[f"price_{i}"]
            if low == high:
                assert price == "skip" and answer is None
                continue
            assert price == (low + high + 1) // 2 and answer in ("Yes", "No")
            view = view_at_question(results, row, f"buy_{i}")
            assert (
                view["lower"] == low
                and view["upper"] == high
                and view["price"] == price
            )
            assert f"for {price} price units" in prompt(row, f"buy_{i}")
            history.append({"step": i, "price": price, "answer": answer})
            if answer == "Yes":
                low = price
            else:
                high = price - 1
        state = states[row.agent.traits["respondent_id"]]
        assert state["lower"] == low == high == state["upper"]
        assert state["history"] == history
        assert row.answer["price_interval"] == f"{low}..{high}"
        report.append(
            {
                "respondent": row.agent.traits["respondent_id"],
                "stated_value": row.agent.traits["value"],
                "elicited_value": low,
                "questions": len(history),
            }
        )
    return report


def check_teams(results, state):
    teams, seats = ("Orion", "Lyra"), {"Designer": 1, "Builder": 2}
    members, profiles = {}, {}
    for row in sorted(results, key=lambda r: r.agent.traits["turn"]):
        a, rid = row.answer, row.agent.traits["respondent_id"]
        if len(members) == 6:
            assert a["team_enrollment"] == "closed" and a.get("role") is None
            continue
        role = a["role"]
        assert a["team_enrollment"] == "open" and role in seats
        profiles[rid] = role
        options = [
            t
            for t in teams
            if sum(m == {"team": t, "role": role} for m in members.values())
            < seats[role]
        ]
        if not options:
            assert (
                a["team_availability"] == "closed"
                and a.get("team") is None
                and a.get("introduction") is None
            )
            continue
        assert a["team_availability"] == "open"
        assert (
            row.get_question_options("team")
            == options
            == view_at_question(results, row, "team")["options"]
        )
        assert a["team"] in options and a["joined_team"] == a["team"]
        assert isinstance(a["introduction"], str) and a["introduction"].strip()
        members[rid] = {"team": a["team"], "role": role}
    assert state["members"] == members and state["profiles"] == profiles
    return {
        "assigned": len(members),
        "not_assigned": len(results) - len(members),
        "teams": {
            t: dict(Counter(m["role"] for m in members.values() if m["team"] == t))
            for t in teams
        },
    }


def save_transcript(results, directory):
    lines = ["# Prompts, answers, and historical state", ""]
    for row in results:
        identity = row.agent.name or row.agent.traits.get(
            "respondent_id", "participant"
        )
        for name, answer in row.answer.items():
            key = f"{name}_user_prompt"
            if answer is None or key not in row.data["prompt"]:
                continue
            lines += [
                f"## {identity}, round {row.data['iteration'] + 1}: {name}",
                "",
                "```text",
                prompt(row, name),
                "```",
                "",
                "Answer: " + json.dumps(answer),
                "",
                row.data["comments_dict"].get(f"{name}_comment") or "",
                "",
            ]
    (directory / "transcript.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Enable paid model calls")
    mode.add_argument(
        "--verify",
        action="store_true",
        help="Check saved responses without model calls",
    )
    parser.add_argument("--case", action="append", choices=CASES)
    parser.add_argument(
        "--model", default="gpt-4o-mini", help="OpenAI model used by the local worker"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runner-url", default="http://localhost:8001")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    if args.verify:
        if not args.output.is_dir():
            parser.error("--verify requires an existing output directory")
    else:
        args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for name in args.case or CASES:
        directory = args.output / name
        if not args.verify:
            directory.mkdir()
        record = {"case": name, "status": "failed"}
        try:
            with redirect_stdout(sys.stderr):
                if args.verify:
                    payload = json.loads(
                        (directory / "runner-response.json").read_text()
                    )
                    results = deserialize_results(payload["results"])
                    jid = json.loads((directory / "submission.json").read_text())[
                        "job_id"
                    ]
                else:
                    job = build_case(
                        name, Model(args.model, service_name="openai", max_tokens=256)
                    )
                    job.save(str(directory / "live.jobs.ep"))
                    jid, results = run_remote(
                        job, args.runner_url, directory, args.timeout, mock_llm=False
                    )
                    results.save(str(directory / "coopr.results.ep"))
                record["job_id"] = jid
                save_transcript(results, directory)
                record["actual"] = check_case(name, results)
                record.update(status="passed", rows=len(results))
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
        print(json.dumps(record), file=sys.stderr, flush=True)
        summary_name = "verification.json" if args.verify else "summary.json"
        (args.output / summary_name).write_text(json.dumps(records, indent=2) + "\n")
    lines = [
        "# Advanced live shared-state acceptance",
        "",
        (
            "Rechecked saved responses; no model calls."
            if args.verify
            else f"Model: openai/{args.model}. Local coopr worker and PostgreSQL."
        ),
        "",
        "| Example | Status | Rows | Outcome | Evidence |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for r in records:
        name = r["case"]
        lines.append(
            f"| {name} | {r['status']} | {r.get('rows', '')} | {json.dumps(r.get('actual', r.get('error')))} | [Transcript]({name}/transcript.md) |"
        )
    lines += [
        "",
        "Checks verify execution semantics, historical reads, and recorded choices. Model reasoning is retained for inspection, not scored for behavioral validity.",
        "",
    ]
    report_path = args.output / ("verification.md" if args.verify else "report.md")
    report_path.write_text("\n".join(lines))
    failed = sum(r["status"] != "passed" for r in records)
    print(
        json.dumps(
            {
                "status": "error" if failed else "ok",
                "passed": len(records) - failed,
                "failed": failed,
                "report": str(report_path),
            }
        )
    )
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
