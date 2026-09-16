"""A full trading report, interactive replay, and portable data exports.

Uses saved completed sessions only; never generates trader decisions.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter
import csv
from datetime import date
import hashlib
import html
import json
from pathlib import Path
import random
import statistics

from .audit import audit_session
from .experiment import ROOT, THEORY, cents
from .report import build_report


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def reconstruct(path):
    """Recover opening/closing portfolios and exact seeded unit matching."""
    s = json.loads((path / "summary.json").read_text())
    if not s["complete"]:
        raise ValueError(f"Incomplete session: {path}")
    s["id"] = path.name
    s["rows"], s["trades"], s["traders"] = [], [], []
    s["books"] = []
    s["cost"] = 0
    calls = path / "model-calls.jsonl"
    if calls.exists():
        for line in calls.read_text().splitlines():
            raw = json.loads(line)["result"]["raw_model_response"]
            s["cost"] += raw.get("decision_cost", 0) or 0
    no_trade_cash, no_trade_shares = 10000, 4
    for t in s["tape"]:
        no_trade_cash += (no_trade_cash * 5 + 50) // 100 + cents(
            t["dividend"]
        ) * no_trade_shares
    s["no_trade_wealth"] = (no_trade_cash + 1400 * no_trade_shares) / 100
    for name, account in sorted(s["accounts"].items()):
        cash, shares = 10000, 4
        totals = Counter()
        for h in account["history"]:
            d = h["decision"]
            opening_cash, opening_shares = cash, shares
            cash -= h["fill"] * cents(h["transaction_price"] or 0)
            shares += h["fill"]
            interest = cents(h["interest"])
            dividends = cents(h["dividend_per_share"]) * shares
            cash += interest + dividends
            totals[h["side"]] += 1
            totals["interest_cents"] += interest
            totals["dividends_cents"] += dividends
            totals["net_trade_cents"] -= h["fill"] * cents(h["transaction_price"] or 0)
            totals["bought"] += max(0, h["fill"])
            totals["sold"] += max(0, -h["fill"])
            row = {
                "session": s["id"],
                "condition": s["config"]["treatment"],
                "trader": name,
                "persona": s["persona_assignment"][name],
                "period": h["period"],
                "side": h["side"],
                "submitted_quantity": d["quantity"],
                "admitted_quantity": h["accepted_quantity"],
                "limit_price": h["limit_cents"] / 100,
                "signed_fill": h["fill"],
                "execution_price": h["transaction_price"] if h["fill"] else None,
                "opening_cash": opening_cash / 100,
                "opening_shares": opening_shares,
                "closing_cash_before_redemption": cash / 100,
                "closing_shares_before_redemption": shares,
                "interest": interest / 100,
                "dividend_income": dividends / 100,
                "wealth_at_fundamental": (cash + shares * 1400) / 100,
                **{
                    k: d[k]
                    for k in ("forecast_0", "forecast_2", "forecast_5", "forecast_10")
                },
                "rejection": h["rejection"],
                "rationale": d["rationale"],
            }
            s["rows"].append(row)
        assert cash + 1400 * shares == account["cash_cents"]
        s["traders"].append(
            {
                "session": s["id"],
                "condition": s["config"]["treatment"],
                "trader": name,
                "persona": s["persona_assignment"][name],
                "buy_orders": totals["buy"],
                "sell_orders": totals["sell"],
                "holds": totals["hold"],
                "shares_bought": totals["bought"],
                "shares_sold": totals["sold"],
                "final_shares_before_redemption": shares,
                "net_trade_cash": totals["net_trade_cents"] / 100,
                "interest_income": totals["interest_cents"] / 100,
                "dividend_income": totals["dividends_cents"] / 100,
                "redemption_income": 14 * shares,
                "final_wealth": account["cash_cents"] / 100,
                "difference_from_no_trade": account["cash_cents"] / 100
                - s["no_trade_wealth"],
            }
        )
    s["rows"].sort(key=lambda r: (r["period"], r["trader"]))
    for period in s["tape"]:
        t = period["period"]
        rows = [r for r in s["rows"] if r["period"] == t]
        names = sorted(s["accounts"])
        random.Random(f"{s['config']['seed']}:priority:{t}").shuffle(names)
        rank = {name: i for i, name in enumerate(names)}
        bids, asks = [], []
        for row in rows:
            if row["side"] not in ("buy", "sell"):
                continue
            target = bids if row["side"] == "buy" else asks
            target.extend(
                (cents(row["limit_price"]), rank[row["trader"]], row["trader"])
                for _ in range(row["admitted_quantity"])
            )
        bids.sort(key=lambda r: (-r[0], r[1]))
        asks.sort(key=lambda r: (r[0], r[1]))
        matched = []
        for bid, ask in zip(bids, asks):
            if bid[0] < ask[0]:
                break
            matched.append((bid, ask))
        assert len(matched) == period["volume"]
        fills = Counter()
        for unit, (bid, ask) in enumerate(matched, 1):
            fills[bid[2]] += 1
            fills[ask[2]] -= 1
            s["trades"].append(
                {
                    "session": s["id"],
                    "condition": s["config"]["treatment"],
                    "period": t,
                    "unit": unit,
                    "buyer": bid[2],
                    "buyer_persona": s["persona_assignment"][bid[2]],
                    "seller": ask[2],
                    "seller_persona": s["persona_assignment"][ask[2]],
                    "quantity": 1,
                    "price": period["price"],
                    "bid_limit": bid[0] / 100,
                    "ask_limit": ask[0] / 100,
                }
            )
        assert all(fills[r["trader"]] == r["signed_fill"] for r in rows)
        best_bid, best_ask = (
            (bids[0][0] / 100 if bids else None),
            (asks[0][0] / 100 if asks else None),
        )
        reason = (
            "traded"
            if matched
            else "no active orders"
            if not bids and not asks
            else "no bids"
            if not bids
            else "no offers"
            if not asks
            else "non-crossing quotes"
        )
        s["books"].append(
            {
                "period": t,
                "bid_units": [b[0] / 100 for b in bids],
                "ask_units": [a[0] / 100 for a in asks],
                "best_bid": best_bid,
                "best_ask": best_ask,
                "reason": reason,
                "volume": len(matched),
                "price": period["price"],
            }
        )
    return s


def make_figures(sessions, output):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    import numpy as np

    figures = {}
    colors = {"buy": "#087e8b", "sell": "#ce6c2b", "hold": "#e0e5e8"}

    def save(fig, name):
        fig.savefig(
            output / f"{name}.png", dpi=170, bbox_inches="tight", pad_inches=0.15
        )
        fig.savefig(output / f"{name}.pdf", bbox_inches="tight", pad_inches=0.15)
        fig.savefig(output / f"{name}.svg", bbox_inches="tight", pad_inches=0.15)
        plt.close(fig)
        figures[name] = base64.b64encode((output / f"{name}.png").read_bytes()).decode()

    fig, axes = plt.subplots(
        len(sessions),
        1,
        figsize=(12, 3.5 * len(sessions)),
        squeeze=False,
        layout="constrained",
    )
    for ax, s in zip(axes[:, 0], sessions):
        names = sorted(
            s["accounts"], key=lambda name: (s["persona_assignment"][name], name)
        )
        matrix = np.zeros((len(names), s["config"]["periods"]))
        codes = {"hold": 0, "buy": 1, "sell": 2}
        for row in s["rows"]:
            matrix[names.index(row["trader"]), row["period"] - 1] = codes[row["side"]]
        ax.imshow(
            matrix,
            aspect="auto",
            interpolation="nearest",
            cmap=ListedColormap([colors["hold"], colors["buy"], colors["sell"]]),
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
                    fontsize=9,
                    fontweight="bold",
                    color="white",
                    bbox={"facecolor": "#162c38", "pad": 1, "edgecolor": "none"},
                )
        ax.set_yticks(
            range(12),
            [
                f"{n.removeprefix('trader-')} · {s['persona_assignment'][n]}"
                for n in names
            ],
            fontsize=9,
        )
        ax.set_xticks(range(0, 30), range(1, 31), fontsize=8)
        ax.set_title(s["config"]["treatment"], loc="left", fontweight="bold")
        ax.set_xlabel("Market period · numbers identify filled shares")
    fig.suptitle(
        "Every trader decision: buy (teal), sell (orange), hold (gray)", fontsize=16
    )
    save(fig, "all-decisions")

    fig, axes = plt.subplots(
        len(sessions),
        2,
        figsize=(12, 3.3 * len(sessions)),
        squeeze=False,
        layout="constrained",
    )
    for (left, right), s in zip(axes, sessions):
        for side in ("buy", "sell"):
            rows = [r for r in s["rows"] if r["side"] == side]
            # Seat-dependent offsets expose coincident quotes; x centers remain periods.
            left.scatter(
                [r["period"] + (int(r["trader"][-2:]) - 5.5) * 0.045 for r in rows],
                [r["limit_price"] for r in rows],
                s=[12 + 6 * r["admitted_quantity"] for r in rows],
                alpha=0.5,
                color=colors[side],
                marker="^" if side == "buy" else "v",
                label=side,
            )
        for t in s["tape"]:
            if t["price"] is not None:
                left.scatter(
                    t["period"],
                    t["price"],
                    marker="*",
                    s=160,
                    color="#151d26",
                    zorder=10,
                )
        left.axhline(14, color="#7b858b", linestyle="--", linewidth=1)
        left.set(xlim=(0.4, 30.6), ylabel="Submitted limit ($)", xlabel="Market period")
        left.set_title(s["config"]["treatment"] + " · all buy/sell quotes", loc="left")
        left.legend(frameon=False)
        xs = list(range(1, 31))
        for side in ("buy", "sell"):
            right.plot(
                xs,
                [
                    sum(
                        r["admitted_quantity"]
                        for r in s["rows"]
                        if r["period"] == t and r["side"] == side
                    )
                    for t in xs
                ],
                color=colors[side],
                label=f"{side} units",
            )
        right.plot(
            xs,
            [t["volume"] for t in s["tape"]],
            color="#151d26",
            label="traded units",
            linewidth=2,
        )
        right.set(
            xlim=(0.5, 30.5),
            ylim=(0, None),
            ylabel="Shares in period orders",
            xlabel="Market period",
        )
        right.legend(frameon=False)
    fig.suptitle("Offers to trade are not transactions", fontsize=16)
    save(fig, "orders-and-liquidity")

    trade_session = next((s for s in sessions if s["trades"]), None)
    if trade_session:
        chosen = [b for b in trade_session["books"] if b["volume"]]
        no_match = next(
            (b for b in trade_session["books"] if b["reason"] == "non-crossing quotes"),
            None,
        )
        if no_match:
            chosen.append(no_match)
        fig, axes = plt.subplots(
            1,
            len(chosen),
            figsize=(5 * len(chosen), 4),
            squeeze=False,
            layout="constrained",
        )
        for ax, b in zip(axes[0], chosen):
            for values, side in [(b["bid_units"], "buy"), (b["ask_units"], "sell")]:
                if values:
                    ax.step(
                        range(1, len(values) + 1),
                        values,
                        where="mid",
                        marker=".",
                        color=colors[side],
                        label=side,
                    )
            if b["volume"]:
                ax.axhline(
                    b["price"],
                    color="#172c37",
                    linestyle="--",
                    label=f"cleared ${b['price']:.2f}",
                )
                ax.axvspan(0.5, b["volume"] + 0.5, color="#a9cbd0", alpha=0.25)
            ax.set_title(
                f"{trade_session['config']['treatment']} · period {b['period']}",
                loc="left",
            )
            ax.set(xlabel="Cumulative unit rank", ylabel="Limit price ($)")
            ax.legend(frameon=False, fontsize=8)
        save(fig, "clearing-detail")

    fig, axes = plt.subplots(
        len(sessions),
        2,
        figsize=(12, 3.5 * len(sessions)),
        squeeze=False,
        layout="constrained",
    )
    for (left, right), s in zip(axes, sessions):
        palette = plt.get_cmap("tab20")
        for i, trader in enumerate(s["traders"]):
            rows = [r for r in s["rows"] if r["trader"] == trader["trader"]]
            label = trader["trader"][-2:] + " " + trader["persona"]
            left.step(
                [0] + [r["period"] for r in rows],
                [4] + [r["closing_shares_before_redemption"] for r in rows],
                where="post",
                color=palette(i),
                label=label,
                alpha=0.85,
            )
            right.plot(
                [0] + [r["period"] for r in rows],
                [156] + [r["wealth_at_fundamental"] for r in rows],
                color=palette(i),
                alpha=0.8,
            )
        left.set(
            title=s["config"]["treatment"] + " · inventories",
            xlabel="Period (before terminal redemption)",
            ylabel="Shares",
            xlim=(0, 30),
            ylim=(0, 8),
        )
        right.set(
            title="Cash + $14 × shares",
            xlabel="Market period",
            ylabel="Wealth at fundamental value ($)",
            xlim=(0, 30),
        )
        if any(t["shares_bought"] or t["shares_sold"] for t in s["traders"]):
            left.legend(fontsize=6, ncol=3, frameon=False)
        else:
            left.text(
                0.5,
                0.85,
                "All 12 traders overlap",
                transform=left.transAxes,
                ha="center",
                color="#64747c",
            )
    save(fig, "portfolios")

    fig, axes = plt.subplots(
        1,
        len(sessions),
        figsize=(5 * len(sessions), 5.8),
        squeeze=False,
        layout="constrained",
    )
    for ax, s in zip(axes[0], sessions):
        traders = sorted(s["traders"], key=lambda t: t["final_wealth"])
        ax.barh(
            range(12),
            [t["difference_from_no_trade"] for t in traders],
            color=[
                "#087e8b" if t["difference_from_no_trade"] >= 0 else "#ce6c2b"
                for t in traders
            ],
        )
        ax.set_yticks(
            range(12),
            [t["trader"][-2:] + " " + t["persona"] for t in traders],
            fontsize=8,
        )
        ax.axvline(0, color="#69777d", linewidth=1)
        ax.set(
            title=s["config"]["treatment"],
            xlabel="Final wealth minus same-dividend no-trade path ($)",
            xlim=(-14, 14),
        )
    save(fig, "wealth-differences")

    fig, axes = plt.subplots(
        len(sessions),
        2,
        figsize=(12, 3.5 * len(sessions)),
        squeeze=False,
        layout="constrained",
    )
    for (left, right), s in zip(axes, sessions):
        for trader in s["traders"]:
            rows = [r for r in s["rows"] if r["trader"] == trader["trader"]]
            left.plot(
                [r["period"] for r in rows],
                [r["forecast_0"] for r in rows],
                alpha=0.65,
                linewidth=0.9,
            )
        for side, color, marker in [
            ("buy", colors["buy"], "^"),
            ("sell", colors["sell"], "v"),
        ]:
            rows = [r for r in s["rows"] if r["side"] == side]
            right.scatter(
                [r["forecast_0"] for r in rows],
                [r["limit_price"] for r in rows],
                color=color,
                marker=marker,
                alpha=0.4,
                s=18,
                label=side,
            )
        for ax in (left, right):
            ax.axhline(14, color="#77858b", linestyle="--", linewidth=1)
        left.set(
            title=s["config"]["treatment"] + " · each trader’s current forecast",
            xlabel="Period",
            ylabel="Forecast ($)",
        )
        right.set(
            title="Quotes versus current forecasts",
            xlabel="Forecast ($)",
            ylabel="Limit price ($)",
        )
        right.legend(frameon=False)
    save(fig, "individual-beliefs")
    return figures


def table(headers, rows, cls=""):
    return (
        '<div class="table-scroll"><table class="'
        + cls
        + '"><thead><tr>'
        + "".join("<th>" + html.escape(str(x)) + "</th>" for x in headers)
        + "</tr></thead><tbody>"
        + "".join(
            "<tr>"
            + "".join("<td>" + html.escape(str(x)) + "</td>" for x in row)
            + "</tr>"
            for row in rows
        )
        + "</tbody></table></div>"
    )


def build_full_report(runs, output):
    # Retain the smaller overview and its exports as an independent entry point.
    build_report(runs, output)
    (output / "overview.html").write_text((output / "index.html").read_text())
    paths = sorted(runs.glob("*/summary.json"))
    sessions = [reconstruct(p.parent) for p in paths]
    preferred = {"baseline": 0, "BT+OC+PC": 1, "evolved": 2}
    sessions.sort(key=lambda s: (preferred.get(s["config"]["treatment"], 3), s["id"]))
    audits = [audit_session(p.parent) for p in paths]
    figures = make_figures(sessions, output)
    all_rows = [r for s in sessions for r in s["rows"]]
    trades = [r for s in sessions for r in s["trades"]]
    traders = [r for s in sessions for r in s["traders"]]
    write_csv(output / "all-orders.csv", all_rows)
    write_csv(output / "executed-trades.csv", trades)
    write_csv(output / "trader-accounts.csv", traders)
    write_csv(
        output / "market-books.csv",
        [
            {
                "session": s["id"],
                **{k: v for k, v in b.items() if k not in ("bid_units", "ask_units")},
            }
            for s in sessions
            for b in s["books"]
        ],
    )
    source = json.loads((ROOT / "source.json").read_text())
    manifest = {
        str(p.parent.name): {
            "summary_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "orders_sha256": hashlib.sha256(
                (p.parent / "orders.json").read_bytes()
            ).hexdigest(),
        }
        for p in paths
    }
    report_data = {
        "sessions": sessions,
        "source": source,
        "audit": audits,
        "provenance": manifest,
    }
    (output / "trading-data.json").write_text(json.dumps(report_data, indent=2) + "\n")
    (output / "report-audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    overview = base64.b64encode((output / "markets.png").read_bytes()).decode()

    def figure(name, caption):
        return f'<figure><img alt="{html.escape(caption, quote=True)}" src="data:image/png;base64,{figures[name]}"><figcaption>{html.escape(caption)} <a href="{name}.pdf">PDF figure</a> · <a href="{name}.svg">SVG</a></figcaption></figure>'

    condition_rows = []
    reasons = []
    persona_rows = []
    for s in sessions:
        counts = Counter(r["side"] for r in s["rows"])
        condition_rows.append(
            [
                s["config"]["treatment"],
                len(s["rows"]),
                counts["buy"],
                counts["sell"],
                counts["hold"],
                s["metrics"]["volume"],
                s["metrics"]["trading_periods"],
                s["quantity_reductions"],
            ]
        )
        counts = Counter(b["reason"] for b in s["books"])
        reasons.append(
            [
                s["config"]["treatment"],
                *[
                    counts[x]
                    for x in [
                        "traded",
                        "no active orders",
                        "no bids",
                        "no offers",
                        "non-crossing quotes",
                    ]
                ],
            ]
        )
        for persona in sorted(set(s["persona_assignment"].values())):
            rows = [r for r in s["rows"] if r["persona"] == persona]
            c = Counter(r["side"] for r in rows)
            persona_rows.append(
                [
                    s["config"]["treatment"],
                    persona,
                    len(rows),
                    c["buy"],
                    c["sell"],
                    c["hold"],
                    f"{statistics.mean(r['forecast_0'] for r in rows):.2f}",
                    sum(abs(r["signed_fill"]) for r in rows),
                ]
            )
    trade_table = table(
        [
            "Period",
            "Buyer",
            "Buyer type",
            "Seller",
            "Seller type",
            "Shares",
            "Price",
            "Bid",
            "Ask",
        ],
        [
            [
                r["period"],
                r["buyer"],
                r["buyer_persona"],
                r["seller"],
                r["seller_persona"],
                1,
                f"${r['price']:.2f}",
                f"${r['bid_limit']:.2f}",
                f"${r['ask_limit']:.2f}",
            ]
            for r in trades
        ],
    )
    wealth_table = table(
        [
            "Condition",
            "Trader",
            "Type",
            "Bought",
            "Sold",
            "Shares redeemed",
            "Interest",
            "Dividends",
            "Final wealth",
            "Δ no trade",
        ],
        [
            [
                t["condition"],
                t["trader"],
                t["persona"],
                t["shares_bought"],
                t["shares_sold"],
                t["final_shares_before_redemption"],
                f"${t['interest_income']:.2f}",
                f"${t['dividend_income']:.2f}",
                f"${t['final_wealth']:.2f}",
                f"${t['difference_from_no_trade']:+.2f}",
            ]
            for t in traders
        ],
    )
    quotes = []
    # Fixed, identified examples, rather than an unreported search for persuasive quotes.
    for condition, name, period in [
        ("baseline", "trader-00", 1),
        ("BT+OC+PC", "trader-00", 1),
        ("evolved", "trader-00", 1),
    ]:
        row = next(
            (
                r
                for r in all_rows
                if r["condition"] == condition
                and r["trader"] == name
                and r["period"] == period
            ),
            None,
        )
        if row:
            quotes.append(
                f"<blockquote>{html.escape(row['rationale'])}<footer>{html.escape(condition)} · {name} · period {period} · {html.escape(row['persona'])}</footer></blockquote>"
            )
    persona_texts = "".join(
        f"<details><summary>{html.escape(name)}</summary><pre>{html.escape(text)}</pre></details>"
        for name, text in [
            ("BT", THEORY["BT"]),
            ("OC", THEORY["OC"]),
            ("PC", THEORY["PC"]),
            *[
                (n, (ROOT / "personas" / f"{n}.txt").read_text())
                for n in ["trend_reader", "noise", "reversion_rider"]
            ],
        ]
    )
    cost = sum(s["cost"] for s in sessions)
    template = (ROOT / "report_assets" / "full_report.html").read_text()
    substitutions = {
        "DATE": date.today().isoformat(),
        "COST": f"${cost:.2f}",
        "DECISIONS": f"{len(all_rows):,}",
        "SESSIONS": str(len(sessions)),
        "SHARES": str(len(trades)),
        "OVERVIEW": overview,
        "CONDITION_TABLE": table(
            [
                "Condition",
                "Decisions",
                "Buy",
                "Sell",
                "Hold",
                "Shares traded",
                "Traded periods",
                "Size capped",
            ],
            condition_rows,
        ),
        "REASON_TABLE": table(
            [
                "Condition",
                "Traded",
                "No active orders",
                "No bids",
                "No offers",
                "Quotes do not cross",
            ],
            reasons,
        ),
        "PERSONA_TABLE": table(
            [
                "Condition",
                "Persona",
                "Decisions",
                "Buy",
                "Sell",
                "Hold",
                "Mean forecast now",
                "Filled units¹",
            ],
            persona_rows,
        ),
        "TRADE_TABLE": trade_table,
        "WEALTH_TABLE": wealth_table,
        "HEATMAP": figure(
            "all-decisions",
            "All 36 traders and all 30 periods. Color records submitted direction; numbered dark cells show actual fills. No jitter or random behavior is added to decisions.",
        ),
        "LIQUIDITY": figure(
            "orders-and-liquidity",
            "Every active-side quote is shown, including quotes with zero admitted quantity. Marker area reflects admitted size. Horizontal offsets separate traders within a period; black stars mark executed prices. Each side’s unit counts count repeated orders anew each period.",
        ),
        "CLEARING": figure(
            "clearing-detail",
            "The two trading periods and the first two-sided period without crossing quotes. Sorted admitted unit orders determine volume; the marginal midpoint determines the common price.",
        )
        if "clearing-detail" in figures
        else "",
        "PORTFOLIOS": figure(
            "portfolios",
            "Inventory and wealth paths for every trader. Shares are shown before terminal redemption; wealth uses the known $14 fundamental value, not a fabricated transaction price. Overlapping lines reflect identical paths.",
        ),
        "WEALTH": figure(
            "wealth-differences",
            "Terminal wealth compared with retaining the initial four shares throughout the same realized dividend sequence. This is an accounting counterfactual, not an estimated causal treatment effect.",
        ),
        "BELIEFS": figure(
            "individual-beliefs",
            "Individual current-period forecasts and all buy/sell limit quotes. Points can overlap. These are forecasts and offers, not transactions.",
        ),
        "QUOTES": "".join(quotes),
        "PERSONAS": persona_texts,
        "SOURCE_HASH": source["sha256"],
        "DATA": json.dumps(report_data, separators=(",", ":")).replace("<", "\\u003c"),
        "CSS": (ROOT / "report_assets" / "full_report.css").read_text(),
        "JS": (ROOT / "report_assets" / "full_report.js").read_text(),
    }
    for key, value in substitutions.items():
        template = template.replace("@@" + key + "@@", value)
    (output / "index.html").write_text(template)
    return output / "index.html"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build_full_report(args.runs, args.output))
