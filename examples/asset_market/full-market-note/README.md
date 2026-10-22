# A Full 30-Round LLM Asset Market

**Open `report.pdf`.** The main report covers the fresh 30-round GPT-5 mini
market. The appendices print the complete self-contained experiment, native
workflow executor, and native call-market implementation, followed by final
accounts and reproduction instructions.

## Results and qualifications

- 360 decisions, 30 settlements, 114 shares traded across 21 trading rounds.
- First trade: $23.75 in round 5. Peak: $31 in rounds 26–28 versus $14 fundamental value.
- No trades in rounds 29–30; all 48 outstanding shares were redeemed at $14.
  Redemption is a contractual payment, not an observed market-price crash.
- Recorded model cost: $1.2611. All 390 workflow attempts succeeded.
- Nine of 204 beyond-terminal forecasts violated the instruction to use $14;
  the report distinguishes execution correctness from economic comprehension.
- First 140 decisions ran serially. After a safe checkpoint, 220 more decisions
  ran through paired EDSL jobs; complete 12-trader jobs averaged 30.5 seconds.

## Full code and provenance

`code/full_market_experiment.py` consolidates the construction and entry point
into one readable file. It imports no other experiment module. It was written
**after the run** and checked against the entire archived specification
(normalizing fresh UUIDs and using the archive's creation timestamp).
A full replay of its 360 saved answers reproduced the entire final market state
without model calls. It contains no pilot observation pauses.

`code/edsl/workflow_experiment.py` is the exact batched executor used during
continuation. `code/edsl/call_market.py` is the exact native market implementation.
`code/edsl/assignment_plan.py` is additional supporting source from PR #2622.
The executable library still requires the updated shared-state EDSL checkout,
including the paired-assignment PR applied locally. These snapshots are not
an installable replacement for the full EDSL package.

`code/historical/portable.py` and `run_full_market.py` preserve the actual
construction files. `data/source-manifest.json` records initial implementation
hashes; `data/batch-runner-transition.json` records the switchover and updated
hashes. The earlier serial executor is identified by its hash; it is not included
as a reconstructed source snapshot or mislabelled as the batched implementation.

## Saved-answer replay (no model calls)

With the updated repository checkout as the working directory:

```sh
python -m edsl.workflows.replay \
  --experiment examples/asset_market/full-market-note/data/experiment.json \
  --responses examples/asset_market/full-market-note/data/responses.json \
  --output /private/tmp/full-market-replay-new
```

Or replay through the complete new authoring file:

```sh
python -m examples.asset_market.full_market_experiment \
  --responses examples/asset_market/full-market-note/data/responses.json \
  --output /private/tmp/full-market-source-replay-new
```

From an extracted report bundle, point Python at the updated EDSL checkout:

```sh
PYTHONPATH=/path/to/updated/edsl python code/full_market_experiment.py \
  --responses data/responses.json --output /private/tmp/full-market-bundle-replay
```

Choose a fresh output directory. Providing `--responses` prevents fallback to
model calls. Omitting it runs a new paid hosted-model session, whose answers
need not reproduce the archive. `--prepare-only` writes the specification alone.

## Data and compilation

- `data/model-calls.jsonl.gz`: all 360 actual EDSL results, prompts, and responses.
- `data/experiment.json`, `responses.json`, `market.json`: definition, answers, and complete final state.
- `data/round-13-job.json`: an actual serialized, paired 12-interview job.
- CSV files: every decision and fill, all periods, final wealth, and forecast violations.
- `data/trader-*-round-*.txt` and corresponding answer JSON: actual diagnostic examples.
- `data/authoring-check.json`, `replay-check.json`: source/specification and full replay evidence.
- `figures/`: vector PDF and PNG graphics. No missing prices are imputed.
- `manifest.json`: SHA-256 checksums for source, data, and figures.

Compile from this folder with TeX Live:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error report.tex
```

All graphics and code listings needed for compilation are included. No model
calls, downloads, or shell escape are needed. To regenerate the inputs from the
original repository, run `python -m examples.asset_market.build_full_market_note`.
Original SQLite histories and the checkpoint backup remain in the run directory;
they are not duplicated in the bundle.
