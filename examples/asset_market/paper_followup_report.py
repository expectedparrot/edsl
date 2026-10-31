"""Summarize the all-six paper-archetype follow-up, using observed trades only."""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import html
import json
import os
from pathlib import Path

from .audit import audit_session
from .experiment import ROOT, THEORY
from .full_report import reconstruct, table, write_csv


def excursion_diagnostics(tape):
    observed = [r for r in tape if r["price"] is not None]
    peak = max(observed, key=lambda r: r["price"]) if observed else None
    high = [r["period"] for r in observed if r["price"] >= 17.5]
    longest = current = 0
    for row in tape:
        current = (
            current + 1 if row["price"] is not None and row["price"] >= 17.5 else 0
        )
        longest = max(current, longest)
    after = [r for r in observed if peak and r["period"] > peak["period"]]
    drawdown = (
        (peak["price"] - min(r["price"] for r in after)) / peak["price"]
        if after
        else None
    )
    return {
        "peak_price": peak["price"] if peak else None,
        "peak_period": peak["period"] if peak else None,
        "periods_at_or_above_17_50": high,
        "longest_consecutive_high_periods": longest,
        "post_peak_drawdown": drawdown,
        "excursion": bool(high),
        "sustained_excursion": longest >= 2,
        "excursion_then_20pct_fall": bool(high)
        and drawdown is not None
        and drawdown >= 0.2,
    }


def build(runs, output):
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-market-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    import numpy as np

    paths = sorted(runs.glob("*/summary.json"))
    if not paths:
        raise ValueError("No completed sessions")
    audits = [audit_session(p.parent) for p in paths]
    sessions = [reconstruct(p.parent) for p in paths]
    if any(s["config"]["treatment"] != "RA+MC+BT+PC+NT+OC" for s in sessions):
        raise ValueError("This report is for the all-six paper-archetype condition")
    output.mkdir(parents=True, exist_ok=True)
    diagnostics = [
        {"seed": s["config"]["seed"], **excursion_diagnostics(s["tape"])}
        for s in sessions
    ]
    n = len(sessions)
    fig, axes = plt.subplots(
        3, n, figsize=(5 * n, 9), squeeze=False, layout="constrained"
    )
    observed = [
        r["price"] for s in sessions for r in s["tape"] if r["price"] is not None
    ]
    ceiling = max(20, 1.1 * max(observed, default=14))
    for column, s in enumerate(sessions):
        periods = [r["period"] for r in s["tape"]]
        ax = axes[0, column]
        ax.plot(
            periods,
            [r["price"] if r["price"] is not None else np.nan for r in s["tape"]],
            "o-",
            color="#087e8b",
        )
        ax.axhline(14, color="#687982", linestyle="--", label="Fundamental $14")
        ax.axhline(17.5, color="#ce6c2b", linestyle=":", label="Excursion $17.50")
        ax.set(
            title=f"All six · seed {s['config']['seed']}",
            ylabel="Transaction price ($)",
            ylim=(0, ceiling),
        )
        ax.legend(fontsize=8, frameon=False)
        if not s["metrics"]["trading_periods"]:
            ax.text(0.5, 0.5, "No transactions", transform=ax.transAxes, ha="center")
        axes[1, column].bar(periods, [r["volume"] for r in s["tape"]], color="#087e8b")
        axes[1, column].set(
            ylabel="Shares traded",
            ylim=(0, max(1, max(r["volume"] for r in s["tape"])) * 1.2),
        )
        for side, color in [("buy", "#087e8b"), ("sell", "#ce6c2b")]:
            axes[2, column].plot(
                periods,
                [
                    sum(
                        r["admitted_quantity"]
                        for r in s["rows"]
                        if r["period"] == t and r["side"] == side
                    )
                    for t in periods
                ],
                color=color,
                label=side,
            )
        axes[2, column].set(
            ylabel="Admitted order units", xlabel="Market period", ylim=(0, None)
        )
        axes[2, column].legend(frameon=False)
        for row in range(3):
            axes[row, column].set_xlim(0.5, 30.5)
            axes[row, column].spines[["top", "right"]].set_visible(False)
            axes[row, column].grid(alpha=0.15)
    for ext in ["png", "pdf", "svg"]:
        fig.savefig(output / f"markets.{ext}", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(
        n, 1, figsize=(12, 3.5 * n), squeeze=False, layout="constrained"
    )
    for ax, s in zip(axes[:, 0], sessions):
        names = sorted(
            s["accounts"], key=lambda name: (s["persona_assignment"][name], name)
        )
        cells = np.zeros((12, 30))
        for r in s["rows"]:
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
        for r in s["rows"]:
            if r["signed_fill"]:
                ax.text(
                    r["period"] - 1,
                    names.index(r["trader"]),
                    str(abs(r["signed_fill"])),
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=8,
                    bbox={"facecolor": "#172e3a", "edgecolor": "none", "pad": 1},
                )
        ax.set_yticks(
            range(12),
            [f"{x[-2:]} · {s['persona_assignment'][x]}" for x in names],
            fontsize=9,
        )
        ax.set_xticks(range(30), range(1, 31), fontsize=8)
        ax.set(
            title=f"Seed {s['config']['seed']} · buy (teal), sell (orange), hold (gray)",
            xlabel="Market period · numbers mark filled shares",
        )
    for ext in ["png", "pdf", "svg"]:
        fig.savefig(output / f"decisions.{ext}", dpi=160, bbox_inches="tight")
    plt.close(fig)
    rows = [r for s in sessions for r in s["rows"]]
    trades = [r for s in sessions for r in s["trades"]]
    write_csv(output / "all-orders.csv", rows)
    write_csv(output / "executed-trades.csv", trades)
    write_csv(
        output / "trader-accounts.csv", [r for s in sessions for r in s["traders"]]
    )
    summary = {
        "sessions": len(sessions),
        "decisions": len(rows),
        "shares_traded": len(trades),
        "recorded_cost": sum(s["cost"] for s in sessions),
        "diagnostics": diagnostics,
        "audits": audits,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "trading-data.json").write_text(json.dumps(sessions, indent=2) + "\n")
    findings = table(
        [
            "Seed",
            "Buy / sell / hold",
            "Shares traded",
            "Traded periods",
            "Peak price",
            "Peak period",
            "High-price periods",
            "Largest post-peak fall",
        ],
        [
            [
                s["config"]["seed"],
                " / ".join(
                    str(Counter(r["side"] for r in s["rows"])[side])
                    for side in ["buy", "sell", "hold"]
                ),
                s["metrics"]["volume"],
                s["metrics"]["trading_periods"],
                "—" if d["peak_price"] is None else f"${d['peak_price']:.2f}",
                d["peak_period"] or "—",
                len(d["periods_at_or_above_17_50"]),
                "—"
                if d["post_peak_drawdown"] is None
                else f"{d['post_peak_drawdown']:.1%}",
            ]
            for s, d in zip(sessions, diagnostics)
        ],
    )
    counts = [
        sum(d[k] for d in diagnostics)
        for k in ["excursion", "sustained_excursion", "excursion_then_20pct_fall"]
    ]
    conclusion = f"{counts[0]} of {n} markets reached $17.50; {counts[1]} sustained that level for at least two consecutive periods; {counts[2]} had such an excursion followed by a fall of at least 20% from the observed peak."
    persona_rows = []
    for kind in THEORY:
        subset = [r for r in rows if r["persona"] == kind]
        c = Counter(r["side"] for r in subset)
        persona_rows.append(
            [
                kind,
                len(subset),
                c["buy"],
                c["sell"],
                c["hold"],
                sum(abs(r["signed_fill"]) for r in subset),
            ]
        )
    images = {
        name: base64.b64encode((output / f"{name}.png").read_bytes()).decode()
        for name in ["markets", "decisions"]
    }
    prompts = "".join(
        f"<details><summary>{name}</summary><p>{html.escape(text)}</p></details>"
        for name, text in THEORY.items()
    )
    previous = []
    for path in sorted((ROOT / "runs" / "gpt-4o-mini-pilot").glob("*/summary.json")):
        s = json.loads(path.read_text())
        m = s["metrics"]
        previous.append(
            [
                s["config"]["treatment"],
                m["volume"],
                m["trading_periods"],
                "—" if m["peak_price"] is None else f"${m['peak_price']:.2f}",
            ]
        )
    css = (ROOT / "report_assets" / "full_report.css").read_text()
    content = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>The paper's six trader archetypes — follow-up</title><style>{css}</style><main>
<section class="hero"><p class="eyebrow">Paper-archetype follow-up · local EDSL / gpt-4o-mini</p><h1>All six trader archetypes.<br>Did a bubble emerge?</h1><p class="dek">Two Rational Arbitrageurs, two Momentum Chasers, two Bubble Timers, two Precommitters, two Noise Traders, and two Overconfident Contrarians in every market.</p>
<div class="metrics"><div><strong>{n}</strong><span>30-period sessions</span></div><div><strong>{len(rows):,}</strong><span>actual LLM decisions</span></div><div><strong>{len(trades)}</strong><span>shares traded</span></div><div><strong>${summary["recorded_cost"]:.2f}</strong><span>recorded model cost</span></div></div></section>
<section><h2>Observed result</h2><p>{conclusion}</p>{findings}<figure><img alt="Prices, trading volume, and admitted order units in each session" src="data:image/png;base64,{images["markets"]}"><figcaption>Only actual transaction prices are plotted. No-trade periods are gaps. $14 is fundamental value and $17.50 is the excursion threshold.</figcaption></figure></section>
<section><h2>What changed—and what this comparison establishes</h2><p>The first pilot already used behavioral framing: BT+OC+PC and the source's verbatim evolved personas. Neither produced a bubble. This follow-up changes the theory population to the six types on PDF page 14, adding RA, MC, and NT. It uses the same reconstructed persona wording, model, temperature, initial reference, cash presentation, auction, dividends, interest, and horizon.</p><p>The first pilot therefore remains a non-replication of the source's reported bubble behavior under this implementation. Adding types checks composition; it does not correct the model substitution or recover missing original theory prompt wording. The paper's highlighted composition was BT+OC+PC, not the all-six mix.</p><h3>Earlier single-session pilot</h3>{table(["Condition", "Shares traded", "Traded periods", "Peak price"], previous)}<p>The follow-up seeds are 140926–140928. Seed 140926 shares the earlier dividend and tie-break sequence; model draws remain stochastic. With three new markets and one previous market per comparison condition, these are descriptive results rather than an identified treatment effect.</p></section>
<section><h2>All trader decisions</h2><figure><img alt="All 1080 trader decisions with fills overlaid" src="data:image/png;base64,{images["decisions"]}"><figcaption>Each cell is an actual decision. Filled-share counts appear in dark cells. Repeated buy or sell orders do not count as transactions unless they match.</figcaption></figure>{table(["Type", "Decisions", "Buy", "Sell", "Hold", "Filled side-units"], persona_rows)}<p>Filled side-units count a transaction once for its buyer and once for its seller; their sum is twice market volume.</p></section>
<section><h2>Diagnostics fixed before these results</h2><p>The <a href="../PAPER_SIX_ARCHETYPES.md">design note</a> specifies a $17.50 excursion threshold, two consecutive calendar periods at or above it as a sustained excursion, and a subsequent 20% fall as a crash diagnostic. The latter two are our operational diagnostics, not definitions supplied by the paper. Redemption never counts as a trade or crash. Every seed is reported.</p><p>The economic rules are unchanged: 12 traders, $100 and four shares each, 5% cash interest, $0.40/$1.00 dividends with equal probability, and $14 terminal redemption. The existing independent audit verifies cash, shares, order limits, private observations, prompt inclusion, and 360 accepted responses plus 30 settlements for each market.</p></section>
<section><h2>Exact reconstructed prompts used</h2><p>These expand the short descriptions on PDF page 14. They are not the unavailable original theory prompts. Each follows the original pilot's common instruction: “You are a participant in an experimental asset market. Maximize your final cash wealth.”</p>{prompts}</section>
<section><h2>Downloads and evidence</h2><div class="downloads"><a href="trader-example.md">One complete trader presentation and response</a><a href="markets.pdf">Market figure PDF</a><a href="decisions.pdf">All decisions figure PDF</a><a href="all-orders.csv">Every order and rationale</a><a href="trader-accounts.csv">All account decompositions</a><a href="trading-data.json">Complete data</a><a href="summary.json">Metrics and audits</a></div><p>Source: Ngo et al., <em>Building Traders: Persona Construction for LLM Agents in Experimental Asset Markets</em>, supplied September 2026 presentation, PDF pages 14–17 and 25. Source and execution caveats are documented in the original <a href="../report/index.html">pilot report</a>. New raw evidence is saved under <code>examples/asset_market/runs/paper-six-archetypes/</code>.</p></section></main></html>"""
    (output / "index.html").write_text(content)
    return output / "index.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs", type=Path, default=ROOT / "runs" / "paper-six-archetypes"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "paper-six-report")
    args = parser.parse_args()
    print(build(args.runs, args.output))
