"""Generate Markdown, HTML, and CSV results for the mug design replication."""

from __future__ import annotations

import csv
from html import escape
import json
from math import erfc, sqrt
from pathlib import Path
import statistics


ROOT = Path("examples/automated_social_science/runs/mug-original-replication")
ATTACHMENTS = [
    "no emotional attachment",
    "slight emotional attachment",
    "moderate emotional attachment",
    "high emotional attachment",
    "extreme emotional attachment",
]


def fmt(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}"


def load_rows():
    observations = []
    for path in sorted((ROOT / "cells").glob("*/observation.json")):
        observation = json.loads(path.read_text())
        observation["path"] = path
        observations.append(observation)
    return observations


def coefficient_rows(results):
    equation = results["fit"]["equations"][0]
    benchmark = results["paper_benchmark"]
    rows = []
    for name in ["buyer_budget", "seller_minimum_price", "seller_attachment"]:
        beta = equation["coefficients"][name]
        se = equation["standard_errors"][name]
        p = erfc(abs(beta / se) / sqrt(2)) if se else 0.0
        paper_beta = benchmark["coefficients"][name]
        rows.append((name, beta, se, p, paper_beta, beta - paper_beta))
    return rows


def transcript_text(observation):
    transcript = json.loads((observation["path"].parent / "transcript.json").read_text())
    return "\n".join(f"{item['role'].title()}: {item['text']}" for item in transcript)


def markdown(results, observations):
    values = [item["values"] for item in observations]
    attachment_rates = []
    for level in ATTACHMENTS:
        subset = [row["deal_occurred"] for row in values if row["seller_attachment"] == level]
        attachment_rates.append((level, sum(subset) / len(subset), len(subset)))
    coefficient_table = coefficient_rows(results)
    deals = [item for item in observations if item["values"]["deal_occurred"] == 1]
    no_deals = [item for item in observations if item["values"]["deal_occurred"] == 0]
    representative = []
    if deals:
        representative.append(("Representative deal", min(deals, key=lambda item: item["transcript_version"])))
    if no_deals:
        representative.append(("Representative no-deal", min(no_deals, key=lambda item: item["transcript_version"])))

    lines = [
        "# Recreating the mug-bargaining experiment with EDSL",
        "",
        "## Executive summary",
        "",
        f"We recreated the published **405-cell factorial design** using **{results['model']['name']}** "
        f"through the EDSL causal/conversation adapter. The agents reached a deal in "
        f"**{results['outcomes']['deals']} of 405 conversations ({results['outcomes']['deal_rate']:.1%})**, "
        f"compared with **{results['paper_benchmark']['deal_rate']:.0%}** in Manning, Zhu, and Horton (2024).",
        "",
        "This is a **design replication with a contemporary model**, not an exact computational reproduction: "
        "the paper used GPT-4 in April 2024, and its historical model snapshot and complete prompt stack are not pinned here.",
        "",
        "## Experimental design",
        "",
        "- 9 buyer budgets: $3, $6, $7, $8, $10, $13, $18, $20, $25",
        "- 9 seller minimum acceptable prices: $3, $5, $7, $8, $10, $13, $18, $20, $25",
        "- 5 seller-attachment levels, from none to extreme",
        "- One negotiation per treatment combination; buyer and seller alternate",
        "- A hidden model judge checks for a natural endpoint after every utterance; hard cap of 20",
        "- A measurement-only coordinator codes whether the transcript contains explicit price agreement",
        "- Prespecified linear-probability SCM with HC3 standard errors",
        "",
        "## Main estimates",
        "",
        "| Cause | EDSL estimate | HC3 SE | Approx. p | Paper estimate | Difference |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, beta, se, p, paper_beta, difference in coefficient_table:
        lines.append(f"| `{name}` | {fmt(beta)} | {fmt(se)} | {fmt(p)} | {fmt(paper_beta)} | {fmt(difference)} |")
    lines += [
        "",
        "Coefficients are percentage-point changes in deal probability per one-unit increase when multiplied by 100. "
        "Attachment is encoded 0–4 in its declared ordinal order.",
        "",
        "## Deal rates by seller attachment",
        "",
        "| Attachment | Deal rate | N |",
        "|---|---:|---:|",
    ]
    lines.extend(f"| {level} | {rate:.1%} | {n} |" for level, rate, n in attachment_rates)
    lines += [
        "",
        "## Conversation diagnostics",
        "",
        f"Conversations averaged **{results['outcomes']['mean_turns']:.2f} utterances** "
        f"(range {results['outcomes']['minimum_turns']}–{results['outcomes']['maximum_turns']}).",
        "",
        "## What this exercise established",
        "",
        "The experiment can be represented end-to-end as serializable research objects: SCM, treatment design, "
        "participant assignments, conversation protocol, measurement manifest, transcript state, and frozen estimator. "
        "Private treatment information remained role-scoped, while the coordinator received the completed transcript only for measurement.",
        "",
        "The replication also exposed a useful execution distinction: measurement-only roles must belong to the compiled experiment "
        "without being inserted into the speaking protocol. The general runner now supports that distinction.",
        "",
        "## Limitations",
        "",
        "- A single negotiation was run per cell, matching the published 405-run design but leaving cell-level model randomness unaveraged.",
        "- Provider/model version, prompts, and inference defaults differ from the historical experiment.",
        "- The binary outcome is itself model-coded; future robustness checks should add deterministic transcript coding and multiple judges.",
        "- Statistical significance describes this simulated population and does not establish transportability to human bargaining.",
        "",
        "## Example transcripts",
        "",
    ]
    for title, observation in representative:
        v = observation["values"]
        lines += [
            f"### {title}",
            "",
            f"Treatments: buyer budget ${v['buyer_budget']}; seller minimum ${v['seller_minimum_price']}; "
            f"attachment: {v['seller_attachment']}. Outcome: {v['deal_occurred']}.",
            "",
            "```text",
            transcript_text(observation),
            "```",
            "",
        ]
    lines += [
        "## Reproducibility artifacts",
        "",
        "The run directory contains the serialized experiment, conversation, analysis plan, benchmark, one SQLite transcript store "
        "and provenance record per cell, the fitted SCM, and a flat analysis CSV.",
    ]
    return "\n".join(lines) + "\n"


def html_page(md: str) -> str:
    # Purposefully tiny Markdown renderer for the known generated report structure.
    import re
    output = []
    in_code = False
    in_list = False
    table = []

    def inline(text):
        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
        return text

    def flush_table():
        nonlocal table
        if not table:
            return
        headers = [cell.strip() for cell in table[0].strip("|").split("|")]
        output.append("<table><thead><tr>" + "".join(f"<th>{inline(x)}</th>" for x in headers) + "</tr></thead><tbody>")
        for row in table[2:]:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            output.append("<tr>" + "".join(f"<td>{inline(x)}</td>" for x in cells) + "</tr>")
        output.append("</tbody></table>")
        table = []

    for line in md.splitlines():
        if line == "```text":
            flush_table(); in_code = True; output.append("<pre>"); continue
        if line == "```" and in_code:
            in_code = False; output.append("</pre>"); continue
        if in_code:
            output.append(escape(line)); continue
        if line.startswith("|"):
            table.append(line); continue
        flush_table()
        if line.startswith("- "):
            if not in_list: output.append("<ul>"); in_list = True
            output.append(f"<li>{inline(line[2:])}</li>"); continue
        if in_list: output.append("</ul>"); in_list = False
        if line.startswith("# "): output.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("## "): output.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("### "): output.append(f"<h3>{inline(line[4:])}</h3>")
        elif line: output.append(f"<p>{inline(line)}</p>")
    flush_table()
    if in_list: output.append("</ul>")
    body = "\n".join(output)
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mug-bargaining experiment replication</title><style>
:root{{--ink:#172033;--muted:#637087;--accent:#167354;--paper:#fff;--wash:#f2f6f4;--line:#d9e2df}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--wash);color:var(--ink);font:17px/1.62 system-ui,sans-serif}}
main{{max-width:980px;margin:48px auto;background:var(--paper);padding:56px 72px;border:1px solid var(--line);border-radius:18px;box-shadow:0 16px 50px #17203312}}
h1{{font-size:2.5rem;line-height:1.1}} h2{{margin-top:2.4em;border-top:1px solid var(--line);padding-top:1em;color:var(--accent)}}
h3{{margin-top:2em}} table{{width:100%;border-collapse:collapse;margin:1.2em 0;display:block;overflow:auto}}
th,td{{padding:.65em .8em;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}} th{{background:#eaf5f0}}
code{{background:#eef2f6;padding:.1em .3em;border-radius:4px}} pre{{white-space:pre-wrap;background:#111827;color:#e5e7eb;padding:18px;border-radius:10px;overflow:auto}}
p,li{{max-width:78ch}} @media(max-width:700px){{main{{margin:0;padding:28px 20px;border:0;border-radius:0}}}}
</style></head><body><main>{body}</main></body></html>"""


def main():
    results = json.loads((ROOT / "results.json").read_text())
    observations = load_rows()
    if len(observations) != 405:
        raise SystemExit(f"expected 405 observations, found {len(observations)}")
    rows = [item["values"] | {"cell_id": item["cell_id"], "turns": item["transcript_version"]} for item in observations]
    with (ROOT / "observations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    report = markdown(results, observations)
    (ROOT / "report.md").write_text(report)
    (ROOT / "report.html").write_text(html_page(report))
    print(json.dumps({"status": "ok", "observations": len(observations), "report": str(ROOT / "report.html")}))


if __name__ == "__main__":
    main()
