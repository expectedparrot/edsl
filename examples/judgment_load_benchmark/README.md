# Live judgment evaluation benchmark

This example evaluates 1,000 distinct UCI SMS Spam Collection messages with five
questions per message using `survey.to_evaluation().by(scenarios).by(models).run()`.
Gold spam labels are held separately and never sent to the model.

- [Full report with charts](run-20260918T130250Z/report.html)
- [Report as Markdown](run-20260918T130250Z/report.md)
- [Full-load request timings](run-20260918T130250Z/request-timings.csv)
- [Full-load metrics](run-20260918T130250Z/batched_1000/metrics.json)
- [Successful repeated comparison](run-20260918T131418Z/summary.json)
- [Benchmark script](../../scripts/judgment_load_benchmark.py)

The full load completed 5,000 judgments in 57.52 seconds execution / 60.28 seconds
including compilation, with no HTTP failures or retries. Spam accuracy was 97.6%.
At concurrency 8 and a cap of 18 request starts/s, the repeated 100-input comparison
took 6.13 seconds batched versus 28.45 seconds unbatched (4.64×). The report explains
the rate cap, precision/recall, costs, uncertainty, and limitations.

Compact evidence from all diagnostic runs is included:

- `run-20260918T125350Z`: five-message warmup exposed separately rounded scores.
- `run-20260918T125508Z`: first full run exposed seven 0.99-sum probability vectors.
  All 1,000 saved responses passed offline revalidation after the bounded adapter fix.
- `run-20260918T130250Z`: complete corrected full load and zero-network cache replay;
  subsequent comparison was interrupted by connection errors.
- `run-20260918T131418Z`: comparison-only repeat, complete with no failures/retries.

The TypeSafe adapter preserves original probabilities whenever it normalizes
rounding discrepancies, and retains provider scores alongside distribution means.
The committed evidence includes manifests, phase metrics, summaries, the final
report and charts, and full-load request timings. The manifest records the branch
and HEAD at execution time (before this feature was committed), together with
implementation file hashes. Downloaded messages, raw HTTP responses, predictions,
Evaluation/Results packages, and caches remain local generated artifacts; they
are not included in this example's Git history. Reproduction creates those files,
including `batched_1000/results.ep`. Rendering a new report requires the generated
request logs from a local run.

Dataset: Almeida, T. & Hidalgo, J. (2011). SMS Spam Collection. UCI Machine
Learning Repository. <https://doi.org/10.24432/C5CC84>. License: CC BY 4.0.
The downloaded archive contains the original dataset documentation. See
[dataset.json](dataset.json) for the archive checksum, deduplication, sampling seed,
and class counts.

To reproduce, download the linked UCI archive as `source.zip`, set
`TYPESAFE_API_KEY` in your gitignored `.env`, and run:

```sh
.venv/bin/python scripts/judgment_load_benchmark.py --execute
```

Omit `--execute` to prepare without inference. Add `--comparison-only` to repeat
only the matched comparison. See the full report for the download and rendering
commands.
