"""Audit and visualize an intentionally paused market without imputing redemption."""

import base64
from collections import Counter
import html
import json
import os
import sqlite3

from jinja2 import Template, StrictUndefined
from edsl import Results

from .experiment import ROOT, cents
from .full_report import table, write_csv
from .paper_followup_report import excursion_diagnostics
from .run_gpt5_pilot import source_hashes
from .speculative_prompts import COMMON, PERSONAS, question_text


def audit_prefix(path):
    s = json.loads((path / "summary.json").read_text())
    orders = json.loads((path / "orders.json").read_text())
    n = s["observed_periods"]
    assert s["observation_complete"] and not s["complete"]
    assert s["config"]["periods"] == 30 and 1 <= n < 30
    assert s["config"]["source_sha256"] == source_hashes()
    assert len(s["tape"]) == n and len(orders) == 12 * n
    assert len({(o["trader"], o["period"]) for o in orders}) == 12 * n
    assert s["work_items"]["completed"] == 13 * n
    assert sum(a["shares"] for a in s["accounts"].values()) == 48
    opening_views, histories, rows = {}, {}, []
    for name, account in s["accounts"].items():
        cash, shares = 10000, 4
        assert "redeemed_shares" not in account
        assert len(account["history"]) == n
        for t, h in enumerate(account["history"], 1):
            opening_views[name, t] = {
                "cash_cents": cash,
                "shares": shares,
                "history": account["history"][: t - 1],
            }
            assert h["trader"] == name and h["period"] == t
            assert abs(h["fill"]) <= h["accepted_quantity"]
            if h["side"] == "buy" and h["accepted_quantity"]:
                assert h["accepted_quantity"] <= min(48, cash // h["limit_cents"])
            if h["side"] == "sell":
                assert h["accepted_quantity"] <= shares
            if h["fill"]:
                price = cents(h["transaction_price"])
                assert (
                    h["side"] == "buy" and h["fill"] > 0 and price <= h["limit_cents"]
                ) or (
                    h["side"] == "sell" and h["fill"] < 0 and price >= h["limit_cents"]
                )
                cash -= h["fill"] * price
                shares += h["fill"]
            assert cash >= 0 and shares >= 0
            interest = (cash * 5 + 50) // 100
            assert interest == cents(h["interest"])
            cash += interest + cents(h["dividend_per_share"]) * shares
            histories.setdefault(t, []).append(h)
            rows.append(
                {
                    "period": t,
                    "trader": name,
                    "persona": s["persona_assignment"][name],
                    **h["decision"],
                    "admitted_quantity": h["accepted_quantity"],
                    "signed_fill": h["fill"],
                    "execution_price": h["transaction_price"] if h["fill"] else None,
                    "closing_cash": cash / 100,
                    "closing_shares": shares,
                }
            )
        assert account["cash_cents"] == cash and account["shares"] == shares
    cash_total = 120000
    for row in s["tape"]:
        hs = histories[row["period"]]
        assert sum(h["fill"] for h in hs) == 0
        assert sum(max(0, h["fill"]) for h in hs) == row["volume"]
        assert all(
            h["transaction_price"] == row["price"]
            and h["dividend_per_share"] == row["dividend"]
            for h in hs
        )
        assert row["total_shares"] == 48
        cash_total += cents(row["total_interest"]) + 48 * cents(row["dividend"])
        assert cents(row["total_cash"]) == cash_total
    assert sum(a["cash_cents"] for a in s["accounts"].values()) == cash_total
    with sqlite3.connect(f"file:{path / 'workflow.sqlite'}?mode=ro", uri=True) as c:
        owners = dict(c.execute("SELECT id,participant_id FROM workflow_items"))
        attempts = dict(
            c.execute("SELECT status,count(*) FROM workflow_attempts GROUP BY status")
        )
    with sqlite3.connect(f"file:{path / 'shared-state.sqlite'}?mode=ro", uri=True) as c:
        reads = [
            json.loads(p)
            for (p,) in c.execute("SELECT payload FROM state_events WHERE kind='read'")
        ]
        commands = Counter(
            json.loads(p)["command"]
            for (p,) in c.execute("SELECT payload FROM state_events WHERE kind='write'")
        )
    assert commands == {"submit": 12 * n, "settle": n}
    assert len(reads) == 12 * n
    for r in reads:
        view = r["value"]
        assert set(view) == {"finished", "last_price", "period", "tape", "your_account"}
        assert view["tape"] == s["tape"][: view["period"] - 1]
        assert (
            view["your_account"]
            == opening_views[owners[r["execution_id"]], view["period"]]
        )
    calls = []
    if s["config"]["backend"] == "llm":
        calls = [
            json.loads(line)
            for line in (path / "model-calls.jsonl").read_text().splitlines()
        ]
        assert len({c["work_item_id"] for c in calls}) == 12 * n
        views = {r["execution_id"]: r["value"] for r in reads}
        for call in calls:
            view = views[call["work_item_id"]]
            prompt = call["result"]["prompt"]
            rendered = (
                Template(question_text(view["period"], 30), undefined=StrictUndefined)
                .render(shared_state={"market": view})
                .strip()
            )
            assert prompt["decision_user_prompt"]["text"].startswith(rendered)
            assert (
                COMMON + PERSONAS[s["persona_assignment"][call["participant"]]]
                in prompt["decision_system_prompt"]["text"]
            )
            assert call["result"]["model"]["model"] == "gpt-5-mini"
            assert (
                call["result"]["raw_model_response"]["decision_raw_model_response"][
                    "choices"
                ][0]["finish_reason"]
                == "stop"
            )
        assert len(Results.load(str(path / "results.ep"))) == 12 * n
    audit = {
        "checks_passed": True,
        "observed_periods": n,
        "economic_horizon": 30,
        "accepted_decisions": 12 * n,
        "model_calls": len(calls),
        "commands": dict(commands),
        "attempt_status": attempts,
        "no_early_redemption": True,
        "all_private_views_and_prompts_verified": True,
    }
    return s, sorted(rows, key=lambda r: (r["period"], r["trader"])), calls, audit


def build(path=ROOT / "runs" / "gpt5-short-pilot", output=ROOT / "gpt5-pilot-report"):
    s, rows, calls, audit = audit_prefix(path)
    output.mkdir(exist_ok=True)
    d = excursion_diagnostics(s["tape"])
    cost = sum(
        c["result"]["raw_model_response"].get("decision_cost", 0) or 0 for c in calls
    )
    summary = {
        "audit": audit,
        "diagnostics": d,
        "metrics": s["metrics"],
        "stop_reason": s["stop_reason"],
        "recorded_cost": cost,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "data.json").write_text(
        json.dumps({"session": s, "decisions": rows}, indent=2) + "\n"
    )
    write_csv(output / "decisions.csv", rows)
    write_csv(output / "periods.csv", s["tape"])
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-market-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap

    fig, axes = plt.subplots(4, 1, figsize=(10, 12), layout="constrained")
    periods = [r["period"] for r in s["tape"]]
    prices = [r["price"] if r["price"] is not None else np.nan for r in s["tape"]]
    axes[0].plot(
        periods, prices, "o-", color="#087e8b", label="Actual transaction price"
    )
    axes[0].axhline(14, ls="--", color="#687982", label="Fundamental $14")
    axes[0].axhline(17.5, ls=":", color="#ce6c2b", label="Excursion $17.50")
    axes[0].set(
        title=f"GPT-5 mini · first {len(periods)} rounds of a 30-round market",
        ylabel="Transaction price ($)",
        ylim=(0, max(20, (d["peak_price"] or 14) * 1.1)),
    )
    axes[0].legend()
    axes[1].bar(periods, [r["volume"] for r in s["tape"]], color="#087e8b")
    axes[1].set(ylabel="Shares traded")
    for side, color, aggregator, label in [
        ("buy", "#087e8b", max, "Highest active bid"),
        ("sell", "#ce6c2b", min, "Lowest active ask"),
    ]:
        quotes = [
            aggregator(
                [
                    r["price"]
                    for r in rows
                    if r["period"] == t
                    and r["side"] == side
                    and r["admitted_quantity"] > 0
                ],
                default=np.nan,
            )
            for t in periods
        ]
        axes[2].plot(periods, quotes, "o--", color=color, label=label)
    axes[2].axhline(14, ls="--", color="#687982")
    axes[2].set(ylabel="Submitted quotes ($)")
    axes[2].legend()
    for key, color in [
        ("forecast_0", "#087e8b"),
        ("forecast_2", "#ce6c2b"),
        ("forecast_5", "#7155a6"),
    ]:
        axes[3].plot(
            periods,
            [sum(r[key] for r in rows if r["period"] == t) / 12 for t in periods],
            label=key,
            color=color,
        )
    axes[3].axhline(14, ls="--", color="#687982")
    axes[3].set(ylabel="Mean forecast ($)", xlabel="Observed round")
    axes[3].legend()
    for ax in axes:
        ax.set_xlim(0.5, max(periods) + 0.5)
        ax.grid(alpha=0.15)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xticks(periods)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / f"market.{ext}", dpi=160, bbox_inches="tight")
    plt.close(fig)
    fig, ax = plt.subplots(
        figsize=(max(8, len(periods) * 0.65), 5), layout="constrained"
    )
    names = sorted(
        s["accounts"], key=lambda name: (s["persona_assignment"][name], name)
    )
    cells = np.zeros((12, len(periods)))
    for r in rows:
        cells[names.index(r["trader"]), r["period"] - 1] = {
            "hold": 0,
            "buy": 1,
            "sell": 2,
        }[r["side"]]
    ax.imshow(
        cells,
        aspect="auto",
        cmap=ListedColormap(["#e0e5e8", "#087e8b", "#ce6c2b"]),
        vmin=0,
        vmax=2,
    )
    for r in rows:
        if r["signed_fill"]:
            ax.text(
                r["period"] - 1,
                names.index(r["trader"]),
                str(abs(r["signed_fill"])),
                ha="center",
                va="center",
                color="white",
                bbox={"facecolor": "#172e3a", "edgecolor": "none", "pad": 1},
            )
    ax.set_yticks(
        range(12), [f"{name[-2:]} · {s['persona_assignment'][name]}" for name in names]
    )
    ax.set_xticks(range(len(periods)), periods)
    ax.set(
        title="Buy (teal), sell (orange), hold (gray); numbers show filled shares",
        xlabel="Round",
    )
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / f"decisions.{ext}", dpi=160, bbox_inches="tight")
    plt.close(fig)

    def picture(name):
        return (
            "data:image/png;base64,"
            + base64.b64encode((output / f"{name}.png").read_bytes()).decode()
        )

    findings = table(
        ["Round", "Price", "Shares traded", "Dividend"],
        [
            [
                r["period"],
                "No trade" if r["price"] is None else f"${r['price']:.2f}",
                r["volume"],
                r["dividend"],
            ]
            for r in s["tape"]
        ],
    )
    ledger = table(
        [
            "Round",
            "Trader",
            "Type",
            "Side",
            "Limit",
            "Requested",
            "Admitted",
            "Fill",
            "Rationale",
        ],
        [
            [
                r["period"],
                r["trader"],
                r["persona"],
                r["side"],
                r["price"],
                r["quantity"],
                r["admitted_quantity"],
                r["signed_fill"],
                r["rationale"],
            ]
            for r in rows
        ],
    )
    headline = (
        "The early price threshold was reached."
        if d["sustained_excursion"]
        else "No sustained price excursion in the observed rounds."
    )
    css = (ROOT / "report_assets" / "full_report.css").read_text()
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GPT-5 mini short market pilot</title><style>{css}</style><main><section class="hero"><p class="eyebrow">Genuine LLM trades · saved shared-state workflow</p><h1>{headline}</h1><p class="dek">Observed {len(periods)} rounds; the contractual horizon remains 30. The market is paused with live holdings and no early redemption.</p><div class="metrics"><div><strong>{len(rows)}</strong><span>accepted trader decisions</span></div><div><strong>{s["metrics"]["volume"]}</strong><span>shares traded</span></div><div><strong>{"—" if d["peak_price"] is None else "$" + format(d["peak_price"], ".2f")}</strong><span>peak transaction price</span></div><div><strong>${cost:.2f}</strong><span>recorded model cost</span></div></div></section><section><h2>Observed prices, volume, and expectations</h2><img alt="Market prices, traded volume, and mean forecasts" src="{picture("market")}">{findings}<p>Only actual trades establish market prices; gaps indicate no trade. Forecasts are expectations, not transaction evidence. $14 is fundamental value; $17.50 marks the prior 25% excursion threshold. Stop reason: <code>{html.escape(s["stop_reason"])}</code>. A brief early observation cannot establish a later peak or crash.</p></section><section><h2>Every trading decision</h2><img alt="All trader decisions and filled quantities" src="{picture("decisions")}"><details><summary>Full order ledger and rationales</summary>{ledger}</details></section><section><h2>Design and validation</h2><p>One market, seed 140926, unchanged speculative-v1 prompts and six archetypes (two each). GPT-5 mini uses medium reasoning and an 8000-token completion allowance. All 12 sealed decisions are opened before querying traders concurrently; settlement waits for all submissions. The initial observation limit was 12 rounds. After seeing no trades by round 6 and a selling schedule starting at round 16, we specified an extension to round 20 if there were still zero trades at round 12. The requested limit for this checkpoint is {s["observation_limit"]} rounds, with early stopping after two consecutive transaction prices at or above $17.50. The extension is outcome-dependent and exploratory. This is an exploratory demonstration, not an estimate of bubble frequency.</p><p>The independent prefix audit passed accounting, inventory and budget constraints, private-state visibility, exact prompt rendering, completion status, and {len(periods)} once-only settlements. Shares remain live. The checkpoint can resume without regenerating completed rounds.</p><p><a href="../GPT5_SHORT_PILOT.md">Design</a> · <a href="market.pdf">Market figure PDF</a> · <a href="decisions.csv">All orders and forecasts</a> · <a href="periods.csv">Period data</a> · <a href="data.json">Complete observed state</a> · <a href="summary.json">Metrics and audit</a></p></section></main></html>'''
    (output / "index.html").write_text(page)
    print(
        json.dumps(
            {
                "status": "ok",
                "data": {"report": str(output / "index.html"), **summary},
                "warnings": [],
            }
        )
    )


if __name__ == "__main__":
    build()
