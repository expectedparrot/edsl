"""Build publication figures and source snapshots from the audited saved pilot.

No model calls or market mutations. Run from the repository root:
    python -m examples.asset_market.build_latex_note
"""

import ast
import hashlib
import json
import os
import re
import shutil

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/asset-market-note-mpl")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

from .experiment import ROOT
from .gpt5_pilot_report import audit_prefix


def verify_portable(summary):
    """Check exact prompts and native settlement against the historical run."""
    from . import portable
    from .speculative_prompts import build_experiment as executed
    from edsl.sharedstate.dsl_runtime import default_runtime
    from edsl.workflows import WorkflowExperiment

    def canonical(value):
        identifiers = {}

        def visit(item):
            if isinstance(item, dict):
                return {k: visit(v) for k, v in sorted(item.items())}
            if isinstance(item, list):
                return [visit(v) for v in item]
            if isinstance(item, str) and re.fullmatch(
                r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", item
            ):
                return identifiers.setdefault(item, f"identifier-{len(identifiers)}")
            return item

        return visit(value)

    experiment = portable.build()
    saved = WorkflowExperiment.load(ROOT / "portable/experiment.json")
    assert canonical(experiment.to_dict()) == canonical(saved.to_dict())
    original, _, agents = executed(seed=portable.SEED)
    assert [a.to_dict() for a in agents] == [a.to_dict() for a in experiment.agents]
    for old, new in zip(original.steps, experiment.workflow.steps):
        if old.name.startswith("orders-"):
            assert canonical(old.survey.to_dict()) == canonical(new.survey.to_dict())
    machine = portable.build_market([n for n in summary["accounts"]])
    runtime = default_runtime()
    state = runtime.initial_state(machine)
    orders = json.loads((ROOT / "runs/gpt5-short-pilot/orders.json").read_text())
    for period in range(1, 18):
        for order in (o for o in orders if o["period"] == period):
            inputs = {k: order[k] for k in ["trader", "period", "decision"]}
            state = runtime.execute(machine, state, "submit", inputs).state
        state = runtime.execute(machine, state, "settle", {"period": period}).state
    assert state["tape"] == summary["tape"]
    assert state["accounts"] == summary["accounts"]
    assert state["order_log"] == orders
    return {"equivalent": True, "archived_specification_matches": True,
            "all_trader_instructions_and_questions_match": True,
            "decisions_replayed": len(orders), "settlements_replayed": 17,
            "saved_accounts_tape_and_orders_match": True, "model_calls": 0}


def build():
    out = ROOT / "latex-note"
    for name in ["figures", "code", "data"]:
        (out / name).mkdir(parents=True, exist_ok=True)
    summary, rows, calls, audit = audit_prefix(ROOT / "runs/gpt5-short-pilot")
    equivalence = verify_portable(summary)
    (out / "data/native-equivalence.json").write_text(
        json.dumps(equivalence, indent=2) + "\n"
    )
    for name, expected in summary["config"]["source_sha256"].items():
        src = ROOT / name
        assert hashlib.sha256(src.read_bytes()).hexdigest() == expected
        shutil.copyfile(src, out / "code" / name)
    # Present the complete native authoring file alongside frozen executed sources.
    source = ROOT / "portable.py"
    shutil.copyfile(source, out / "code" / source.name)
    tree = ast.parse(source.read_text())
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    snippets = {"WalkImports": (imports[0].lineno, imports[-1].end_lineno)}
    for macro, names in {
        "WalkSchema": ["SEED", "PERIODS", "COMPOSITION", "KEYS", "OVERPRICING_THRESHOLD"],
        "WalkPersonas": ["COMMON", "PERSONAS"],
        "WalkQuestion": ["question_text"],
        "WalkAgents": ["build_agents"],
        "WalkMarket": ["build_market"],
        "WalkPause": ["add_pause_rules"],
        "WalkPlan": ["build_execution_plan"],
        "WalkBuild": ["build"],
    }.items():
        nodes = [n for n in tree.body if getattr(n, "name", None) in names
                 or any(isinstance(t, ast.Name) and t.id in names
                        for t in getattr(n, "targets", []))]
        snippets[macro] = (min(n.lineno for n in nodes), max(n.end_lineno for n in nodes))
    (out / "walkthrough-listings.tex").write_text("\n".join(
        rf"\newcommand{{\{macro}}}{{\lstinputlisting[firstline={start},lastline={end},firstnumber={start}]{{code/portable.py}}}}"
        for macro, (start, end) in snippets.items()
    ) + "\n")
    for name in ["decisions.csv", "periods.csv", "summary.json"]:
        shutil.copyfile(ROOT / "gpt5-pilot-report" / name, out / "data" / name)
    shutil.copyfile(ROOT / "source.json", out / "data/source.json")
    shutil.copyfile(ROOT / "GPT5_SHORT_PILOT.md", out / "data/observation-plan.md")
    shutil.copyfile(ROOT / "runs/gpt5-short-pilot/archive-recovery.json", out / "data/archive-recovery.json")
    (out / "data/config.json").write_text(json.dumps(summary["config"], indent=2) + "\n")
    (out / "data/audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    call = next(c for c in calls if c["participant"] == "trader-00" and c["step"] == "orders-1")
    for kind in ["system", "user"]:
        (out / f"data/example-{kind}-prompt.txt").write_text(
            call["result"]["prompt"][f"decision_{kind}_prompt"]["text"] + "\n"
        )
    (out / "data/example-answer.json").write_text(json.dumps(call["result"]["answer"], indent=2) + "\n")
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.labelcolor": "#243448", "text.color": "#243448",
        "axes.titleweight": "bold", "pdf.fonttype": 42,
    })
    blue, red, teal = "#246a9c", "#b94d3d", "#147e77"
    tape = summary["tape"]
    ts = np.array([r["period"] for r in tape])
    prices = [r["price"] if r["price"] is not None else np.nan for r in tape]
    bids, asks = [], []
    for t in ts:
        active = [r for r in rows if r["period"] == t and r["admitted_quantity"] > 0]
        bids.append(max((r["price"] for r in active if r["side"] == "buy"), default=np.nan))
        asks.append(min((r["price"] for r in active if r["side"] == "sell"), default=np.nan))
    fig, axes = plt.subplots(2, 1, figsize=(6.6, 3.75), sharex=True,
                             gridspec_kw={"height_ratios": [3, 1]}, layout="constrained")
    ax = axes[0]
    ax.plot(ts, bids, color=blue, lw=1.5, ls="--", label="Highest admitted bid (quote)")
    ax.plot(ts, asks, color=red, marker="v", ls=":", label="Lowest admitted ask (quote)")
    ax.plot(ts, prices, color=teal, marker="o", lw=2.5, label="Actual clearing price", zorder=5)
    ax.axhline(14, color="#4d5966", lw=1, label="Fundamental value: $14")
    ax.axhline(17.5, color="#9a7c40", lw=1, ls=":")
    ax.text(1.2, 17.75, "Early-stop threshold: $17.50", fontsize=8, color="#806631")
    ax.text(5, 20.8, "No transactions in rounds 1–15", fontsize=9)
    ax.annotate("$17.53", (16, 17.53), xytext=(13.6, 18.6), fontsize=8,
                arrowprops={"arrowstyle": "-", "color": teal})
    ax.annotate("$17.67", (17, 17.67), xytext=(17.4, 18.6), fontsize=8,
                arrowprops={"arrowstyle": "-", "color": teal})
    ax.set(ylabel="Dollars per share", ylim=(12.8, 25), xlim=(.5, 18.5))
    ax.legend(loc="upper left", ncol=2, fontsize=7, frameon=False)
    axes[1].bar(ts, [r["volume"] for r in tape], color=teal, width=.65)
    axes[1].set(ylabel="Shares traded", xlabel="Round", yticks=[0, 10, 20], xticks=ts, ylim=(0, 24))
    for t, v in [(16, 2), (17, 19)]:
        axes[1].text(t, v + .8, str(v), ha="center", fontsize=8)
    fig.savefig(out / "figures/market.pdf")
    fig.savefig(out / "figures/market.png", dpi=180)
    plt.close(fig)

    names = sorted(summary["persona_assignment"])
    action = np.zeros((12, 17))
    for r in rows:
        action[names.index(r["trader"]), r["period"]-1] = {"hold": 0, "buy": 1, "sell": 2}[r["side"]]
    fig, ax = plt.subplots(figsize=(6.6, 3.5), layout="constrained")
    ax.imshow(action, cmap=ListedColormap(["#eef0f3", "#d4e8f5", "#f3d6cf"]), vmin=0, vmax=2, aspect="auto")
    for r in rows:
        if r["signed_fill"]:
            ax.text(r["period"]-1, names.index(r["trader"]), f'{r["signed_fill"]:+d}', ha="center", va="center", fontsize=8, fontweight="bold")
    ax.set(xticks=np.arange(17), xticklabels=ts, yticks=np.arange(12),
           yticklabels=[f'{n[-2:]}  {summary["persona_assignment"][n]}' for n in names], xlabel="Round", ylabel="Trader / archetype")
    ax.set_xticks(np.arange(-.5, 17, 1), minor=True)
    ax.set_yticks(np.arange(-.5, 12, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=1.1)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.legend(handles=[Patch(facecolor=c, label=s) for c, s in [("#d4e8f5", "Buy"), ("#f3d6cf", "Sell"), ("#eef0f3", "Hold")]],
              loc="lower left", bbox_to_anchor=(0, 1.01), ncol=3, frameon=False, borderaxespad=0)
    fig.savefig(out / "figures/decisions.pdf")
    fig.savefig(out / "figures/decisions.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.9), layout="constrained")
    for ax, t in zip(axes, [16, 17]):
        obs = [r for r in rows if r["period"] == t]
        b = sorted([r["price"] for r in obs if r["side"] == "buy" for _ in range(r["admitted_quantity"])], reverse=True)
        a = sorted([r["price"] for r in obs if r["side"] == "sell" for _ in range(r["admitted_quantity"])])
        ax.step(range(1, len(b)+1), b, where="mid", color=blue, label="Unit bids")
        ax.step(range(1, len(a)+1), a, where="mid", color=red, label="Unit asks")
        v, p = tape[t-1]["volume"], tape[t-1]["price"]
        ax.scatter([v, v], [b[v-1], a[v-1]], s=20, color=[blue, red], zorder=4)
        ax.axvline(v, color="#697585", ls=":", lw=1)
        ax.axhline(p, color=teal, ls="--", lw=1)
        ax.text(.97, .93, f'Price ${p:.2f}\nVolume {v}', transform=ax.transAxes, ha="right", va="top", fontsize=8,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": .9})
        ax.set(title=f"Round {t}", xlabel="Cumulative unit orders", ylabel="Limit price ($)", ylim=(11.5, 24), xlim=(.5, 26))
        ax.legend(loc="lower left", frameon=False, fontsize=8)
    fig.savefig(out / "figures/clearing.pdf")
    fig.savefig(out / "figures/clearing.png", dpi=180)
    plt.close(fig)
    manifest = {str(f.relative_to(out)): hashlib.sha256(f.read_bytes()).hexdigest()
                for folder in ["code", "data", "figures"] for f in sorted((out / folder).iterdir())}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "ok", "output": str(out), "audit": audit}))


if __name__ == "__main__":
    build()
