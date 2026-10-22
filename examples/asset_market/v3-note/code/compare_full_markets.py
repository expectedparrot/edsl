"""Compare two completed, audited markets with the same economic specification."""

import argparse
from decimal import Decimal, ROUND_HALF_UP
import html
import json
import os
from pathlib import Path


def compare(previous, current):
    old_spec = json.loads((previous / "experiment.json").read_text())
    new_spec = json.loads((current / "experiment.json").read_text())
    # Differences in answers should not be confused with changed market rules.
    assert old_spec["states"] == new_spec["states"]
    assert old_spec["agents"] == new_spec["agents"]
    assert old_spec["execution_plan"] == new_spec["execution_plan"]
    assert [s["survey"]["questions"] for s in old_spec["workflow"]["steps"]] == [
        s["survey"]["questions"] for s in new_spec["workflow"]["steps"]
    ]
    markets = [json.loads((p / "market.json").read_text()) for p in (previous, current)]
    summaries = [
        json.loads((p / "report/summary.json").read_text()) for p in (previous, current)
    ]
    assert all(s["audit"]["passed"] for s in summaries)
    assert [r["dividend"] for r in markets[0]["tape"]] == [
        r["dividend"] for r in markets[1]["tape"]
    ]
    assert all(s["decisions"] == 360 and s["rounds"] == 30 for s in summaries)
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-market-compare-mpl")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    report = current / "report"
    names = sorted(markets[0]["accounts"])
    current_key = new_spec.get("metadata", {}).get("run_label", "current")
    current_label = current_key.upper()
    previous_label = (
        old_spec.get("metadata", {}).get("run_label", "previous run").upper()
    )
    labels = [previous_label, current_label + ": typed configuration"]
    colors = ["#71839b", "#147e77"]
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout="constrained", sharex=True)
    for i, (market, label, color) in enumerate(zip(markets, labels, colors)):
        x = [r["period"] for r in market["tape"]]
        price = [
            r["price"] if r["price"] is not None else np.nan for r in market["tape"]
        ]
        axes[0].plot(
            x, price, "o-", color=color, label=label, linewidth=1.8, markersize=4
        )
        axes[1].bar(
            np.array(x) + (i - 0.5) * 0.36,
            [r["volume"] for r in market["tape"]],
            width=0.36,
            color=color,
            label=label,
        )
    axes[0].axhline(14, color="#333", linestyle="--", label="Fundamental value: $14")
    axes[0].scatter(
        [30.8],
        [14],
        marker="D",
        color="#333",
        s=38,
        label="Terminal redemption (not a trade)",
    )
    axes[0].set(
        ylabel="Transaction price ($)",
        title="Fresh LLM decisions under the same market rules",
    )
    axes[0].legend(fontsize=9, ncol=2)
    axes[1].set(
        ylabel="Shares traded", xlabel="Round", xticks=range(1, 31), xlim=(0.5, 31.5)
    )
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(report / "comparison.png", dpi=160)
    fig.savefig(report / "comparison.pdf")
    plt.close(fig)

    # Same dividend stream and endowment: a common no-trading benchmark.
    passive = 10000
    for row in markets[0]["tape"]:
        passive += (
            int(
                (Decimal(passive) * Decimal(".05")).quantize(
                    Decimal(1), rounding=ROUND_HALF_UP
                )
            )
            + round(row["dividend"] * 100) * 4
        )
    passive += 4 * 1400
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    for i, (market, label, color) in enumerate(zip(markets, labels, colors)):
        values = [(market["accounts"][n]["cash_cents"] - passive) / 100 for n in names]
        ax.bar(
            np.arange(len(names)) + (i - 0.5) * 0.36,
            values,
            width=0.36,
            color=color,
            label=label,
        )
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set(
        xticks=range(len(names)),
        xticklabels=[n.removeprefix("trader-") for n in names],
        xlabel="Trader (same persona and seat in both runs)",
        ylabel="Final cash minus passive cash ($)",
        title=f"Trading outcomes relative to holding initial shares: passive cash ${passive / 100:.2f}",
    )
    ax.legend()
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(report / "wealth-comparison.png", dpi=160)
    fig.savefig(report / "wealth-comparison.pdf")
    plt.close(fig)

    diagnostics = []
    for market in markets:
        violations = []
        for row in market["order_log"]:
            for horizon in (2, 5, 10):
                forecast = row["decision"][f"forecast_{horizon}"]
                if row["period"] + horizon > 30 and abs(forecast - 14) > 1e-8:
                    violations.append(
                        {
                            "trader": row["trader"],
                            "period": row["period"],
                            "horizon": horizon,
                            "forecast": forecast,
                        }
                    )
        diagnostics.append(
            {
                "terminal_forecast_violations": len(violations),
                "violations": violations,
                "transaction_rounds_above_fundamental": sum(
                    r["price"] is not None and r["price"] > 14 for r in market["tape"]
                ),
            }
        )
    comparison = {
        "same_economics_agents_and_question_templates": True,
        "same_realized_dividends": True,
        "passive_terminal_cash": passive / 100,
        "previous": {"path": str(previous), **summaries[0], **diagnostics[0]},
        current_key: {"path": str(current), **summaries[1], **diagnostics[1]},
    }
    (report / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    metrics = [
        ("Trading rounds", "trading_rounds"),
        ("Shares traded (turnover)", "volume"),
        ("First trade round", "first_trade_round"),
        ("Peak price ($)", "peak_price"),
        ("Peak round (first occurrence)", "peak_round"),
        ("Last transaction price ($)", "last_transaction_price"),
    ]
    rows = "".join(
        f"<tr><th>{label}</th><td>{summaries[0][key]}</td><td>{summaries[1][key]}</td></tr>"
        for label, key in metrics
    )
    for i, summary in enumerate(summaries):
        summary["formatted_cost"] = f"${summary['recorded_model_cost']:.2f}"
    rows += f"<tr><th>Recorded model cost</th><td>{summaries[0]['formatted_cost']}</td><td>{summaries[1]['formatted_cost']}</td></tr>"
    current_summary = summaries[1]
    observed = [r for r in markets[1]["tape"] if r["price"] is not None]
    if observed:
        peak = current_summary["peak_price"]
        if peak > 14:
            interpretation = f"{current_label} reached ${peak:.2f}, {(peak / 14 - 1) * 100:.1f}% above the $14 fundamental value."
            peak_row = next(r for r in observed if r["price"] == peak)
            unit = "share" if peak_row["volume"] == 1 else "shares"
            interpretation += f" The first peak involved {peak_row['volume']} {unit} in round {peak_row['period']}."
        else:
            interpretation = f"{current_label}'s peak transaction price was ${peak:.2f}; no trades occurred above the $14 fundamental value."
        if current_summary["post_peak_drawdown"] is not None:
            interpretation += f" The largest observed transaction-price decline after the first peak was {100 * current_summary['post_peak_drawdown']:.1f}%."
    else:
        interpretation = f"{current_label} produced no transactions. Submitted quotes alone do not establish a price bubble."
    previous_serial = (
        summaries[0].get("execution", {}).get("initial_serial_decisions", 0)
    )
    execution_note = (
        f"The previous run had {previous_serial} decisions outside the paired-batch path."
        if previous_serial
        else "Both runs used paired EDSL jobs from round 1."
    )
    display_label = html.escape(current_label)
    incomplete = current_summary.get("incomplete_result_records", 0)
    recovery_note = (
        f' {incomplete} incomplete result record(s) were retained, and missing decisions were retried without changing the economic rules. The recorded cost may exclude a failed call if it returned no usage data. <a href="../recovery.json">Recovery record</a>.'
        if incomplete
        else ""
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asset market {display_label}: comparison</title><style>body{{max-width:1100px;margin:40px auto;padding:0 20px;font:17px/1.55 system-ui;color:#243448}}img{{width:100%}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:8px;border-bottom:1px solid #ddd}}pre{{white-space:pre-wrap}}</style>
<h1>Asset market {display_label}</h1><p>{html.escape(interpretation)}</p>
<p>Thirty rounds, twelve GPT-5 mini traders, and 360 fresh decisions. {display_label} uses the validated typed configuration and one paired 12-interview EDSL job per round from the start. {execution_note}{recovery_note}</p>
<p>The economic rules, personas, seats, question templates, and realized dividends are identical. This is another stochastic model realization, not a test of a changed economic treatment.</p>
<table><tr><th>Measure</th><th>{html.escape(previous_label)}</th><th>{display_label}</th></tr>{rows}</table>
<img src="comparison.png" alt="Transaction prices and traded volume in both markets">
<p>Gaps mean no transaction. Redemption at $14 is a contractual payoff, not an observed market crash. Two sessions cannot establish the frequency of bubbles.</p>
<img src="wealth-comparison.png" alt="Individual final wealth relative to passive holding in both markets">
<p>The accounting and private-prompt audits passed for both runs. {display_label} contained {diagnostics[1]["terminal_forecast_violations"]} forecasts inconsistent with the instruction to use $14 beyond the last trading round, compared with {diagnostics[0]["terminal_forecast_violations"]} previously. Valid accounting does not imply correct economic reasoning.</p>
<p><a href="index.html">{display_label}: all trading decisions and rationales</a> · <a href="comparison.pdf">Price comparison PDF</a> · <a href="comparison.json">Comparison data</a> · <a href="../rules.json">Typed rules</a> · <a href="../treatment.json">Trader treatment</a></p></html>"""
    (report / "comparison.html").write_text(page)
    print(
        json.dumps(
            {
                "status": "ok",
                "report": str(report / "comparison.html"),
                current_key: summaries[1],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous", type=Path)
    parser.add_argument("current", type=Path)
    args = parser.parse_args()
    compare(args.previous, args.current)
