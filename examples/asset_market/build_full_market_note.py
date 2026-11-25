"""Build the full-market LaTeX report's data, figures, and complete code listings.

Reads the completed run; makes no model calls. Run from the repository root:
    python -m examples.asset_market.build_full_market_note
"""

import ast
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-full-note-mpl")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

from . import full_market_experiment as source
from .report_full_market import build as audit_and_report

ROOT = Path(__file__).parent
RUN = ROOT / "runs/gpt5-full-30-native"
OUT = ROOT / "full-market-note"


def verified_source(name, digest):
    """Prefer matching live code; otherwise use the verified execution snapshot.

    Later library refactors must not replace the code attributed to this run.
    """
    snapshots = {
        "edsl/sharedstate/call_market.py": OUT / "code/edsl/call_market.py",
        "edsl/workflows/experiment.py": OUT / "code/edsl/workflow_experiment.py",
        "edsl/jobs/assignment_plan.py": OUT / "code/edsl/assignment_plan.py",
    }
    candidates = [Path(name)]
    if name in snapshots:
        candidates.append(snapshots[name])
    for path in candidates:
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            return path
    raise ValueError(f"No verified executed source snapshot for {name}")


def canonical(value):
    ids = {}

    def visit(item):
        if isinstance(item, dict):
            return {k: visit(v) for k, v in sorted(item.items())}
        if isinstance(item, list):
            return [visit(v) for v in item]
        if isinstance(item, str) and re.fullmatch(
            r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", item
        ):
            return ids.setdefault(item, f"identifier-{len(ids)}")
        return item

    return visit(value)


def write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build():
    audit_and_report(RUN)
    for folder in ["data", "figures", "code", "code/historical", "code/edsl"]:
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    market = json.loads((RUN / "market.json").read_text())
    spec = json.loads((RUN / "experiment.json").read_text())
    summary = json.loads((RUN / "report/summary.json").read_text())
    new = source.build(created_at=spec["metadata"]["created_at"]).to_dict()
    assert canonical(new) == canonical(spec), (
        "Standalone source differs from saved experiment"
    )
    transition = json.loads((RUN / "batch-runner-transition.json").read_text())
    assert (
        hashlib.sha256((RUN / "experiment.json").read_bytes()).hexdigest()
        == transition["original_spec_sha256"]
    )
    executed_sources = {
        name: verified_source(name, digest)
        for name, digest in transition["updated_sources"].items()
    }
    original_hashes = json.loads((RUN / "source-manifest.json").read_text())
    # The serial runtime was replaced during the run; its recorded hash remains
    # in source-manifest.json. The executed batched runtime is checked above.
    for name, digest in original_hashes.items():
        if name != "edsl/workflows/experiment.py":
            executed_sources[name] = verified_source(name, digest)
    check = {
        "complete_specification_matches": True,
        "normalized_generated_uuids": True,
        "created_at_taken_from_archive": True,
        "original_specification_hash_unchanged": True,
        "executed_batched_sources_match": True,
        "new_model_calls": 0,
    }
    (OUT / "data/authoring-check.json").write_text(json.dumps(check, indent=2) + "\n")
    for name in [
        "experiment.json",
        "market.json",
        "responses.json",
        "completion.json",
        "source-manifest.json",
        "batch-runner-transition.json",
        "inference-batches.jsonl",
    ]:
        shutil.copyfile(RUN / name, OUT / "data" / name)
    for name in ["summary.json", "decisions.csv", "periods.csv", "terminal-wealth.csv"]:
        shutil.copyfile(RUN / "report" / name, OUT / "data" / name)
    shutil.copyfile(ROOT / "source.json", OUT / "data/source-paper.json")
    shutil.copyfile(
        ROOT / "full_market_experiment.py", OUT / "code/full_market_experiment.py"
    )
    for name in ["portable.py", "run_full_market.py"]:
        shutil.copyfile(ROOT / name, OUT / "code/historical" / name)
    for source_name, destination in [
        ("edsl/workflows/experiment.py", "workflow_experiment.py"),
        ("edsl/sharedstate/call_market.py", "call_market.py"),
        ("edsl/jobs/assignment_plan.py", "assignment_plan.py"),
    ]:
        origin = executed_sources[source_name]
        target = OUT / "code/edsl" / destination
        if origin.resolve() != target.resolve():
            shutil.copyfile(origin, target)
    for name in ["report_full_market.py", "build_full_market_note.py"]:
        shutil.copyfile(ROOT / name, OUT / "code" / name)
    with gzip.open(OUT / "data/model-calls.jsonl.gz", "wb") as handle:
        handle.write((RUN / "model-calls.jsonl").read_bytes())
    batches = [
        json.loads(x)
        for x in (RUN / "inference-batches.jsonl").read_text().splitlines()
    ]
    example_job = next(r for r in batches if r["steps"] == ["orders-13"])
    shutil.copyfile(RUN / example_job["job_path"], OUT / "data/round-13-job.json")

    with (RUN / "report/decisions.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    personas = {
        a["name"]: next(
            k
            for k, v in source.PERSONAS.items()
            if a["instruction"] == source.COMMON + v
        )
        for a in spec["agents"]
        if a["traits"]["role"] == "trader"
    }
    names = sorted(market["accounts"])
    tape = market["tape"]
    periods = np.arange(1, 31)
    passive = 10000
    for row in tape:
        passive += (passive * 5 + 50) // 100 + round(row["dividend"] * 100) * 4
    passive += 5600
    wealth = [
        {
            "trader": n,
            "persona": personas[n],
            "terminal_cash": market["accounts"][n]["cash_cents"] / 100,
            "passive_cash": passive / 100,
            "difference_from_passive": (market["accounts"][n]["cash_cents"] - passive)
            / 100,
            "redeemed_shares": market["accounts"][n]["redeemed_shares"],
            "gross_traded_quantity": sum(
                abs(h["fill"]) for h in market["accounts"][n]["history"]
            ),
        }
        for n in names
    ]
    write_csv(OUT / "data/wealth-comparison.csv", wealth)
    violations, eligible = [], 0
    for row in market["order_log"]:
        for horizon in [2, 5, 10]:
            if row["period"] + horizon > 30:
                eligible += 1
                value = row["decision"][f"forecast_{horizon}"]
                if abs(value - 14) > 1e-8:
                    violations.append(
                        {
                            "trader": row["trader"],
                            "persona": personas[row["trader"]],
                            "period": row["period"],
                            "horizon": horizon,
                            "forecast": value,
                            "required": 14,
                        }
                    )
    write_csv(OUT / "data/terminal-forecast-violations.csv", violations)
    diagnostics = {
        "passive_terminal_cash": passive / 100,
        "forecast_opportunities_beyond_terminal": eligible,
        "noncompliant_forecasts": len(violations),
        "affected_decisions": len({(r["trader"], r["period"]) for r in violations}),
        "affected_traders": len({r["trader"] for r in violations}),
        "personas": personas,
        "terminal_cash_total": sum(r["terminal_cash"] for r in wealth),
        "vwap": sum(r["price"] * r["volume"] for r in tape if r["price"] is not None)
        / summary["volume"],
    }
    (OUT / "data/diagnostics.json").write_text(json.dumps(diagnostics, indent=2) + "\n")
    with sqlite3.connect(f"file:{RUN}/workflow.sqlite?mode=ro", uri=True) as db:
        ids = {
            i: (name, step)
            for i, name, step in db.execute(
                "select id,participant_id,step_name from workflow_items"
            )
        }
    calls = [
        json.loads(line)
        for line in (RUN / "model-calls.jsonl").read_text().splitlines()
    ]
    for trader, period in [("trader-11", 5), ("trader-00", 28)]:
        call = next(
            c for c in calls if ids[c["work_item_id"]] == (trader, f"orders-{period}")
        )
        for kind in ["system", "user"]:
            (OUT / f"data/{trader}-round-{period}-{kind}.txt").write_text(
                call["result"]["prompt"][f"decision_{kind}_prompt"]["text"] + "\n"
            )
        (OUT / f"data/{trader}-round-{period}-answer.json").write_text(
            json.dumps(call["result"]["answer"], indent=2) + "\n"
        )

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "pdf.fonttype": 42,
        }
    )
    blue, red, teal = "#246a9c", "#b94d3d", "#147e77"
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(7, 4.1),
        sharex=True,
        layout="constrained",
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax = axes[0]
    for side, aggregate, color, style in [
        ("buy", max, blue, "--"),
        ("sell", min, red, ":"),
    ]:
        values = [
            aggregate(
                (
                    float(r["price"])
                    for r in rows
                    if int(r["period"]) == t
                    and r["side"] == side
                    and int(r["accepted_quantity"]) > 0
                ),
                default=np.nan,
            )
            for t in periods
        ]
        ax.plot(
            periods,
            values,
            style,
            color=color,
            lw=1,
            label="Highest bid" if side == "buy" else "Lowest ask",
        )
    ax.plot(
        periods,
        [r["price"] if r["price"] is not None else np.nan for r in tape],
        "o-",
        color=teal,
        lw=1.7,
        ms=4,
        label="Transaction price",
    )
    ax.axhline(14, color="#657080", lw=1, label="Fundamental value / redemption: $14")
    ax.scatter([30], [14], marker="D", color="#657080", s=35, zorder=5)
    ax.annotate(
        "Redemption; no trade",
        xy=(30, 14),
        xytext=(20.5, 16.3),
        arrowprops={"arrowstyle": "->", "color": "#657080"},
        fontsize=8,
    )
    ax.set(ylabel="Dollars per share", ylim=(12.5, 36.2))
    ax.legend(loc="upper left", ncol=2, fontsize=8, frameon=False)
    axes[1].bar(periods, [r["volume"] for r in tape], color=teal)
    axes[1].set(
        xlabel="Round", ylabel="Shares traded", xticks=range(1, 31), xlim=(0.4, 30.6)
    )
    axes[1].tick_params(axis="x", labelsize=7)
    save_figure(fig, "prices")

    matrix = np.zeros((12, 30))
    for row in rows:
        matrix[names.index(row["trader"]), int(row["period"]) - 1] = {
            "hold": 0,
            "buy": 1,
            "sell": 2,
        }[row["side"]]
    fig, ax = plt.subplots(figsize=(7, 4.1), layout="constrained")
    ax.imshow(
        matrix,
        cmap=ListedColormap(["#eef0f3", "#d4e8f5", "#f3d6cf"]),
        vmin=0,
        vmax=2,
        aspect="auto",
    )
    for row in rows:
        fill = int(row["signed_fill"])
        if fill:
            ax.text(
                int(row["period"]) - 1,
                names.index(row["trader"]),
                f"{fill:+d}",
                ha="center",
                va="center",
                fontsize=6,
            )
    ax.set(
        xticks=range(30),
        xticklabels=periods,
        yticks=range(12),
        yticklabels=[f"{n[-2:]} {personas[n]}" for n in names],
        xlabel="Round",
        ylabel="Trader / archetype",
    )
    ax.tick_params(axis="x", labelsize=7)
    ax.legend(
        handles=[
            Patch(facecolor=c, label=s)
            for c, s in [("#d4e8f5", "Buy"), ("#f3d6cf", "Sell"), ("#eef0f3", "Hold")]
        ],
        loc="lower left",
        bbox_to_anchor=(0, 1.01),
        ncol=3,
        frameon=False,
    )
    save_figure(fig, "decisions")

    fig, ax = plt.subplots(figsize=(7, 3.9), layout="constrained")
    differences = [r["difference_from_passive"] for r in wealth]
    ax.barh(
        range(12), differences, color=[teal if x >= 0 else red for x in differences]
    )
    ax.axvline(0, color="#657080", lw=1)
    ax.set(
        yticks=range(12),
        yticklabels=[f"{n[-2:]} {personas[n]}" for n in names],
        xlabel="Final cash minus passive-holding benchmark ($)",
        xlim=(-490, 260),
    )
    ax.invert_yaxis()
    for i, value in enumerate(differences):
        ax.text(
            value + (5 if value >= 0 else -5),
            i,
            f"{value:+.2f}",
            va="center",
            ha="left" if value >= 0 else "right",
            fontsize=8,
        )
    save_figure(fig, "wealth")

    table = [
        r"\begin{center}\small",
        r"\begin{tabular}{@{}llrrr@{}}",
        r"\toprule",
        r"Trader & Type & Final cash (\$) & Difference (\$) & Redeemed \\",
        r"\midrule",
    ]
    for r in wealth:
        table.append(
            f"{r['trader'][-2:]} & {r['persona']} & {r['terminal_cash']:.2f} & {r['difference_from_passive']:+.2f} & {r['redeemed_shares']} "
            + r"\\"
        )
    table += [r"\bottomrule", r"\end{tabular}", r"\end{center}"]
    (OUT / "wealth-table.tex").write_text("\n".join(table) + "\n")
    make_listings()
    files = [
        f
        for folder in ["code", "data", "figures"]
        for f in sorted((OUT / folder).rglob("*"))
        if f.is_file()
    ]
    manifest = {
        str(f.relative_to(OUT)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in files
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(OUT),
                "check": check,
                "diagnostics": diagnostics,
            }
        )
    )


def save_figure(fig, name):
    fig.savefig(OUT / f"figures/{name}.pdf")
    fig.savefig(OUT / f"figures/{name}.png", dpi=180)
    plt.close(fig)


def make_listings():
    definitions = {}
    filename = "code/full_market_experiment.py"
    text = (OUT / filename).read_text()
    tree = ast.parse(text)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    common = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign) and n.targets[0].id == "COMMON"
    )
    boundaries = [
        common.lineno,
        funcs["question_text"].lineno,
        funcs["build_agents"].lineno,
        funcs["build_execution_plan"].lineno,
        funcs["build"].lineno,
        funcs["main"].lineno,
    ]
    starts = [1] + boundaries
    ends = [b - 1 for b in boundaries] + [len(text.splitlines())]
    for macro, start, end in zip(
        [
            "CodeSetup",
            "CodePersonas",
            "CodeQuestion",
            "CodeMarket",
            "CodePlan",
            "CodeWorkflow",
            "CodeRun",
        ],
        starts,
        ends,
    ):
        definitions[macro] = (filename, start, end)
    for filename, splits, macros in [
        (
            "code/edsl/workflow_experiment.py",
            ["run", "_batch_survey"],
            ["RuntimeBundle", "RuntimeRun", "RuntimeBatch"],
        ),
        (
            "code/edsl/call_market.py",
            ["cents", "settle_market"],
            ["MarketDefinition", "MarketAdmission", "MarketSettlement"],
        ),
    ]:
        text = (OUT / filename).read_text()
        tree = ast.parse(text)
        functions = {
            n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
        }
        boundaries = [
            min([functions[n].lineno] + [d.lineno for d in functions[n].decorator_list])
            for n in splits
        ]
        for macro, start, end in zip(
            macros,
            [1] + boundaries,
            [b - 1 for b in boundaries] + [len(text.splitlines())],
        ):
            definitions[macro] = (filename, start, end)
    (OUT / "code-listings.tex").write_text(
        "\n".join(
            rf"\newcommand{{\{name}}}{{\lstinputlisting[firstline={start},lastline={end},firstnumber={start}]{{{filename}}}}}"
            for name, (filename, start, end) in definitions.items()
        )
        + "\n"
    )


if __name__ == "__main__":
    build()
