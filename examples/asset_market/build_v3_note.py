"""Build v3 report inputs from frozen run artifacts; never make model calls."""

import ast
from collections import Counter
import difflib
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).parent
RUN = ROOT / "runs/gpt5-v3-30-typed"
OUT = ROOT / "v3-note"
BASE = ROOT / "full-market-note/code"


def build():
    for folder in ("code", "code/baseline", "data", "figures"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    original = json.loads((RUN / "source-manifest.json").read_text())
    recovery = json.loads((RUN / "recovery.json").read_text())
    sources = {
        "experiment": (
            "examples/asset_market/typed_market_experiment.py",
            "typed_market_experiment.py",
        ),
        "rules": ("edsl/sharedstate/market_rules.py", "market_rules.py"),
        "records": ("edsl/sharedstate/market_records.py", "market_records.py"),
        "market": ("edsl/sharedstate/call_market.py", "call_market.py"),
        "executor": ("edsl/workflows/experiment.py", "workflow_experiment.py"),
    }
    baselines = {
        "experiment": BASE / "full_market_experiment.py",
        "market": BASE / "edsl/call_market.py",
        "executor": BASE / "edsl/workflow_experiment.py",
    }
    highlight_defs = []
    changes = {}
    for key, (name, filename) in sources.items():
        source = RUN / "source" / name
        digest = original[name]
        if key == "executor":
            source = RUN / "recovery-before-retry/workflow_experiment_after_fix.py"
            digest = recovery["runtime_after_sha256"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, name
        shutil.copyfile(source, OUT / "code" / filename)
        lines = source.read_text().splitlines()
        old = baselines[key].read_text().splitlines() if key in baselines else []
        if key in baselines:
            shutil.copyfile(baselines[key], OUT / "code/baseline" / filename)
        changed = []
        for tag, _, _, first, last in difflib.SequenceMatcher(
            a=old, b=lines, autojunk=False
        ).get_opcodes():
            if tag in ("replace", "insert"):
                changed.extend(range(first + 1, last + 1))
        changes[filename] = {
            "baseline": str(baselines.get(key, "new file")),
            "highlighted_lines": changed,
            "sha256": digest,
        }
        highlight_defs.extend(
            r"\expandafter\def\csname changed:" + key + ":" + str(n) + r"\endcsname{1}"
            for n in changed
        )
        (OUT / "code" / f"{filename}.diff").write_text(
            "\n".join(
                difflib.unified_diff(
                    old,
                    lines,
                    fromfile=f"previous/{filename}",
                    tofile=f"v3/{filename}",
                    lineterm="",
                )
            )
            + "\n"
        )
    shutil.copyfile(
        RUN / "source/edsl/workflows/experiment.py",
        OUT / "code/workflow_experiment_before_retry.py",
    )
    shutil.copyfile(RUN / "recover_null_result.py", OUT / "code/recover_null_result.py")
    verification = json.loads((RUN / "verification.json").read_text())
    for filename in ("report_full_market.py", "compare_full_markets.py"):
        source = ROOT / filename
        assert (
            hashlib.sha256(source.read_bytes()).hexdigest()
            == verification["report_sources"][f"examples/asset_market/{filename}"]
        )
        shutil.copyfile(source, OUT / "code" / filename)
    shutil.copyfile(ROOT / "TYPED_MARKET.md", OUT / "code/TYPED_MARKET.md")
    shutil.copyfile(__file__, OUT / "code/build_v3_note.py")
    (OUT / "highlights.tex").write_text("\n".join(highlight_defs) + "\n")
    (OUT / "data/code-changes.json").write_text(json.dumps(changes, indent=2) + "\n")
    for name in (
        "experiment.json",
        "rules.json",
        "treatment.json",
        "market.json",
        "responses.json",
        "completion.json",
        "run-plan.json",
        "source-manifest.json",
        "inference-batches.jsonl",
        "recovery.json",
        "verification.json",
    ):
        shutil.copyfile(RUN / name, OUT / "data" / name)
    for name in (
        "summary.json",
        "decisions.csv",
        "periods.csv",
        "terminal-wealth.csv",
        "comparison.json",
    ):
        shutil.copyfile(RUN / "report" / name, OUT / "data" / name)
    with gzip.GzipFile(
        filename=str(OUT / "data/model-calls.jsonl.gz"), mode="wb", mtime=0
    ) as f:
        f.write((RUN / "model-calls.jsonl").read_bytes())
    shutil.copyfile(ROOT / "source.json", OUT / "data/source-paper.json")
    markets = [
        json.loads((ROOT / "runs" / name / "market.json").read_text())
        for name in ("gpt5-full-30-native", "gpt5-v2-30-typed", "gpt5-v3-30-typed")
    ]
    summaries = [
        json.loads((ROOT / "runs" / name / "report/summary.json").read_text())
        for name in ("gpt5-full-30-native", "gpt5-v2-30-typed", "gpt5-v3-30-typed")
    ]
    for i in (0, 1):
        (OUT / "data" / f"prior-{i + 1}-market.json").write_text(
            json.dumps(markets[i], indent=2) + "\n"
        )
        (OUT / "data" / f"prior-{i + 1}-summary.json").write_text(
            json.dumps(summaries[i], indent=2) + "\n"
        )
    m = markets[2]
    summary = summaries[2]
    assert summary["audit"]["passed"] and summary["decisions"] == 360
    calls = [
        json.loads(x) for x in (RUN / "model-calls.jsonl").read_text().splitlines()
    ]
    assert (
        len(calls) == 361
        and sum(isinstance(c["result"]["answer"].get("decision"), dict) for c in calls)
        == 360
    )
    from .typed_market_experiment import RULES, build_agents, COMMON
    from .full_market_experiment import PERSONAS as OLD_PERSONAS

    agents = build_agents()
    types = {
        a.name: next(k for k, v in OLD_PERSONAS.items() if a.instruction == COMMON + v)
        for a in agents
        if a.traits["role"] == "trader"
    }
    assert all(abs(RULES.fundamental_value(t) - 14) < 1e-8 for t in range(1, 31))
    passive = 10000
    for row in m["tape"]:
        passive += (passive * 5 + 50) // 100 + round(row["dividend"] * 100) * 4
    passive += 5600
    eligible = sum(r["period"] + h > 30 for r in m["order_log"] for h in (2, 5, 10))
    violations = [
        {
            "trader": r["trader"],
            "period": r["period"],
            "horizon": h,
            "forecast": r["decision"][f"forecast_{h}"],
        }
        for r in m["order_log"]
        for h in (2, 5, 10)
        if r["period"] + h > 30 and r["decision"][f"forecast_{h}"] != 14
    ]
    wealth = [
        {
            "trader": n,
            "type": types[n],
            "cash": a["cash_cents"] / 100,
            "difference": (a["cash_cents"] - passive) / 100,
            "redeemed": a["redeemed_shares"],
        }
        for n, a in sorted(m["accounts"].items())
    ]
    diag = {
        "side_counts": dict(Counter(r["side"] for r in m["order_log"])),
        "passive_cash": passive / 100,
        "wealth": wealth,
        "forecast_opportunities": eligible,
        "violations": violations,
        "vwap": sum(
            r["price"] * r["volume"] for r in m["tape"] if r["price"] is not None
        )
        / summary["volume"],
        "capped_orders": sum(
            r["side"] != "hold" and r["accepted_quantity"] < r["decision"]["quantity"]
            for r in m["order_log"]
        ),
        "rejected_orders": sum(r["rejection"] is not None for r in m["order_log"]),
    }
    (OUT / "data/diagnostics.json").write_text(json.dumps(diag, indent=2) + "\n")
    # Actual elicited rationales cited in the main text.
    examples = [
        r
        for r in m["order_log"]
        if (r["trader"], r["period"])
        in {("trader-05", 5), ("trader-00", 25), ("trader-00", 29), ("trader-11", 29)}
    ]
    (OUT / "data/discussed-decisions.json").write_text(
        json.dumps(examples, indent=2) + "\n"
    )
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/v3-note-mpl")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    plt.rcParams.update(
        {"font.size": 10, "axes.spines.top": False, "axes.spines.right": False}
    )
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 6),
        sharex=True,
        layout="constrained",
        gridspec_kw={"height_ratios": [2, 1]},
    )
    labels = ["Original full run", "V2", "V3"]
    colors = ["#b0b9c7", "#8a98ae", "#147e77"]
    for market, label, color in zip(markets, labels, colors):
        axes[0].plot(
            range(1, 31),
            [r["price"] if r["price"] is not None else np.nan for r in market["tape"]],
            "o-",
            label=label,
            color=color,
            markersize=3,
            linewidth=1.7,
        )
    axes[0].axhline(14, ls="--", color="#333333", label="Fundamental value: $14")
    axes[0].scatter(
        [30.8],
        [14],
        marker="D",
        s=35,
        color="#333333",
        label="Redemption (not a trade)",
    )
    axes[0].set(ylabel="Transaction price ($)", ylim=(12.8, 33))
    axes[0].legend(ncol=3, fontsize=8, loc="upper left")
    axes[1].bar(range(1, 31), [r["volume"] for r in m["tape"]], color="#147e77")
    axes[1].set(
        xlabel="Round", ylabel="V3 shares traded", xticks=range(1, 31), xlim=(0.5, 31.5)
    )
    for ext in ("pdf", "png"):
        fig.savefig(OUT / "figures" / f"prices.{ext}", dpi=180)
    plt.close(fig)
    names = sorted(m["accounts"])
    matrix = np.zeros((12, 30))
    for r in m["order_log"]:
        matrix[names.index(r["trader"]), r["period"] - 1] = {
            "hold": 0,
            "buy": 1,
            "sell": 2,
        }[r["side"]]
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    palette = ["#edf0f2", "#c6e2f5", "#f1cbbd"]
    ax.imshow(
        matrix,
        cmap=ListedColormap(palette),
        vmin=0,
        vmax=2,
        aspect="auto",
        extent=[0.5, 30.5, 11.5, -0.5],
    )
    for i, n in enumerate(names):
        for h in m["accounts"][n]["history"]:
            if h["fill"]:
                ax.text(
                    h["period"],
                    i,
                    f"{h['fill']:+d}",
                    ha="center",
                    va="center",
                    fontsize=7,
                )
    ax.set(
        xticks=range(1, 31),
        yticks=range(12),
        yticklabels=[f"{n[-2:]} {types[n]}" for n in names],
        xlabel="Round",
        ylabel="Trader / archetype",
    )
    ax.legend(
        handles=[
            Patch(color=c, label=label)
            for c, label in zip(palette, ["Hold", "Buy", "Sell"])
        ],
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.13),
    )
    for ext in ("pdf", "png"):
        fig.savefig(OUT / "figures" / f"decisions.{ext}", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
    vals = [r["difference"] for r in wealth]
    ax.barh(range(12), vals, color=["#147e77" if v >= 0 else "#bd624d" for v in vals])
    ax.set(
        yticks=range(12),
        yticklabels=[f"{n[-2:]} {types[n]}" for n in names],
        xlabel="Final cash minus passive holding ($)",
        xlim=(-470, 210),
    )
    ax.invert_yaxis()
    ax.axvline(0, color="#333", lw=0.7)
    for i, v in enumerate(vals):
        ax.text(
            v + (5 if v >= 0 else -5),
            i,
            f"{v:+.2f}",
            ha="left" if v >= 0 else "right",
            va="center",
            fontsize=8,
        )
    for ext in ("pdf", "png"):
        fig.savefig(OUT / "figures" / f"wealth.{ext}", dpi=180)
    plt.close(fig)
    table = [
        r"\begin{tabular}{@{}llrrr@{}}\toprule Trader & Type & Final cash (\$) & Difference (\$) & Redeemed\\\midrule"
    ]
    table.extend(
        f"{r['trader'][-2:]} & {r['type']} & {r['cash']:.2f} & {r['difference']:+.2f} & {r['redeemed']} \\\\"
        for r in wealth
    )
    table.append(r"\bottomrule\end{tabular}")
    (OUT / "wealth-table.tex").write_text("\n".join(table) + "\n")
    # Full files, broken only at meaningful source boundaries. Every line is printed.
    sections = [
        (
            "experiment",
            "Complete typed experiment",
            "The executed authoring file includes all six personas inline. Green lines differ from the standalone experiment in the previous report.",
            [
                (1, "Configuration and trader treatment"),
                (101, "Complete persona prompts"),
                (167, "Questions generated from rules"),
                (222, "Agents, market, and execution plan"),
                (263, "Thirty-round workflow"),
                (334, "Command-line entry point"),
            ],
        ),
        (
            "rules",
            "Validated economic rules",
            "This is a new file; all its lines are highlighted. Configuration objects reject unknown fields and invalid nested values when constructed.",
            [
                (1, "Base model, alternatives, and income objects"),
                (131, "Market rules and cross-field validation"),
                (192, "Valuation and economic instructions"),
                (260, "Serialization and legacy authoring compatibility"),
                (329, "Validation of the existing wire format"),
            ],
        ),
        (
            "records",
            "Decision and market-record contracts",
            "This is a new file. The decision schema generates QuestionDict fields, while runtime validation applies stronger economic and structural constraints.",
            [
                (1, "Order intent and rejection semantics"),
                (77, "Shared decision schema"),
                (136, "Admission, fills, accounts, and round records"),
            ],
        ),
        (
            "market",
            "Native market integration",
            "Green lines show changes from the earlier dictionary-based implementation. Clearing economics remain version 1; records and rules now pass through typed validation.",
            [
                (1, "Factory and serialized machine"),
                (104, "Order admission"),
                (143, "Settlement"),
            ],
        ),
        (
            "executor",
            "Complete workflow executor after the retry fix",
            "The baseline is the executor printed in the previous report. The highlighted null-response guard was added after the failed final-round batch; both runtime versions are in the bundle.",
            [
                (1, "Bundle and serialization"),
                (128, "Execution and recovery"),
                (259, "Paired EDSL jobs and response admission"),
            ],
        ),
    ]
    # Resolve function boundaries from the frozen files instead of relying on edit-sensitive constants.
    for key, title, intro, groups in sections:
        filename = sources[key][1]
        text = (OUT / "code" / filename).read_text()
        lines = text.splitlines()
        if key == "market":
            nodes = {
                n.name: n.lineno
                for n in ast.parse(text).body
                if isinstance(n, ast.FunctionDef)
            }
            groups = [
                (1, "Factory and serialized machine"),
                (nodes["submit_order"], "Order admission"),
                (nodes["settle_market"], "Settlement"),
            ]
        if key == "executor":
            cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef))
            methods = {
                n.name: min([n.lineno] + [d.lineno for d in n.decorator_list])
                for n in cls.body
                if isinstance(n, ast.FunctionDef)
            }
            groups = [
                (1, "Bundle and serialization"),
                (methods["run"], "Execution and recovery"),
                (methods["_batch_survey"], "Paired EDSL jobs and response admission"),
            ]
        output = [
            r"\clearpage" if key == "experiment" else r"\Needspace{16\baselineskip}",
            r"\section{" + title + "}",
            intro,
            r"\par\textit{Source:} \path{code/" + filename + "}.",
            r"\def\activefile{" + key + "}",
        ]
        covered = []
        for i, (start, heading) in enumerate(groups):
            end = groups[i + 1][0] - 1 if i + 1 < len(groups) else len(lines)
            covered.extend(range(start, end + 1))
            output += [
                r"\Needspace{6\baselineskip}",
                r"\subsection{" + heading + "}",
                r"\lstinputlisting[firstline="
                + str(start)
                + ",lastline="
                + str(end)
                + ",firstnumber="
                + str(start)
                + "]{code/"
                + filename
                + "}",
            ]
        assert covered == list(range(1, len(lines) + 1))
        (OUT / f"appendix-{key}.tex").write_text("\n".join(output) + "\n")
    manifest = {
        str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("code", "data", "figures")
        for p in sorted((OUT / folder).rglob("*"))
        if p.is_file()
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(OUT),
                "lines_printed": sum(
                    len((OUT / "code" / f).read_text().splitlines())
                    for _, f in sources.values()
                ),
                "diagnostics": diag,
            }
        )
    )


if __name__ == "__main__":
    build()
