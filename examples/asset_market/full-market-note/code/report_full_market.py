"""Audit and visualize a completed native market using saved artifacts only."""

import argparse
from collections import Counter
import csv
from decimal import Decimal, ROUND_HALF_UP
import html
import json
import os
from pathlib import Path
import sqlite3

from jinja2 import Template, StrictUndefined


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build(path):
    state = json.loads((path / "market.json").read_text())
    spec = json.loads((path / "experiment.json").read_text())
    completion = json.loads((path / "completion.json").read_text())
    calls = [
        json.loads(line)
        for line in (path / "model-calls.jsonl").read_text().splitlines()
    ]
    assert completion["status"] == "completed" and completion["completed_items"] == 390
    assert not spec["workflow"].get("pause_rules")
    assert state["finished"] and state["period"] == 31
    assert len(state["tape"]) == 30 and len(state["order_log"]) == 360
    assert len(calls) == len({c["work_item_id"] for c in calls}) == 360
    rows, opening = [], {}
    for name, account in sorted(state["accounts"].items()):
        cash, shares = 10000, 4
        assert len(account["history"]) == 30
        for period, h in enumerate(account["history"], 1):
            opening[name, period] = {
                "cash_cents": cash,
                "shares": shares,
                "history": account["history"][: period - 1],
            }
            assert h["period"] == period and h["trader"] == name
            assert abs(h["fill"]) <= h["accepted_quantity"]
            if h["side"] == "buy":
                if h["accepted_quantity"]:
                    assert h["accepted_quantity"] <= min(48, cash // h["limit_cents"])
                assert h["fill"] >= 0
            elif h["side"] == "sell":
                assert h["accepted_quantity"] <= shares and h["fill"] <= 0
            if h["fill"]:
                price = cents(h["transaction_price"])
                assert (
                    price <= h["limit_cents"]
                    if h["fill"] > 0
                    else price >= h["limit_cents"]
                )
                cash -= h["fill"] * price
                shares += h["fill"]
            assert cash >= 0 and shares >= 0
            assert cents(h["interest"]) == (cash * 5 + 50) // 100
            cash += cents(h["interest"]) + cents(h["dividend_per_share"]) * shares
            rows.append(
                {
                    "period": period,
                    "trader": name,
                    **h["decision"],
                    "accepted_quantity": h["accepted_quantity"],
                    "rejection": h["rejection"],
                    "signed_fill": h["fill"],
                    "transaction_price": h["transaction_price"],
                    "closing_cash_before_redemption": cash / 100,
                    "closing_shares_before_redemption": shares,
                }
            )
        assert shares == account["redeemed_shares"] and account["shares"] == 0
        assert account["cash_cents"] == cash + 1400 * shares
    total_cash = 120000
    for tape in state["tape"]:
        batch = [r for r in rows if r["period"] == tape["period"]]
        assert sum(r["signed_fill"] for r in batch) == 0
        assert sum(max(0, r["signed_fill"]) for r in batch) == tape["volume"]
        assert sum(r["closing_shares_before_redemption"] for r in batch) == 48
        assert tape["total_shares"] == 48
        total_cash += cents(tape["total_interest"]) + 48 * cents(tape["dividend"])
        assert total_cash == cents(tape["total_cash"])
        assert (
            sum(cents(r["closing_cash_before_redemption"]) for r in batch) == total_cash
        )
    assert (
        sum(a["cash_cents"] for a in state["accounts"].values())
        == total_cash + 48 * 1400
    )
    with sqlite3.connect(f"file:{path}/workflow.sqlite?mode=ro", uri=True) as db:
        owners = {
            r[0]: (r[1], r[2])
            for r in db.execute(
                "select id,participant_id,step_name from workflow_items"
            )
        }
        attempts = dict(
            db.execute("select status,count(*) from workflow_attempts group by status")
        )
    with sqlite3.connect(f"file:{path}/state-0.sqlite?mode=ro", uri=True) as db:
        reads = [
            json.loads(r[0])
            for r in db.execute("select payload from state_events where kind='read'")
        ]
        writes = Counter(
            json.loads(r[0])["command"]
            for r in db.execute("select payload from state_events where kind='write'")
        )
    assert writes == {"submit": 360, "settle": 30} and len(reads) == 360
    views = {r["execution_id"]: r["value"] for r in reads}
    questions = {
        s["name"]: s["survey"]["questions"][0]["question_text"]
        for s in spec["workflow"]["steps"]
    }
    agents = {a["name"]: a for a in spec["agents"]}
    responses = []
    for call in calls:
        trader, step = owners[call["work_item_id"]]
        view = views[call["work_item_id"]]
        assert set(view) == {"finished", "last_price", "period", "tape", "your_account"}
        assert view["your_account"] == opening[trader, view["period"]]
        assert view["tape"] == state["tape"][: view["period"] - 1]
        result = call["result"]
        rendered = (
            Template(questions[step], undefined=StrictUndefined)
            .render(shared_state={"market": view})
            .strip()
        )
        assert result["prompt"]["decision_user_prompt"]["text"].startswith(rendered)
        assert (
            agents[trader]["instruction"]
            in result["prompt"]["decision_system_prompt"]["text"]
        )
        assert (
            result["raw_model_response"]["decision_raw_model_response"]["choices"][0][
                "finish_reason"
            ]
            == "stop"
        )
        responses.append(
            {"step": step, "participant": trader, "answers": result["answer"]}
        )
    observed = [r for r in state["tape"] if r["price"] is not None]
    peak = max(observed, key=lambda r: r["price"]) if observed else None
    after = [r["price"] for r in observed if peak and r["period"] > peak["period"]]
    longest = streak = 0
    for row in state["tape"]:
        streak = streak + 1 if row["price"] is not None and row["price"] >= 17.5 else 0
        longest = max(longest, streak)
    summary = {
        "rounds": 30,
        "decisions": 360,
        "volume": sum(r["volume"] for r in observed),
        "trading_rounds": len(observed),
        "first_trade_round": observed[0]["period"] if observed else None,
        "peak_price": peak["price"] if peak else None,
        "peak_round": peak["period"] if peak else None,
        "last_transaction_price": observed[-1]["price"] if observed else None,
        "longest_consecutive_prices_at_least_17_50": longest,
        "post_peak_drawdown": (peak["price"] - min(after)) / peak["price"]
        if after
        else None,
        "recorded_model_cost": sum(
            c["result"]["raw_model_response"].get("decision_cost", 0) or 0
            for c in calls
        ),
        "audit": {
            "passed": True,
            "orders": dict(writes),
            "attempts": attempts,
            "all_private_views_and_prompts_verified": True,
            "shares_redeemed": 48,
        },
    }
    batch_file = path / "inference-batches.jsonl"
    if batch_file.exists():
        batches = [json.loads(line) for line in batch_file.read_text().splitlines()]
        completed_batches = [row for row in batches if row["event"] == "completed"]
        timings = [
            row["elapsed_seconds"]
            for row in completed_batches
            if row["interviews"] == 12
        ]
        summary["execution"] = {
            "initial_serial_decisions": 140,
            "batched_decisions": sum(row["results"] for row in completed_batches),
            "edsl_jobs_completed": len(completed_batches),
            "mean_full_round_job_seconds": sum(timings) / len(timings)
            if timings
            else None,
            "pairing": "zip_assign from PR #2622",
        }
    report = path / "report"
    report.mkdir(exist_ok=True)
    (report / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (path / "responses.json").write_text(json.dumps(responses, indent=2) + "\n")
    write_csv(
        report / "decisions.csv", sorted(rows, key=lambda r: (r["period"], r["trader"]))
    )
    write_csv(report / "periods.csv", state["tape"])
    write_csv(
        report / "terminal-wealth.csv",
        [
            {
                "trader": name,
                "cash": a["cash_cents"] / 100,
                "redeemed_shares": a["redeemed_shares"],
            }
            for name, a in sorted(state["accounts"].items())
        ],
    )
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-full-market-mpl")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap

    fig, axes = plt.subplots(
        3,
        1,
        figsize=(11, 10),
        layout="constrained",
        gridspec_kw={"height_ratios": [2, 1, 2]},
    )
    tape = state["tape"]
    periods = [r["period"] for r in tape]
    axes[0].plot(
        periods,
        [r["price"] if r["price"] is not None else np.nan for r in tape],
        "-o",
        color="#147e77",
        label="Transaction price",
    )
    for side, func, style in [("buy", max, "--"), ("sell", min, ":")]:
        prices = [
            func(
                (
                    r["price"]
                    for r in rows
                    if r["period"] == t
                    and r["side"] == side
                    and r["accepted_quantity"] > 0
                ),
                default=np.nan,
            )
            for t in periods
        ]
        axes[0].plot(
            periods,
            prices,
            style,
            alpha=0.7,
            label="Highest bid" if side == "buy" else "Lowest ask",
        )
    axes[0].axhline(14, color="gray", label="Fundamental value: $14")
    axes[0].axhline(17.5, color="gray", ls=":", label="25% overpricing: $17.50")
    axes[0].set(
        ylabel="Dollars per share", title="Fresh GPT-5 mini market: all 30 rounds"
    )
    axes[0].legend(ncol=2, fontsize=9)
    axes[1].bar(periods, [r["volume"] for r in tape], color="#147e77")
    axes[1].set(ylabel="Shares traded")
    names = sorted(state["accounts"])
    matrix = np.zeros((12, 30))
    for row in rows:
        matrix[names.index(row["trader"]), row["period"] - 1] = {
            "hold": 0,
            "buy": 1,
            "sell": 2,
        }[row["side"]]
    axes[2].imshow(
        matrix,
        cmap=ListedColormap(["#eceff2", "#d4e8f5", "#f3d6cf"]),
        vmin=0,
        vmax=2,
        aspect="auto",
        extent=[0.5, 30.5, 11.5, -0.5],
    )
    for row in rows:
        if row["signed_fill"]:
            axes[2].text(
                row["period"],
                names.index(row["trader"]),
                f"{row['signed_fill']:+d}",
                ha="center",
                va="center",
                fontsize=7,
            )
    axes[2].set(
        yticks=range(12),
        yticklabels=names,
        xlabel="Round",
        title="Every decision: blue = buy, red = sell, gray = hold; numbers = signed fills",
    )
    for ax in axes:
        ax.set_xlim(0.5, 30.5)
        ax.set_xticks(range(1, 31))
        ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(report / "market.png", dpi=160)
    fig.savefig(report / "market.pdf")
    plt.close(fig)
    ledger = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(r[k]))}</td>"
            for k in [
                "period",
                "trader",
                "side",
                "price",
                "quantity",
                "signed_fill",
                "rationale",
            ]
        )
        + "</tr>"
        for r in sorted(rows, key=lambda r: (r["period"], r["trader"]))
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Full 30-round asset market</title><style>body{{max-width:1100px;margin:40px auto;padding:0 20px;font:17px/1.5 system-ui;color:#243448}}img{{width:100%}}table{{border-collapse:collapse;font-size:13px}}td,th{{padding:8px;border-bottom:1px solid #ddd;vertical-align:top}}pre{{white-space:pre-wrap;background:#f4f6f8;padding:18px}}</style><h1>Full 30-round GPT-5 mini market</h1><p>A fresh session with the same speculative-v1 personas and seed 140926. All 360 decisions are new model responses. Observation ran to round 30, with no early pauses; all 48 shares were redeemed at $14 after final income.</p><img src="market.png" alt="Prices, volume, and all trader decisions"><p>Missing transaction prices mean no trade. Quotes are not transaction prices. This is one exploratory market; it does not establish a general bubble frequency.</p><p>The first 140 decisions ran sequentially. Execution then resumed from the same state using paired agent/scenario EDSL jobs from PR #2622. The remaining four decisions in round 12 formed one job, followed by one 12-interview job per round. The switch preserved all accepted answers and frozen prompt contents.</p><h2>Results and audit</h2><pre>{html.escape(json.dumps(summary, indent=2))}</pre><p><a href="market.pdf">Figure PDF</a> · <a href="decisions.csv">All decisions</a> · <a href="periods.csv">Round data</a> · <a href="terminal-wealth.csv">Final wealth</a></p><details><summary>All orders and rationales</summary><table><tr><th>Round</th><th>Trader</th><th>Side</th><th>Limit</th><th>Requested</th><th>Fill</th><th>Rationale</th></tr>{ledger}</table></details></html>"""
    (report / "index.html").write_text(page)
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    build(parser.parse_args().path)
