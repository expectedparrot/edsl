"""Independently audit completed market artifacts without making model calls."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3

from .experiment import ROOT, cents


def audit_session(path: Path):
    summary = json.loads((path / "summary.json").read_text())
    config = summary["config"]
    periods = config["periods"]
    orders = json.loads((path / "orders.json").read_text())
    accounts = summary["accounts"]
    assert summary["complete"], "incomplete market"
    assert len(accounts) == 12
    assert summary["work_items"] == {"completed": periods * 13}
    assert len(orders) == periods * 12
    assert len({(o["trader"], o["period"]) for o in orders}) == periods * 12
    assert len(summary["tape"]) == periods
    assert sum(a["redeemed_shares"] for a in accounts.values()) == 48
    assert all(a["shares"] == 0 for a in accounts.values())
    code_files = [
        ROOT / "experiment.py",
        ROOT / "run.py",
        *sorted((ROOT / "personas").glob("*.txt")),
    ]
    code_hash = hashlib.sha256(b"".join(p.read_bytes() for p in code_files)).hexdigest()
    assert code_hash == config["implementation_sha256"], (
        "implementation changed since execution"
    )
    history_by_period = {t: [] for t in range(1, periods + 1)}
    expected_private_views = {}
    for name, account in accounts.items():
        cash, shares = 10000, 4
        assert len(account["history"]) == periods
        for t, history in enumerate(account["history"], start=1):
            expected_private_views[name, t] = {
                "cash_cents": cash,
                "shares": shares,
                "history": account["history"][: t - 1],
            }
            assert history["period"] == t and history["trader"] == name
            fill = history["fill"]
            assert abs(fill) <= history["accepted_quantity"]
            if fill:
                price = cents(history["transaction_price"])
                if fill > 0:
                    assert history["side"] == "buy"
                    assert price <= history["limit_cents"]
                else:
                    assert history["side"] == "sell"
                    assert price >= history["limit_cents"]
                cash -= fill * price
                shares += fill
            assert cash >= 0 and shares >= 0
            interest = (cash * 5 + 50) // 100
            assert interest == cents(history["interest"])
            cash += interest + shares * cents(history["dividend_per_share"])
            history_by_period[t].append(history)
        assert account["redeemed_shares"] == shares
        assert account["cash_cents"] == cash + shares * 1400
    previous_cash = 120000
    for period in summary["tape"]:
        histories = history_by_period[period["period"]]
        assert sum(h["fill"] for h in histories) == 0
        assert sum(max(h["fill"], 0) for h in histories) == period["volume"]
        assert all(h["transaction_price"] == period["price"] for h in histories)
        assert all(h["dividend_per_share"] == period["dividend"] for h in histories)
        assert period["total_shares"] == 48
        assert cents(period["total_cash"]) == previous_cash + cents(
            period["total_interest"]
        ) + 48 * cents(period["dividend"])
        previous_cash = cents(period["total_cash"])
    assert sum(a["cash_cents"] for a in accounts.values()) == previous_cash + 48 * 1400
    with sqlite3.connect(
        f"file:{path / 'workflow.sqlite'}?mode=ro", uri=True
    ) as connection:
        item_owners = dict(
            connection.execute(
                "SELECT id,participant_id FROM workflow_items"
            ).fetchall()
        )
        completed = connection.execute(
            "SELECT count(*) FROM workflow_items WHERE status='completed'"
        ).fetchone()[0]
        assert completed == periods * 13
        attempt_status = dict(
            connection.execute(
                "SELECT status,count(*) FROM workflow_attempts GROUP BY status"
            ).fetchall()
        )
    with sqlite3.connect(
        f"file:{path / 'shared-state.sqlite'}?mode=ro", uri=True
    ) as connection:
        writes = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT payload FROM state_events WHERE kind='write'"
            )
        ]
        commands = Counter(row["command"] for row in writes)
        assert commands == {"submit": periods * 12, "settle": periods}
        reads = [
            json.loads(row[0])
            for row in connection.execute(
                "SELECT payload FROM state_events WHERE kind='read'"
            )
        ]
        assert len(reads) == periods * 12
        for read in reads:
            value = read["value"]
            assert set(value) == {
                "finished",
                "last_price",
                "period",
                "tape",
                "your_account",
            }
            assert value["tape"] == summary["tape"][: value["period"] - 1]
            name = item_owners[read["execution_id"]]
            assert (
                value["your_account"] == expected_private_views[name, value["period"]]
            )
    model_calls = 0
    if config["backend"] == "llm":
        from edsl import AgentList, Results

        agents = {a.name: a for a in AgentList.load(str(path / "traders.ep"))}
        calls = [
            json.loads(line)
            for line in (path / "model-calls.jsonl").read_text().splitlines()
        ]
        model_calls = len(calls)
        assert len({call["work_item_id"] for call in calls}) == periods * 12
        for call in calls:
            system = call["result"]["prompt"]["decision_system_prompt"]["text"]
            assert agents[call["participant"]].instruction in system, (
                "persona missing from actual system prompt"
            )
            assert (
                "{{ shared_state"
                not in call["result"]["prompt"]["decision_user_prompt"]["text"]
            )
        assert len(Results.load(str(path / "results.ep"))) == periods * 12
    return {
        "session": path.name,
        "checks_passed": True,
        "periods": periods,
        "accepted_decisions": periods * 12,
        "model_calls": model_calls,
        "state_commands": dict(commands),
        "attempt_status": attempt_status,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    paths = sorted(args.runs.glob("*/summary.json"))
    if not paths:
        parser.error("no completed session summaries found")
    result = {
        "status": "ok",
        "data": [audit_session(p.parent) for p in paths],
        "warnings": [],
    }
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")
