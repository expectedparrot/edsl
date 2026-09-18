"""Render saved judgment benchmark measurements without making inference calls."""

import argparse
import csv
import html
import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/edsl-benchmark-matplotlib")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(directory, comparison_run=None):
    summary = json.loads((directory / "summary.json").read_text())
    phases = {p["phase"]: p for p in summary["phases"]}
    comparison_note = "The matched comparison comes from the same run as the main load."
    if comparison_run is not None:
        replacement = json.loads((comparison_run / "summary.json").read_text())
        for field in ("model", "concurrency", "request_rate_cap", "comparison_inputs"):
            assert replacement["manifest"][field] == summary["manifest"][field]
        assert replacement["manifest"]["dataset"] == summary["manifest"]["dataset"]
        prior_batched = phases["matched_batched"]
        prior_single = phases["matched_single"]
        comparison_note = (
            f"The first comparison was interrupted by transport errors: "
            f"batched completed {prior_batched['completed_rows']}/100 inputs and "
            f"single-question completed {prior_single['completed_rows']}/100. "
            f"Those timings are not used for the speedup. The matched comparison "
            f"was repeated with the same dataset, model, prompts, concurrency, and pacing "
            f"in `{comparison_run.name}`; the original failures remain in `{directory.name}`."
        )
        phases.update({p["phase"]: p for p in replacement["phases"]})
        summary["comparison"] = replacement["comparison"]
        summary["phases"] = list(phases.values())
        summary["total_estimated_usd"] = sum(
            p["estimated_usd"] for p in phases.values()
        )
    main = phases["batched_1000"]
    batched, single = phases["matched_batched"], phases["matched_single"]
    replay = phases["cache_replay"]
    attempts = json.loads((directory / "attempts.json").read_text())
    events = [a for a in attempts if a["phase"] == "batched_1000"]
    with (directory / "request-timings.csv").open("w", newline="") as stream:
        fields = [
            "source_id",
            "question_count",
            "start_seconds",
            "http_seconds",
            "pacing_wait_seconds",
            "status",
        ]
        writer = csv.DictWriter(
            stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(events)
    accuracy = main["accuracy"]
    speedup = single["execute_seconds"] / batched["execute_seconds"]
    if batched["failed_batches"] or single["failed_batches"]:
        raise ValueError(
            "Matched comparison has failures; do not report a clean speedup"
        )
    savings = 1 - batched["usage"]["input_tokens"] / single["usage"]["input_tokens"]
    # Quantify the independently reported score discrepancy on the full run.
    differences = []
    normalized_vectors = 0
    wire_lines = directory / "http-responses.jsonl"
    for line in wire_lines.read_text().splitlines():
        event = json.loads(line)
        if event["phase"] != "batched_1000" or "response" not in event:
            continue
        normalized_vectors += sum(
            abs(sum(a["probabilities"].values()) - 1) > 1e-6
            for a in event["response"]["answers"].values()
            if "probabilities" in a
        )
        answer = event["response"]["answers"]["pressure"]
        derived = sum(int(i) * p for i, p in answer["probabilities"].items())
        differences.append(abs(answer["score"] - derived))
    rounding = {
        "nonzero_differences": sum(d > 1e-6 for d in differences),
        "max_absolute_difference": max(differences, default=0),
        "normalized_probability_vectors": normalized_vectors,
    }
    summary["analysis"] = {
        "matched_speedup": speedup,
        "matched_input_token_savings": savings,
        "score_consistency": rounding,
    }
    all_attempts = []
    for path in directory.parent.glob("run-*/attempts.json"):
        all_attempts.extend(json.loads(path.read_text()))
    total_input = sum(a.get("usage", {}).get("input_tokens", 0) for a in all_attempts)
    summary["analysis"]["all_recorded_runs_estimated_usd"] = (
        total_input * 0.042 / 1_000_000
    )
    summary["analysis"]["all_recorded_runs_http_attempts"] = len(all_attempts)
    (directory / "analysis.json").write_text(json.dumps(summary["analysis"], indent=2))

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "#f6f8fb",
            "axes.facecolor": "white",
        }
    )
    fig, axs = plt.subplots(2, 2, figsize=(12, 8), layout="constrained")
    fig.suptitle(
        "EDSL judgment evaluations · 1,000 real SMS messages",
        fontsize=18,
        fontweight="bold",
    )
    completions = sorted(a["start_seconds"] + a["http_seconds"] for a in events)
    origin = min(a["start_seconds"] for a in events)
    xs = [t - origin for t in completions]
    axs[0, 0].plot(xs, range(1, len(xs) + 1), color="#167d9a", linewidth=2)
    axs[0, 0].set(
        title="Full load: completed HTTP requests",
        xlabel="Seconds from first request",
        ylabel="Requests completed",
    )
    axs[0, 0].grid(alpha=0.2)
    latencies = [a["http_seconds"] * 1000 for a in events]
    axs[0, 1].hist(latencies, bins=35, color="#167d9a", alpha=0.85)
    p95 = main["http_latency_seconds"]["p95"] * 1000
    axs[0, 1].axvline(p95, color="#d36239", linestyle="--", label=f"p95: {p95:.0f} ms")
    axs[0, 1].set(
        title="Full load: HTTP latency (excluding pacing)",
        xlabel="Milliseconds",
        ylabel="Request count",
    )
    axs[0, 1].legend(frameon=False)
    bars = axs[1, 0].barh(
        ["5 questions per request", "1 question per request"],
        [batched["execute_seconds"], single["execute_seconds"]],
        color=["#167d9a", "#d36239"],
    )
    for bar in bars:
        axs[1, 0].text(
            bar.get_width() + 0.25,
            bar.get_y() + bar.get_height() / 2,
            f"{bar.get_width():.2f}s",
            va="center",
        )
    axs[1, 0].set(
        title=f"Same {batched['inputs']} inputs × 5 questions · {speedup:.2f}× faster",
        xlabel="Execution wall time (seconds)",
    )
    axs[1, 0].set_xlim(0, single["execute_seconds"] * 1.22)
    axs[1, 0].invert_yaxis()
    c = accuracy["confusion"]
    matrix = [[c["true_ham"], c["false_spam"]], [c["missed_spam"], c["true_spam"]]]
    axs[1, 1].imshow(matrix, cmap="Blues", vmin=0)
    for i in range(2):
        for j in range(2):
            axs[1, 1].text(
                j,
                i,
                str(matrix[i][j]),
                ha="center",
                va="center",
                fontsize=18,
                color=(
                    "white" if matrix[i][j] > max(map(max, matrix)) / 2 else "#153449"
                ),
            )
    axs[1, 1].set(
        xticks=[0, 1],
        xticklabels=["ham", "spam"],
        yticks=[0, 1],
        yticklabels=["ham", "spam"],
        xlabel="Predicted",
        ylabel="Gold label",
        title=f"Spam classification · {accuracy['accuracy']:.1%} accuracy",
    )
    fig.savefig(directory / "benchmark.png", dpi=160)
    fig.savefig(directory / "benchmark.svg")
    svg_path = directory / "benchmark.svg"
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text().splitlines()) + "\n"
    )
    plt.close(fig)

    rows = []
    for name in ("batched_1000", "matched_batched", "matched_single", "cache_replay"):
        p = phases[name]
        rows.append(
            f"| {name} | {p['inputs']} | {p['http_attempts']} | {p['compile_seconds']:.3f} | {p['execute_seconds']:.3f} | {p['end_to_end_seconds']:.3f} | {p['usage']['input_tokens']:,} | ${p['estimated_usd']:.5f} |"
        )
    report = f"""# Judgment evaluation load benchmark

**{main['completed_rows']:,} real inputs × 5 judgments: {main['execute_seconds']:.2f} seconds execution,
{main['end_to_end_seconds']:.2f} seconds including workload construction and compilation.**
The full load returned {main['completed_judgments']:,} judgments in {main['http_attempts']:,} HTTP attempts.

![Benchmark charts](benchmark.png)

## Measurements

| Run | Inputs | HTTP attempts | Compile (s) | Execute (s) | Build + compile + execute (s) | Input tokens | Estimated cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

Full-load throughput was **{main['inputs_per_second']:.2f} inputs/s** or
**{main['judgments_per_second']:.2f} judgments/s**. HTTP latency was
**{main['http_latency_seconds']['p50'] * 1000:.0f} ms median**,
**{main['http_latency_seconds']['p95'] * 1000:.0f} ms p95**, and
**{main['http_latency_seconds']['p99'] * 1000:.0f} ms p99**.
There were **{main['retries']} retries** and **{len(main['failed_batches'])} failed batches**;
HTTP statuses: `{json.dumps(main['http_statuses'])}`.
Saving the main evaluation/results packages took another {main['save_packages_seconds']:.2f} seconds.
File saving and dataset preparation are excluded from the timing table.

On the same {batched['inputs']} messages, batching was **{speedup:.2f}× faster** and used
**{savings:.1%} fewer input tokens** than sending one question per request.
Answer agreement by question: `{json.dumps(summary['comparison']['answer_agreement_by_question'])}`.
Maximum probability difference: {summary['comparison']['maximum_probability_difference']:.6g}.
The persisted-cache replay made **{replay['http_attempts']} HTTP requests**.

## Task and quality

The dataset is the [UCI SMS Spam Collection](https://archive.ics.uci.edu/dataset/228/sms%2Bspam%2Bcollection),
by Almeida and Hidalgo (2011), [DOI 10.24432/C5CC84](https://doi.org/10.24432/C5CC84), licensed CC BY 4.0.
We sampled 1,000 messages without replacement after exact-text deduplication, using seed 20260918.
The sample contains 882 ham and 118 spam messages. Only message text and its source-row ID
were sent to the model; labels were held separately. Questions cover spam classification,
urgency, commercial content, intent, and pressure (a three-level descriptive rubric).

Only spam classification has a gold label. Accuracy was **{accuracy['accuracy']:.1%}**, versus
an **{accuracy['majority_baseline']:.1%}** majority-class baseline. Spam precision was
**{accuracy['spam_precision']:.1%}**, recall **{accuracy['spam_recall']:.1%}**, and binary Brier
score **{accuracy['brier_score']:.4f}**. There were {c['false_spam']} false positives and
{c['missed_spam']} missed spam messages. Misclassified source IDs and probabilities are
in `batched_1000/metrics.json`. The other four judgments are workload and consistency
checks, not validated accuracy measurements. This is an old public dataset and is not
a contamination-controlled test of generalization.

## Execution and interpretation

{comparison_note}

- Model: `{summary['manifest']['model']}`; provider-reported versions: `{main['actual_models']}`.
- Concurrency: {main['concurrency']}; a shared pacer permits at most {main['request_rate_cap']:.0f} request starts/s,
  below TypeSafe's published 1,200 requests/minute limit. Pacing also covers retries.
- The warmup, full load, and two matched runs use independent empty EDSL caches.
  Cache replay reloads the saved full-load cache and checks identical answers.
- Matched runs use identical inputs, instructions, concurrency, and pacing. They are single,
  sequential trials (batched first), not randomized repetitions. Provider-side caching is uncontrolled.
- The measured speedup includes reduced rate-limit pressure. This is sustainable client
  throughput at the chosen cap, not a measurement of maximum server capacity or model compute speed.
- HTTP latency excludes client pacing, but includes network time; logical request durations
  including pacing/retries are recorded separately. Instrumentation/checkpoint overhead is included.
- Price estimate uses the [published $0.042/million input tokens](https://docs.typesafe.ai/models),
  output free, checked September 18, 2026. Total for the successful benchmark phases:
  **${summary['total_estimated_usd']:.5f}**. Including earlier diagnostic runs, the total
  across {len(all_attempts):,} recorded HTTP attempts is approximately
  **${summary['analysis']['all_recorded_runs_estimated_usd']:.5f}**. These are estimates, not invoices.

## Integration issues found by the load test

The first five-input warmup exposed independently reported Score/probability values that
failed an overly strict mean-equality check. Two valid HTTP responses differed by 0.01.
The backend now validates score bounds and probability distributions independently,
resolves EDSL answers from the distribution, and preserves the provider score plus
`score_from_distribution` and `score_difference` for audit. A regression test covers the
observed response. Full-load score differences: {rounding['nonzero_differences']} nonzero;
maximum absolute difference {rounding['max_absolute_difference']:.6g}.

The first full run also found seven batches with probability vectors totaling 0.99.
The TypeSafe adapter now normalizes vectors only when every entry is valid and the
mass discrepancy is at most 0.01. It preserves `reported_probabilities` and explicit
`probability_normalization` metadata. Larger discrepancies still fail validation.
The corrected full run normalized {normalized_vectors} vectors. All 1,000 saved
responses from the first full run also passed offline revalidation after the fix.
Cache replay is now explicitly forbidden from issuing inference calls; the earlier
incomplete-cache check correctly attempted to refill seven missing batches and was
not a pure cache benchmark. Earlier runs remain available in sibling run directories.

## Reproduce

From the repository root, set `TYPESAFE_API_KEY` in your gitignored `.env`, then:

```sh
mkdir -p examples/judgment_load_benchmark
curl -L --fail --silent --show-error '{SOURCE_DOWNLOAD}' -o examples/judgment_load_benchmark/source.zip
.venv/bin/python scripts/judgment_load_benchmark.py --execute
.venv/bin/python scripts/render_judgment_benchmark.py <run-directory>
```

Omit `--execute` to prepare the sample without inference. The manifest records the dataset
checksum, source revision, implementation file hashes, runtime, seed, and model. Each phase
contains its Evaluation and Results packages, a separately persisted cache, predictions,
and metrics. `http-responses.jsonl` checkpoints successful raw responses and timings;
`attempts.json` and `calls.json` separate HTTP attempts from logical calls. Credentials and
HTTP headers are never logged.

To repeat only the comparison, add `--comparison-only` to the benchmark command.
Pass `--comparison-run <repeat-directory>` to the report renderer to use it;
the report records both the failed comparison and the repeat explicitly.
"""
    (directory / "report.md").write_text(report)
    # A readable standalone HTML artifact with its chart embedded as SVG.
    chart = (directory / "benchmark.svg").read_text()
    import base64

    chart_uri = "data:image/svg+xml;base64," + base64.b64encode(chart.encode()).decode()
    table = "".join(
        f"<tr><td>{html.escape(p['phase'])}</td><td>{p['inputs']:,}</td><td>{p['http_attempts']:,}</td>"
        f"<td>{p['execute_seconds']:.2f}s</td><td>{p['compile_seconds']:.2f}s</td>"
        f"<td>${p['estimated_usd']:.5f}</td></tr>"
        for p in summary["phases"]
        if p["phase"] != "warmup"
    )
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>EDSL judgment load benchmark</title><style>
body{{font:16px/1.6 system-ui,sans-serif;background:#f6f8fb;color:#183247;margin:0}}main{{max-width:1100px;margin:auto;padding:42px 24px}}
h1{{font-size:36px;line-height:1.2}}.lead{{font-size:22px}}.cards{{display:flex;gap:18px;flex-wrap:wrap}}.card{{background:white;border-radius:12px;padding:20px;flex:1;min-width:180px}}.number{{font-size:30px;font-weight:700;color:#167d9a}}
table{{border-collapse:collapse;background:white;width:100%}}th,td{{text-align:right;padding:10px;border-bottom:1px solid #dce5eb}}th:first-child,td:first-child{{text-align:left}}img{{width:100%}}pre{{white-space:pre-wrap;background:white;padding:22px;border-radius:12px;font:14px/1.6 ui-monospace,monospace}}a{{color:#167d9a}}</style>
<main><p>EDSL · JUDGMENT EVALUATIONS · SEPTEMBER 18, 2026</p><h1>1,000 real messages. 5,000 typed judgments.</h1>
<p class="lead">A live test of Jev through EDSL’s fluent Evaluation API.</p><div class="cards">
<div class="card"><div class="number">{main['execute_seconds']:.2f}s</div>full-load execution</div>
<div class="card"><div class="number">{speedup:.2f}×</div>matched batching speedup</div>
<div class="card"><div class="number">{accuracy['accuracy']:.1%}</div>spam classification accuracy</div>
<div class="card"><div class="number">${main['estimated_usd']:.4f}</div>estimated full-load inference cost</div></div>
<p>Eight concurrent workers, capped at 18 request starts/s. The speedup includes the benefit of fewer requests under this cap.</p>
<img src="{chart_uri}" alt="Full-load completions, latency histogram, matched batching comparison, and spam confusion matrix">
<table><thead><tr><th>Run</th><th>Inputs</th><th>HTTP calls</th><th>Execute</th><th>Compile</th><th>Est. cost</th></tr></thead><tbody>{table}</tbody></table>
<h2>Methods, findings, and reproduction</h2><pre>{html.escape(report)}</pre></main></html>"""
    (directory / "report.html").write_text(page)
    print(
        json.dumps(
            {"report": str(directory / "report.html"), **summary["analysis"]}, indent=2
        )
    )


SOURCE_DOWNLOAD = (
    "https://archive.ics.uci.edu/static/public/228/sms%2Bspam%2Bcollection.zip"
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--comparison-run", type=Path)
    args = parser.parse_args()
    render(args.directory, args.comparison_run)
