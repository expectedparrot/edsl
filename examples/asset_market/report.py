"""Build a self-contained HTML report and standalone figures from saved runs."""

from __future__ import annotations

import argparse
import base64
from collections import defaultdict
from collections import Counter
import csv
import html
import io
import json
import math
import os
from pathlib import Path
import statistics


def build_report(runs: Path, output: Path):
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-market-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True, exist_ok=True)
    sessions = [
        (p.parent, json.loads(p.read_text()))
        for p in sorted(runs.glob("*/summary.json"))
    ]
    if not sessions:
        raise ValueError(f"No session summaries under {runs}")
    preferred = {"baseline": 0, "BT+OC+PC": 1, "evolved": 2}
    sessions.sort(
        key=lambda pair: (
            preferred.get(pair[1]["config"]["treatment"], 3),
            pair[1]["config"]["treatment"],
            pair[1]["config"]["seed"],
        )
    )
    summaries = [s for _, s in sessions]
    groups = defaultdict(list)
    for path, session in sessions:
        groups[session["config"]["treatment"]].append((path, session))
    # Keep the figure bounded for a full 63-composition grid; diagnostics below
    # still include every market. The first six conditions are explicitly named.
    plotted = list(groups.items())[:6]
    n = len(plotted)
    observed_prices = [
        row["price"] for s in summaries for row in s["tape"] if row["price"] is not None
    ]
    price_ceiling = max(20, 1.1 * max(observed_prices, default=14))
    volume_ceiling = max(
        1, 1.15 * max(row["volume"] for s in summaries for row in s["tape"])
    )
    plotted_forecasts = [14.0]
    fig, axes = plt.subplots(
        3, n, figsize=(5 * n, 9), squeeze=False, constrained_layout=True
    )
    plt.rcParams.update({"font.family": "sans-serif"})
    for column, (treatment, group) in enumerate(plotted):
        for path, session in group:
            tape = session["tape"]
            periods = [row["period"] for row in tape]
            prices = [
                row["price"] if row["price"] is not None else math.nan for row in tape
            ]
            axes[0, column].plot(
                periods,
                prices,
                "o-",
                markersize=3,
                label=f"seed {session['config']['seed']}",
                color="#076b83" if len(group) == 1 else None,
            )
            axes[1, column].plot(
                periods, [row["volume"] for row in tape], "o-", markersize=3
            )
            orders = json.loads((path / "orders.json").read_text())
            by_period = defaultdict(list)
            for order in orders:
                by_period[order["period"]].append(order["decision"])
            for horizon, color in [
                (0, "#076b83"),
                (2, "#bf631d"),
                (5, "#a73962"),
                (10, "#7155a6"),
            ]:
                xs = [
                    t
                    for t in sorted(by_period)
                    if t + horizon <= session["config"]["periods"]
                ]
                forecasts = [
                    statistics.mean(d[f"forecast_{horizon}"] for d in by_period[t])
                    for t in xs
                ]
                plotted_forecasts.extend(forecasts)
                axes[2, column].plot(
                    xs,
                    forecasts,
                    color=color,
                    alpha=0.75,
                    label=f"h={horizon}" if session is group[0][1] else None,
                )
        axes[0, column].set_title(
            f"{treatment}\n{len(group)} market(s)", loc="left", fontweight="bold"
        )
        for row in [0, 2]:
            axes[row, column].axhline(14, color="#737b84", linestyle="--", linewidth=1)
            axes[row, column].set_ylabel(
                "Price ($)" if row == 0 else "Mean forecast ($)"
            )
        axes[1, column].set_ylabel("Shares traded")
        axes[0, column].set_ylim(0, price_ceiling)
        axes[1, column].set_ylim(0, volume_ceiling)
        from matplotlib.ticker import MaxNLocator

        axes[1, column].yaxis.set_major_locator(MaxNLocator(integer=True))
        axes[2, column].set_xlabel("Market period")
        axes[2, column].legend(frameon=False, ncol=4, fontsize=8)
        for row in range(3):
            axes[row, column].grid(alpha=0.15)
            axes[row, column].spines[["top", "right"]].set_visible(False)
            horizon = max(s["config"]["periods"] for _, s in group)
            axes[row, column].set_xlim(0.5, horizon + 0.5)
        if not any(s["metrics"]["trading_periods"] for _, s in group):
            axes[0, column].text(
                0.5,
                0.75,
                "No transactions",
                ha="center",
                transform=axes[0, column].transAxes,
                color="#737b84",
            )
    for column in range(n):
        axes[2, column].set_ylim(
            min(plotted_forecasts) - 0.1, max(plotted_forecasts) + 0.1
        )
        axes[2, column].ticklabel_format(axis="y", style="plain", useOffset=False)
    fig.suptitle(
        "Asset-market reconstruction · observed trades, volume, and beliefs",
        fontsize=16,
    )
    for extension in ["png", "pdf", "svg"]:
        fig.savefig(
            output / f"markets.{extension}",
            dpi=160,
            bbox_inches="tight",
            pad_inches=0.15,
        )
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode()

    def fmt(value, digits=3):
        return "—" if value is None else f"{value:.{digits}f}"

    rows = []
    costs = []
    accuracy = []
    behavior = defaultdict(Counter)
    for path, session in sessions:
        m = session["metrics"]
        orders = json.loads((path / "orders.json").read_text())
        prices = {row["period"]: row["price"] for row in session["tape"]}
        for horizon in (0, 2, 5, 10):
            errors = [
                abs(
                    order["decision"][f"forecast_{horizon}"]
                    - prices[order["period"] + horizon]
                )
                for order in orders
                if prices.get(order["period"] + horizon) is not None
            ]
            accuracy.append(
                {
                    "treatment": session["config"]["treatment"],
                    "seed": session["config"]["seed"],
                    "horizon": horizon,
                    "valid_forecasts": len(errors),
                    "MAE": statistics.mean(errors) if errors else None,
                }
            )
        for order in orders:
            key = (
                session["config"]["treatment"],
                session["persona_assignment"][order["trader"]],
            )
            behavior[key][order["decision"]["side"]] += 1
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(value))}</td>"
                for value in [
                    session["config"]["treatment"],
                    session["config"]["seed"],
                    "complete" if session["complete"] else "INCOMPLETE",
                    m["trading_periods"],
                    m["no_trade_periods"],
                    m["volume"],
                    fmt(m["peak_price"], 2),
                    fmt(m["peak_fraction"]),
                    fmt(m["RAD_traded_periods"]),
                    fmt(m["post_peak_drawdown"]),
                    session["order_rejections"],
                    session["quantity_reductions"],
                ]
            )
            + "</tr>"
        )
        call_file = path / "model-calls.jsonl"
        for line in call_file.read_text().splitlines() if call_file.exists() else []:
            call = json.loads(line)
            raw = call["result"].get("raw_model_response", {})
            for name, value in raw.items():
                if name.endswith("_cost") and isinstance(value, (int, float)):
                    costs.append(value)
    wealth_rows = []
    for _, session in sessions:
        for name, account in session["accounts"].items():
            wealth_rows.append(
                {
                    "treatment": session["config"]["treatment"],
                    "seed": session["config"]["seed"],
                    "trader": name,
                    "persona": session["persona_assignment"][name],
                    "cash": account["cash_cents"] / 100,
                    "shares": account["shares"],
                    "complete": session["complete"],
                }
            )
    for name, data in [
        ("forecast-accuracy.csv", accuracy),
        ("terminal-wealth.csv", wealth_rows),
    ]:
        with (output / name).open("w") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    behavior_rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(v))}</td>"
            for v in [condition, persona, counts["buy"], counts["sell"], counts["hold"]]
        )
        + "</tr>"
        for (condition, persona), counts in sorted(behavior.items())
    )
    backend_names = ", ".join(sorted({s["config"]["backend"] for s in summaries}))
    model_names = ", ".join(
        sorted({s["config"]["model"] or "scripted test" for s in summaries})
    )
    complete = sum(s["complete"] for s in summaries)
    observed_trades = sum(s["metrics"]["volume"] for s in summaries)
    no_trade_sessions = sum(s["metrics"]["trading_periods"] == 0 for s in summaries)
    large_peaks = sum(s["metrics"]["above_1_25F"] for s in summaries)
    findings = f"{observed_trades} shares traded across {len(summaries)} markets; {no_trade_sessions} market(s) had no transactions. {large_peaks} market(s) reached a transaction price of at least $17.50 (1.25 × fundamental value)."
    plotted_note = (
        ""
        if len(groups) <= 6
        else "For readability the figure shows the first six conditions; the diagnostics table includes every session."
    )
    note = (
        "These are actual LLM decisions, executed through local EDSL."
        if backend_names == "llm"
        else "This report includes scripted mechanism checks. Scripted prices are not LLM evidence."
    )
    cost_text = (
        f"Recorded model cost: ${sum(costs):.4f}."
        if costs
        else "Provider cost was not available in the saved raw records."
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Building Traders · EDSL reconstruction</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#203039;background:#f7f9fa;margin:0}}main{{max-width:1250px;margin:auto;padding:48px 28px}}
h1{{font-size:40px;line-height:1.15;max-width:900px}}h2{{margin-top:38px}}.eyebrow{{text-transform:uppercase;letter-spacing:2px;color:#076b83;font-size:13px}}
.card{{background:white;padding:24px;border:1px solid #dce4e7;border-radius:12px;margin:24px 0}}.note{{border-left:4px solid #bf631d;padding:12px 20px;background:#fff6ed}}
table{{border-collapse:collapse;font-size:13px;width:100%}}td,th{{text-align:left;border-bottom:1px solid #e0e5e8;padding:10px;white-space:nowrap}}
th{{font-weight:600}}img{{width:100%;height:auto}}.scroll{{overflow-x:auto}}a{{color:#076b83}}code{{font-size:13px}}li{{margin:8px 0}}
</style><main><div class="eyebrow">EDSL · shared state + durable workflows</div>
<h1>Building traders, one sealed market period at a time</h1>
<p>Reconstruction of the asset-market design in Ngo et al.’s September 2026 slides.</p>
<div class="card"><strong>{complete}/{len(summaries)} markets complete</strong> · {html.escape(model_names)} · {html.escape(backend_names)} backend
<p>{note} {cost_text}</p><p>12 traders per market; $100 and 4 shares initially; 5% cash interest; stochastic $0.40/$1 dividends; $14 terminal redemption.</p></div>
<div class="note"><strong>Scope:</strong> These runs test a reconstructed design with a different model and explicit exchange assumptions.
They do not establish replication of the paper’s bubble or treatment effects. No human microdata or evolutionary optimization was re-created.
Single-session comparisons have no estimate of between-market uncertainty.</div>
<h2>Observed market paths</h2><p>{findings} {plotted_note}</p><div class="card"><img alt="Transaction prices, trade volume, and mean forecasts by treatment" src="data:image/png;base64,{encoded}">
<p>Dashed line: $14 fundamental value. Missing transaction prices are gaps. Forecast curves omit horizons beyond redemption.
A price path can be flat without generating a bubble even though an earliest peak is mathematically defined.</p>
<a href="markets.pdf">Export PDF figure</a> · <a href="markets.svg">SVG</a> · <a href="markets.png">PNG</a></div>
<h2>Session diagnostics</h2><div class="card scroll"><table><thead><tr>{"".join("<th>" + x + "</th>" for x in ["Condition", "Seed", "Status", "Traded periods", "No trade", "Volume", "Peak $", "Peak / T", "RAD", "Drawdown", "Rejected", "Size capped"])}</tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p>RAD averages |price − 14| / 14 over traded periods only. Drawdown is the greatest proportional fall from the observed peak to a later transaction.
No-trade sessions have no peak or deviation estimate. Capped quantities are retained alongside submitted orders.</p>
<h2>What traders submitted</h2><div class="card scroll"><table><thead><tr><th>Condition</th><th>Persona</th><th>Buy orders</th><th>Sell orders</th><th>Holds</th></tr></thead>
<tbody>{behavior_rows}</tbody></table></div><p>These are submitted sides, not fills. A market needs compatible bids and offers to trade.
The evolved instructions are present in the recorded system prompts; a persona description does not guarantee that a model will follow its stated behavior.</p>
<h2>How to read the comparison</h2><ul>
<li><strong>Baseline:</strong> no behavioral persona beyond the common profit objective.</li>
<li><strong>BT+OC+PC:</strong> four bubble timers, four overconfident contrarians, and four precommitters. Text reconstructed from the slide summaries.</li>
<li><strong>Evolved:</strong> seven Trend Readers, three Noise, and two Reversion Riders, using the supplied verbatim persona texts.</li>
<li>The source reports mean peak fractions of 0.628 for same-market humans, 0.627 for the highlighted theory mix, and 0.633 for evolved personas.
These are external summary benchmarks. Their raw price paths are unavailable, and none are plotted as reconstructed human observations.</li></ul>
<h2>Execution and evidence</h2><p>Every period fans out to 12 private trader tasks, waits for all sealed orders, clears one uniform price,
and atomically updates balances and income in shared state. The exchange uses deterministic code; only traders use the language model.</p>
<p>SQLite workflow and state histories, raw model calls, serialized definitions, accepted Results packages, and order/period CSVs are saved under
<code>{html.escape(str(runs))}</code>. See the example README for every reconstruction choice and reproducible commands.</p>
<p><a href="forecast-accuracy.csv">Forecast accuracy by horizon</a> · <a href="terminal-wealth.csv">Terminal wealth by trader</a></p>
</main></html>"""
    (output / "index.html").write_text(page)
    (output / "summary.json").write_text(
        json.dumps(
            {
                "sessions": len(summaries),
                "complete": complete,
                "model_cost": sum(costs) if costs else None,
                "forecast_accuracy": accuracy,
            },
            indent=2,
        )
        + "\n"
    )
    return output / "index.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_report(args.runs, args.output))
