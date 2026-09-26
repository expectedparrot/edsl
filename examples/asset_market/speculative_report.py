"""Audit and compare speculative-v1 with the earlier all-six prompt treatment."""

from __future__ import annotations

import base64
from collections import Counter
import html
import json
import os
import sqlite3

from jinja2 import StrictUndefined, Template

from .audit import audit_session
from .experiment import ROOT
from .full_report import reconstruct, table, write_csv
from .paper_followup_report import excursion_diagnostics
from .run_speculative import prompt_hash
from .speculative_prompts import COMMON, PERSONAS, VERSION, question_text


def audit_variant(path):
    audit = audit_session(path)
    config = json.loads((path / "config.json").read_text())
    assert config["prompt_variant"] == VERSION
    assert config["prompt_implementation_sha256"] == prompt_hash()
    summary = json.loads((path / "summary.json").read_text())
    with sqlite3.connect(f"file:{path / 'shared-state.sqlite'}?mode=ro", uri=True) as c:
        observations = {
            r["execution_id"]: r["value"]
            for (payload,) in c.execute(
                "SELECT payload FROM state_events WHERE kind='read'"
            )
            for r in [json.loads(payload)]
        }
    for line in (path / "model-calls.jsonl").read_text().splitlines():
        call = json.loads(line)
        view = observations[call["work_item_id"]]
        template = Template(
            question_text(view["period"], config["periods"]), undefined=StrictUndefined
        )
        expected = template.render(shared_state={"market": view}).strip()
        prompt = call["result"]["prompt"]
        actual = prompt["decision_user_prompt"]["text"]
        assert actual.startswith(expected), (
            "actual trader question differs from variant"
        )
        kind = summary["persona_assignment"][call["participant"]]
        assert COMMON + PERSONAS[kind] in prompt["decision_system_prompt"]["text"]
    audit["variant_hash_and_all_rendered_prompts_verified"] = True
    return audit


def save_example(path, output):
    call = json.loads((path / "model-calls.jsonl").read_text().splitlines()[0])
    prompt = call["result"]["prompt"]
    presentation = {
        "session": path.name,
        "participant": call["participant"],
        "step": call["step"],
        "system_prompt": prompt["decision_system_prompt"]["text"],
        "user_prompt": prompt["decision_user_prompt"]["text"],
        "response": call["result"]["answer"]["decision"],
    }
    (output / "trader-example.json").write_text(
        json.dumps(presentation, indent=2) + "\n"
    )
    (output / "trader-example.md").write_text(
        f"# Actual speculative-v1 trader presentation\n\n{path.name}, "
        f"{call['participant']}, {call['step']}. Exact saved strings, including literal "
        "backslash-n sequences in the response-format suffix.\n\n## System prompt\n\n```text\n"
        + presentation["system_prompt"]
        + "\n```\n\n## User prompt\n\n```text\n"
        + presentation["user_prompt"]
        + "\n```\n\n## Actual response\n\n```json\n"
        + json.dumps(presentation["response"], indent=2)
        + "\n```\n"
    )


def build():
    output = ROOT / "speculative-report"
    output.mkdir(parents=True, exist_ok=True)
    (output / "prompt-design.md").write_text(
        "# Speculative v1: complete prompt design\n\n"
        "Newly authored exploratory intervention; not source-paper prompts.\n\n"
        "## Common system instruction\n\n"
        + COMMON
        + "\n\n"
        + "".join(f"## {kind}\n\n{text}\n\n" for kind, text in PERSONAS.items())
        + "## First-period question template\n\n```jinja2\n"
        + question_text(1, 30)
        + "\n```\n\nEDSL appends the same typed dictionary response instructions "
        "used in the original runs.\n"
    )
    paths = sorted((ROOT / "runs" / "speculative-v1").glob("*/summary.json"))
    assert len(paths) == 3, "expected all three sessions"
    audits = [audit_variant(p.parent) for p in paths]
    sessions = [reconstruct(p.parent) for p in paths]
    controls = [
        reconstruct(
            ROOT
            / "runs"
            / "paper-six-archetypes"
            / f"RA-MC-BT-PC-NT-OC-s{s['config']['seed']}"
        )
        for s in sessions
    ]
    diagnostics = [
        dict(seed=s["config"]["seed"], **excursion_diagnostics(s["tape"]))
        for s in sessions
    ]
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-market-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    import numpy as np

    observed = [
        r["price"]
        for s in sessions + controls
        for r in s["tape"]
        if r["price"] is not None
    ]
    fig, axes = plt.subplots(3, 3, figsize=(15, 9), layout="constrained")
    for column, (s, control) in enumerate(zip(sessions, controls)):
        periods = [r["period"] for r in s["tape"]]
        for data, color, label in [
            (control, "#8c979d", "Original prompts"),
            (s, "#087e8b", "Speculative v1"),
        ]:
            axes[0, column].plot(
                periods,
                [
                    r["price"] if r["price"] is not None else np.nan
                    for r in data["tape"]
                ],
                "o-",
                color=color,
                label=label,
            )
        axes[0, column].axhline(14, ls="--", color="#687982", label="Fundamental $14")
        axes[0, column].axhline(17.5, ls=":", color="#ce6c2b", label="Excursion $17.50")
        axes[0, column].set(
            title=f"Seed {s['config']['seed']}",
            ylabel="Transaction price ($)",
            ylim=(0, max(20, max(observed, default=14) * 1.1)),
        )
        axes[0, column].legend(fontsize=8)
        axes[1, column].bar(periods, [r["volume"] for r in s["tape"]], color="#087e8b")
        axes[1, column].set(ylabel="Shares traded · speculative v1", ylim=(0, None))
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
            ylabel="Admitted order units", xlabel="Period", ylim=(0, None)
        )
        axes[2, column].legend()
        for row in range(3):
            axes[row, column].set_xlim(0.5, 30.5)
            axes[row, column].grid(alpha=0.15)
            axes[row, column].spines[["top", "right"]].set_visible(False)
    for ext in ["png", "svg", "pdf"]:
        fig.savefig(output / f"markets.{ext}", dpi=160, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), layout="constrained")
    for ax, s in zip(axes, sessions):
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
                    fontsize=7,
                    bbox={"facecolor": "#172e3a", "edgecolor": "none", "pad": 1},
                )
        ax.set_yticks(
            range(12),
            [f"{name[-2:]} · {s['persona_assignment'][name]}" for name in names],
        )
        ax.set_xticks(range(30), range(1, 31), fontsize=8)
        ax.set(
            title=f"Seed {s['config']['seed']} · buy (teal), sell (orange), hold (gray)",
            xlabel="Period · numbers show filled shares",
        )
    for ext in ["png", "svg", "pdf"]:
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
        "variant": VERSION,
        "decisions": len(rows),
        "shares_traded": len(trades),
        "recorded_cost": sum(s["cost"] for s in sessions),
        "diagnostics": diagnostics,
        "audits": audits,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "trading-data.json").write_text(json.dumps(sessions, indent=2) + "\n")
    save_example(paths[0].parent, output)
    findings = table(
        [
            "Seed",
            "Buy / sell / hold",
            "Shares traded",
            "Traded periods",
            "Peak",
            "High-price periods",
            "Longest high streak",
            "Post-peak fall",
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
                len(d["periods_at_or_above_17_50"]),
                d["longest_consecutive_high_periods"],
                "—"
                if d["post_peak_drawdown"] is None
                else f"{d['post_peak_drawdown']:.1%}",
            ]
            for s, d in zip(sessions, diagnostics)
        ],
    )
    count = sum(d["excursion"] for d in diagnostics)
    sustained = sum(d["sustained_excursion"] for d in diagnostics)
    crash = sum(d["excursion_then_20pct_fall"] for d in diagnostics)

    def picture(name):
        return (
            "data:image/png;base64,"
            + base64.b64encode((output / f"{name}.png").read_bytes()).decode()
        )

    css = (ROOT / "report_assets" / "full_report.css").read_text()
    prompts = "".join(
        f"<details><summary>{kind}</summary><p>{html.escape(text)}</p></details>"
        for kind, text in PERSONAS.items()
    )
    ledger = "".join(
        f"<details><summary>Seed {s['config']['seed']} — all 360 orders and rationales</summary>"
        + table(
            [
                "Period",
                "Trader",
                "Type",
                "Side",
                "Limit",
                "Quantity",
                "Fill",
                "Rationale",
            ],
            [
                [
                    r["period"],
                    r["trader"],
                    r["persona"],
                    r["side"],
                    r["limit_price"],
                    r["admitted_quantity"],
                    r["signed_fill"],
                    r["rationale"],
                ]
                for r in s["rows"]
            ],
        )
        + "</details>"
        for s in sessions
    )
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Speculative prompts: asset market experiment</title><style>{css}</style><main>
<section class="hero"><p class="eyebrow">Exploratory prompt intervention · gpt-4o-mini</p><h1>Can speculative prompts induce a bubble?</h1><p class="dek">Three 30-period markets; all six archetypes; unchanged exchange and financial rules.</p><div class="metrics"><div><strong>{len(rows):,}</strong><span>LLM decisions</span></div><div><strong>{len(trades)}</strong><span>shares traded</span></div><div><strong>{count}/3</strong><span>markets reached $17.50</span></div><div><strong>${summary["recorded_cost"]:.2f}</strong><span>recorded model cost</span></div></div></section>
<section><h2>Observed result</h2><p>{count} of three markets reached $17.50, {sustained} sustained that level for two consecutive periods, and {crash} had an excursion followed by a fall of at least 20% from the observed peak. These are diagnostics of observed trades; a high opening price alone does not establish a rising bubble.</p>{findings}<img alt="Actual prices compared with the original prompts, volume, and order units" src="{picture("markets")}"><p>No-trade periods are gaps. The original all-six runs traded 20, 7, and 12 shares respectively, all at $14.</p></section>
<section><h2>What changed</h2><p>We removed the supplied fundamental-value answer and artificial opening reference; displayed account money in dollars; and strengthened resale, momentum, optimism, timing, and loss-aversion framing. The actual $14 terminal redemption and all dividend, interest, endowment, clearing, and collateral rules remain disclosed and unchanged.</p><p>These newly authored prompts are not the paper's prompts. This joint intervention cannot identify which wording change caused a difference. The same seeds fix assignments, dividends, and tie breaks, but model draws remain stochastic. The model runs were preceded by a cache-permission failure with no recorded model responses, preserved separately; no prompt tuning followed the LLM outcomes.</p><p><a href="../SPECULATIVE_PROMPTS.md">Design fixed before results</a> · <a href="prompt-design.md">Complete prompt design</a> · <a href="trader-example.md">One complete actual prompt and response</a></p></section>
<section><h2>All trading decisions</h2><img alt="All 1080 decisions, with executed shares labeled" src="{picture("decisions")}">{ledger}</section>
<section><h2>Exact persona instructions</h2><p>Common instruction: {html.escape(COMMON)}</p>{prompts}</section>
<section><h2>Validation and interpretation</h2><p>All three accounting and workflow audits passed. We also verified every actual system instruction and rendered question against this prompt version and its saved private state. Passing these checks establishes correct execution of this implementation; it does not establish realistic behavior or replication of the source paper.</p><p>Opening rationales exposed valuation and constraint misunderstandings. In seed 140926, both Rational Arbitrageurs bid $0.70 while discussing the expected one-period dividend. One called four shares the maximum affordable purchase despite holding $100. The full order ledger preserves these explanations. Removing the supplied valuation answer therefore also exposed limitations in the model's own valuation and arithmetic; price changes cannot be attributed solely to stronger speculative psychology.</p><p>Excursion means an actual price of at least $17.50. Sustained means at least two consecutive calendar periods at that level. Crash means a subsequent 20% decline from the observed peak after an excursion. The sustained and crash definitions are ours. Redemption is excluded, and no-trade periods break a streak.</p></section>
<section><h2>Downloads</h2><div class="downloads"><a href="markets.pdf">Market figure PDF</a><a href="decisions.pdf">Decision figure PDF</a><a href="all-orders.csv">All orders and forecasts</a><a href="executed-trades.csv">Executed trades</a><a href="trader-accounts.csv">Account outcomes</a><a href="trading-data.json">Full data</a><a href="summary.json">Metrics and audits</a></div></section></main></html>'''
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
