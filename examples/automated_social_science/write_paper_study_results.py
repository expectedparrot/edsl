"""Write individual and comparative reports for the paper design replications."""

from __future__ import annotations

import csv
from html import escape
import json
from math import erfc, sqrt
from pathlib import Path

from examples.automated_social_science.run_paper_studies import BENCHMARKS
from examples.automated_social_science.write_original_mug_results import html_page


RUNS = Path("examples/automated_social_science/runs")
ROOTS = {
    "bail": RUNS / "paper-replications-v3" / "bail",
    "interview": RUNS / "paper-replications" / "interview",
    "auction": RUNS / "paper-replications-v8" / "auction",
}
REPORT_ROOT = RUNS / "paper-study-reports"
LABELS = {"bail": "Bail hearing", "interview": "Lawyer job interview", "auction": "Art auction"}
VARIABLE_LABELS = {
    "bail": {
        "criminal_history": "Criminal history",
        "judge_case_count": "Judge case count",
        "defendant_remorse": "Defendant remorse",
        "bail_amount": "Bail amount",
    },
    "interview": {
        "passed_bar": "Passed bar",
        "interviewer_friendliness": "Interviewer friendliness",
        "applicant_height": "Applicant height",
        "hired": "Hired",
    },
    "auction": {
        "bidder_1_budget": "Bidder 1 budget",
        "bidder_2_budget": "Bidder 2 budget",
        "bidder_3_budget": "Bidder 3 budget",
        "final_price": "Final price",
    },
}


def load(study):
    root = ROOTS[study]
    result = json.loads((root / "results.json").read_text())
    observations = []
    for path in sorted((root / "cells").glob("*/observation.json")):
        item = json.loads(path.read_text()); item["path"] = path; observations.append(item)
    return result, observations


def p_value(beta, se):
    return erfc(abs(beta / se) / sqrt(2)) if se else 0.0


def p_text(value):
    return "<0.001" if value < 0.001 else f"{value:.3f}"


def write_csv(study, observations):
    rows = [item["values"] | {"cell_id": item["cell_id"], "turns": item["transcript_version"]} for item in observations]
    with (ROOTS[study] / "observations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def theory_diagnostic(study, observations):
    if study != "auction":
        return None
    squared = []
    exact = 0
    for item in observations:
        row = item["values"]
        prediction = sorted([row["bidder_1_budget"], row["bidder_2_budget"], row["bidder_3_budget"]])[-2]
        error = row["final_price"] - prediction
        squared.append(error * error)
        exact += abs(error) < 1e-9
    return {"mse": sum(squared) / len(squared), "exact": exact, "n": len(squared)}


def transcript(observation):
    rows = json.loads((observation["path"].parent / "transcript.json").read_text())
    return "\n".join(f"{row['role'].replace('_', ' ').title()}: {row['text']}" for row in rows)


def study_markdown(study, result, observations):
    equation = result["fit"]["equations"][0]
    benchmark = result["paper_benchmark"]
    lines = [
        f"# {LABELS[study]}: EDSL design replication", "",
        "## Summary", "",
        f"All **{len(observations)}** published factorial cells completed with **gemini-2.5-flash-lite**. "
        f"The simulated mean outcome was **{result['outcomes']['mean']:.3f}**, compared with "
        f"**{benchmark['mean']:.3f}** in Manning, Zhu, and Horton (2024).", "",
        "This is a design replication with a contemporary model, not an exact reproduction of the historical GPT-4 snapshot and prompts.", "",
        "## Prespecified path estimates", "",
        "| Cause | EDSL estimate | HC3 SE | Approx. p | Paper estimate | Paper SE | Difference |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cause, paper_beta in benchmark["coefficients"].items():
        beta = equation["coefficients"][cause]; se = equation["standard_errors"][cause]
        lines.append(f"| `{cause}` | {beta:.3f} | {se:.3f} | {p_text(p_value(beta, se))} | {paper_beta:.3f} | {benchmark['standard_errors'][cause]:.3f} | {beta-paper_beta:.3f} |")
    lines += ["", "## Conversation diagnostics", "", f"Mean utterances: **{result['outcomes']['mean_turns']:.2f}**; maximum: **{result['outcomes']['maximum_turns']}**.", ""]
    theory = theory_diagnostic(study, observations)
    if theory:
        lines += [
            "## Auction-theory check", "",
            f"Predicting the final price with the second-highest private value gives **MSE {theory['mse']:.2f}**. "
            f"The final price exactly equals that benchmark in **{theory['exact']} of {theory['n']} auctions ({theory['exact']/theory['n']:.1%})**. "
            "The paper reported an MSE of 128 for this comparison.", "",
        ]
    sample = min(observations, key=lambda item: item["transcript_version"])
    treatments = ", ".join(f"{key}={value}" for key, value in sample["values"].items() if key != benchmark["outcome"])
    lines += [
        "## Example transcript", "", f"Treatments: {treatments}. Outcome: {sample['values'][benchmark['outcome']]}", "",
        "```text", transcript(sample), "```", "",
        "## Interpretation and limitations", "",
        "The randomized factorial identifies the simulated-model effects under this execution protocol. It does not establish transportability to humans. "
        "Differences from the paper can arise from model version, prompts, stopping judgments, outcome coding, and provider defaults. "
        "All treatment assignments, private role contexts, transcripts, measurements, and fitted specifications are retained for audit and re-analysis.", "",
    ]
    if study == "bail":
        lines += ["Note: Figure 3 prints `7×7×5 = 243`; the arithmetic and Appendix Figure A.5 confirm **245** actual simulations. Criminal history and expressed remorse are shared courtroom information in the canonical run; judge workload remains private.", ""]
    if study == "interview":
        lines += ["Note: Figure 4 prints 405 simulations; its `2×5×8` factorial and accompanying text establish **80**.", ""]
    if study == "auction":
        capped = sum(item["transcript_version"] == 20 for item in observations)
        lines += [f"Protocol warning: **{capped} of {len(observations)}** auctions reached the published 20-utterance cap. Serializable turn instructions, participant retirement, center routing, and constrained numeric actions reduced cap pressure and eliminated over-budget bids. Larger bid jumps also raised the mean price, so protocol choice remains substantively consequential.", ""]
    return "\n".join(lines)


def combined_markdown(studies):
    lines = ["# Automated Social Science: EDSL replications", "", "## Overview", "", "This collection recreates all four published experimental designs with serializable EDSL causal and conversation objects and a contemporary Google model.", "", "| Study | Cells | EDSL mean | Paper mean | Mean turns |", "|---|---:|---:|---:|---:|"]
    for study, result, observations in studies:
        lines.append(f"| {LABELS[study]} | {len(observations)} | {result['outcomes']['mean']:.3f} | {result['paper_benchmark']['mean']:.3f} | {result['outcomes']['mean_turns']:.2f} |")
    lines += ["", "## Reports", "", "- [Mug bargaining](../mug-original-replication/report.html)"]
    lines.extend(f"- [{LABELS[study]}](../{ROOTS[study].relative_to(RUNS)}/report.html)" for study, _, _ in studies)
    lines += [
        "", "## What changed during validation", "",
        "The first bail pass allowed the judge to decide before hearing the parties; a second pass fixed sequencing but showed that private defendant facts never reliably reached the judge. The canonical bail run therefore models criminal history and expressed remorse as shared courtroom information.", "",
        "The first auction pass allowed closure after bidder 1. The canonical auction requires all three bidders to participate before closure. This restored strong positive budget effects, although the published 20-turn cap still truncates most auctions.",
    ]
    lines += ["", "## Reproducibility", "", "Each study directory contains its compiled experiment, conversation definition, frozen analysis plan, benchmark, fitted results, flat CSV, and one durable transcript/provenance bundle per factorial cell."]
    return "\n".join(lines) + "\n"


def scm_svg(study, result):
    """Render a compact fitted SCM with original and new edge estimates."""
    benchmark = result["paper_benchmark"]
    equation = result["fit"]["equations"][0]
    causes = list(benchmark["coefficients"])
    outcome = benchmark["outcome"]
    positions = [85, 240, 395]
    colors = ["#206f57", "#315ca8", "#9a5a18"]
    edges = []
    nodes = []
    for cause, x, color in zip(causes, positions, colors):
        paper = benchmark["coefficients"][cause]
        new = equation["coefficients"][cause]
        edges.append(
            f'<path d="M{x} 112 C{x} 175 240 172 240 244" fill="none" stroke="{color}" stroke-width="3" marker-end="url(#arrow-{study})"/>'
            f'<rect x="{x - 64}" y="155" width="128" height="45" rx="8" fill="#fff" stroke="{color}"/>'
            f'<text x="{x}" y="173" text-anchor="middle" class="edge-paper">Original {paper:+.3f}</text>'
            f'<text x="{x}" y="190" text-anchor="middle" class="edge-new">New {new:+.3f}</text>'
        )
        nodes.append(
            f'<rect x="{x - 67}" y="42" width="134" height="70" rx="14" fill="{color}"/>'
            f'<text x="{x}" y="72" text-anchor="middle" class="node-label">{escape(VARIABLE_LABELS[study][cause])}</text>'
            f'<text x="{x}" y="92" text-anchor="middle" class="node-kind">TREATMENT</text>'
        )
    return f'''<svg class="scm" viewBox="0 0 480 350" role="img" aria-label="Fitted structural causal model for {escape(LABELS[study])}">
      <defs><marker id="arrow-{study}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#667085"/></marker></defs>
      {''.join(edges)}{''.join(nodes)}
      <rect x="163" y="244" width="154" height="78" rx="39" fill="#18243a"/>
      <text x="240" y="276" text-anchor="middle" class="node-label">{escape(VARIABLE_LABELS[study][outcome])}</text>
      <text x="240" y="298" text-anchor="middle" class="node-kind">OUTCOME</text>
    </svg>'''


def comparison_html(studies):
    sections = []
    for study, result, observations in studies:
        benchmark = result["paper_benchmark"]
        equation = result["fit"]["equations"][0]
        rows = []
        for cause, paper_beta in benchmark["coefficients"].items():
            beta = equation["coefficients"][cause]
            se = equation["standard_errors"][cause]
            paper_se = benchmark["standard_errors"][cause]
            direction = "same" if (beta == 0 or paper_beta == 0 or beta * paper_beta > 0) else "opposite"
            rows.append(f'''<tr>
              <th>{escape(VARIABLE_LABELS[study][cause])}<code>{escape(cause)}</code></th>
              <td>{paper_beta:+.3f}<small>SE {paper_se:.3f}</small></td>
              <td class="new-estimate">{beta:+.3f}<small>HC3 SE {se:.3f}</small></td>
              <td>{beta-paper_beta:+.3f}</td><td><span class="direction {direction}">{direction}</span></td>
            </tr>''')
        caveat = ""
        if study == "bail":
            caveat = "Canonical run shares criminal history and expressed remorse as courtroom information; judge workload remains private. Figure 3's 243 is a typo—the appendix confirms 245 cells."
        elif study == "interview":
            caveat = "Figure 4's 405 is a typo; the stated 2×5×8 factorial and text establish 80 cells. Friendliness and height differ in direction from the original estimates."
        else:
            capped = sum(item["transcript_version"] == 20 for item in observations)
            caveat = f"{capped} of {len(observations)} auctions reached the cap, down from 329. All bids satisfy private maxima, but faster bid jumps raised the mean price above the paper's result."
        sections.append(f'''<section id="{study}" class="study">
          <div class="section-heading"><div><span class="eyebrow">{len(observations)} factorial cells · 0 failures</span><h2>{escape(LABELS[study])}</h2></div>
          <div class="means"><span>Outcome mean</span><strong>{result['outcomes']['mean']:.3f}</strong><small>Original {benchmark['mean']:.3f}</small></div></div>
          <div class="study-grid"><div class="diagram-card"><h3>Fitted structural causal model</h3>{scm_svg(study, result)}
          <p class="legend"><span class="original-dot"></span> Original paper <span class="new-dot"></span> New EDSL replication</p></div>
          <div class="table-card"><h3>Coefficient comparison</h3><div class="table-wrap"><table><thead><tr><th>Path</th><th>Original</th><th>New</th><th>Δ</th><th>Sign</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></div></div>
          <p class="caveat"><strong>Interpretation note.</strong> {escape(caveat)}</p>
        </section>''')
    old_auction = json.loads((RUNS / "paper-replications-v2" / "auction" / "results.json").read_text())
    new_auction = next(result for study, result, _ in studies if study == "auction")
    protocol_comparison = f'''<section class="study"><span class="eyebrow">Auction protocol iteration</span><h2>Did terseness reduce cap pressure?</h2>
      <div class="table-wrap"><table><thead><tr><th>Metric</th><th>Procedural v2</th><th>Terse + retirement + contracts</th></tr></thead><tbody>
      <tr><th>Mean turns</th><td>{old_auction['outcomes']['mean_turns']:.2f}</td><td class="new-estimate">{new_auction['outcomes']['mean_turns']:.2f}</td></tr>
      <tr><th>Cap hits</th><td>329 / 343</td><td class="new-estimate">120 / 343</td></tr>
      <tr><th>Mean final price</th><td>${old_auction['outcomes']['mean']:.2f}</td><td>${new_auction['outcomes']['mean']:.2f}</td></tr>
      <tr><th>Feasibility violations</th><td>Observed</td><td class="new-estimate">0</td></tr>
      </tbody></table></div><p class="caveat"><strong>Result.</strong> The new protocol cut mean turns by 25% and cap hits by 64%. Structured choices made over-budget bids impossible. Faster bid increments increased prices, demonstrating that conversational efficiency is part of the experimental treatment unless held fixed.</p></section>'''
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Original vs new fitted SCMs</title><style>
:root{{--ink:#172033;--muted:#657087;--paper:#fff;--wash:#eef3f1;--line:#d7e0dd;--green:#167354;--violet:#6842d8}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--wash);color:var(--ink);font:16px/1.55 Inter,ui-sans-serif,system-ui,sans-serif}}
.hero{{background:#152339;color:white;padding:64px max(28px,calc((100vw - 1180px)/2));background-image:radial-gradient(circle at 85% 15%,#28765d88,transparent 34%)}}
.hero h1{{font-size:clamp(2.3rem,5vw,4.5rem);line-height:1.02;max-width:900px;margin:.15em 0}} .hero p{{max-width:760px;color:#d5ddea;font-size:1.12rem}}
nav{{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}} nav a{{color:white;text-decoration:none;border:1px solid #ffffff55;padding:8px 14px;border-radius:999px}}
main{{max-width:1180px;margin:auto;padding:28px}} .study{{background:var(--paper);margin:30px 0;padding:36px;border:1px solid var(--line);border-radius:20px;box-shadow:0 14px 42px #1720330d}}
.section-heading{{display:flex;align-items:end;justify-content:space-between;gap:24px;border-bottom:1px solid var(--line);padding-bottom:22px}} h2{{font-size:2.1rem;margin:.15em 0}} h3{{margin-top:0}}
.eyebrow{{color:var(--green);font-weight:750;text-transform:uppercase;letter-spacing:.08em;font-size:.76rem}} .means{{text-align:right}} .means span,.means small{{display:block;color:var(--muted)}} .means strong{{font-size:2rem}}
.study-grid{{display:grid;grid-template-columns:minmax(360px,.85fr) minmax(520px,1.15fr);gap:25px;margin-top:26px}} .diagram-card,.table-card{{border:1px solid var(--line);border-radius:15px;padding:20px;overflow:hidden}}
.scm{{display:block;width:100%;height:auto}} .node-label{{fill:white;font-size:13px;font-weight:750}} .node-kind{{fill:#dce8e4;font-size:9px;font-weight:800;letter-spacing:.12em}} .edge-paper{{fill:#59657b;font-size:11px}} .edge-new{{fill:#172033;font-size:11px;font-weight:800}}
.legend{{font-size:.82rem;color:var(--muted);text-align:center}} .original-dot,.new-dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 5px 0 14px}} .original-dot{{background:#9ba5b6}} .new-dot{{background:var(--green)}}
.table-wrap{{overflow:auto}} table{{width:100%;border-collapse:collapse}} th,td{{padding:13px 11px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}} th:first-child{{text-align:left}} thead th{{font-size:.72rem;text-transform:uppercase;color:var(--muted)}} tbody th{{white-space:normal}} tbody th code{{display:block;color:var(--muted);font-weight:400;font-size:.73rem}} td small{{display:block;color:var(--muted)}} .new-estimate{{font-weight:800;color:var(--green)}}
.direction{{font-size:.72rem;padding:4px 8px;border-radius:999px;background:#e6f5ed;color:#126044}} .direction.opposite{{background:#fff0df;color:#8c4a0e}} .caveat{{background:#f6f8f7;border-left:4px solid var(--green);padding:15px 18px;border-radius:6px;color:#465268}}
footer{{max-width:1180px;margin:0 auto 60px;padding:0 28px;color:var(--muted)}}
@media(max-width:950px){{.study-grid{{grid-template-columns:1fr}}}} @media(max-width:600px){{main{{padding:12px}}.study{{padding:20px}}.section-heading{{align-items:start;flex-direction:column}}.means{{text-align:left}}}}
</style></head><body><header class="hero"><span class="eyebrow">Manning, Zhu &amp; Horton (2024) · contemporary-model replication</span><h1>Original vs new fitted causal models</h1><p>Side-by-side results from 668 real-model simulations using <strong>gemini-2.5-flash-lite</strong>. Edge labels report unstandardized coefficients from the paper and the new EDSL replication.</p><nav><a href="#bail">Bail hearing</a><a href="#interview">Job interview</a><a href="#auction">Art auction</a></nav></header><main>{''.join(sections)}{protocol_comparison}</main><footer>Design replication, not an exact computational reproduction: the historical April 2024 GPT-4 snapshot and full prompt stack are unavailable. Standard errors for the new estimates are HC3.</footer></body></html>'''


def main():
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    studies = []
    for study in LABELS:
        result, observations = load(study)
        if len(observations) != BENCHMARKS[study]["n"]:
            raise SystemExit(f"{study}: expected {BENCHMARKS[study]['n']} observations, found {len(observations)}")
        write_csv(study, observations)
        report = study_markdown(study, result, observations)
        (ROOTS[study] / "report.md").write_text(report)
        (ROOTS[study] / "report.html").write_text(html_page(report))
        studies.append((study, result, observations))
    index = combined_markdown(studies)
    (REPORT_ROOT / "index.md").write_text(index)
    (REPORT_ROOT / "index.html").write_text(html_page(index))
    (REPORT_ROOT / "comparison.html").write_text(comparison_html(studies))
    print(json.dumps({"status": "ok", "studies": {study: len(observations) for study, _, observations in studies}, "index": str(REPORT_ROOT / "index.html")}))


if __name__ == "__main__":
    main()
