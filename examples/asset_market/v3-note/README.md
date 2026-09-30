# V3 asset-market report

Open [report.pdf](report.pdf). Six pages explain the market, visualize all 360
trader decisions and fills, compare three full sessions, and document recovery.
The appendices print all 1,698 lines of the five core source files.

## Highlight convention

Green lines are added or modified relative to the **frozen source in the previous
full-market report**, not relative to V2. Gray lines are unchanged. New rules and
record modules are entirely green. The executor includes the null-result guard
used for the final one-trader retry. `code/baseline/`, `code/*.diff`, and
`data/code-changes.json` make the comparison inspectable, including deletions.
Original file line numbers are preserved in the listings.

## Results

- 30 rounds; 360 valid decisions; 107 shares traded in 17 rounds.
- First trade $22; peak $29.50; last trade $23.75; fundamental value $14.
- The last trade was one share: a $31.50 bid met a $16 ask under midpoint pricing.
- All 48 shares redeemed for $14 after final-round income.
- Successful 12-interview batches averaged 35.1 seconds.
- Recorded model cost $1.2877415; the failed result lacked usage data.

The original full run, V2, and V3 have the same default economics, persona texts,
seat assignment, model settings, seed, and dividend realizations, with fresh
responses. Their differences do not identify the effect of typed authoring.

## Rebuild the PDF

From this directory, with a TeX installation including `listings` and `lstlinebgrd`:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex
```

Figures and complete source listings are bundled; rebuilding the PDF makes no
model calls. To regenerate figures and report inputs **from the repository**:

```sh
python -m examples.asset_market.build_v3_note
```

That helper expects all three archived runs and the previous report's frozen
sources at their repository paths. Its copy under `code/` documents the build;
it is not a standalone figure builder for an arbitrary extracted directory.

## Replay without model calls

From the repository root with this shared-state branch installed, choose a fresh
output directory:

```sh
python -m examples.asset_market.typed_market_experiment \
  --responses examples/asset_market/v3-note/data/responses.json \
  --rules examples/asset_market/v3-note/data/rules.json \
  --treatment examples/asset_market/v3-note/data/treatment.json \
  --output /private/tmp/asset-market-v3-replay-new
```

This replays the 360 valid answers, not the failed attempt. No new model answers
are requested. It requires this branch's compatible EDSL runtime. The appendix
contains the full study-specific authoring and core implementation, not a copy
of the entire EDSL dependency tree.

## Provenance and recovery

`manifest.json` hashes the bundled code, data, and figures. The executed source
manifest and recovery verification identify both executor versions. The initial
version is `code/workflow_experiment_before_retry.py`; the printed version is
`code/workflow_experiment.py`. Reporting helpers are hash-checked against the
post-recovery verification record; they include the incomplete-result accounting.

`data/model-calls.jsonl.gz` preserves 361 result records, including the null
result. `data/responses.json` holds the 360 valid decisions. `data/market.json`
contains the final state, complete tape, order log, and individual histories.
The CSV files provide convenient round, decision, and wealth tables.

One invalid final-round submission intent was recorded before backend validation.
The one-time `code/recover_null_result.py` backed up databases, verified that the
intent's effect had never been applied, archived the invalid intent, and made
only that item retryable. It is forensic source, **not a routine rerun command or
a general recovery API**. The final audit verified that all previously completed
359 decisions and 29 settlements remained unchanged. `data/recovery.json` and
`data/verification.json` record the recovery and its checks.

The source-paper PDF is not redistributed. Its metadata and checksum are in
`data/source-paper.json`. These exploratory persona prompts are not the authors'
original prompts, and this run is not a numerical replication of their results.

## Verified report build

The final PDF has 33 pages (six pages of results plus appendices). All 1,698
core source lines are included exactly once. The extracted bundle compiles
without LaTeX layout or reference warnings. The documented saved-answer replay
completed all 390 workflow items and reproduced the archived final market state
exactly, without model calls. See `build-verification.json`.
