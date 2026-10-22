# Above-Fundamental Trading in an EDSL Asset Market

`note.pdf` is the compiled note; `note.tex` is the editable LaTeX source.
The main text reports one GPT-5 mini market observed through round 17.
The appendix includes the workflow diagram, complete speculative prompts,
an actual answer, and the self-contained native experiment: `call_market`
configuration, workflow dependencies and pause rules, the EDSL execution plan,
and `WorkflowExperiment` save/load/replay examples.

## Compile

From this directory, with a standard TeX Live installation:

```sh
latexmk -pdf -interaction=nonstopmode -halt-on-error note.tex
```

No model calls, external downloads, or shell escape are needed to compile.
All figures and listing files are included and use relative paths.

## Contents

- `figures/`: publication figures in vector PDF and PNG.
- `code/portable.py`: complete native authoring file, with only EDSL and
  standard-library imports. Trader prompts match the historical construction;
  native commands reproduce all 204 saved decisions and 17 settlements without
  model calls. This rewrite was written after the reported run. Its `build()`
  works with the updated EDSL branch; `export()` additionally needs the original
  run directory to extract archived answers.
- `code/market_walkthrough.py`: retained earlier explanatory version using
  custom settlement functions; the appendix now presents `portable.py`.
- `code/`: also contains unchanged snapshots of the four source files fingerprinted by the run.
  These files belong in `examples/asset_market/` in the original EDSL branch;
  this compact bundle is not a standalone installation of the simulation.
- `data/decisions.csv`: all 204 decisions, rationales, fills, and closing holdings.
- `data/periods.csv`: all 17 rounds. Null prices mean no trade; the internal
  `reference_price` field is not an observed transaction or a displayed quote.
- `data/example-*-prompt.txt`: full actual EDSL system/user prompts for trader-00,
  round 1; `example-answer.json` contains its actual structured answer.
- `data/config.json`, `audit.json`, `summary.json`: configuration and audit/results.
- `data/observation-plan.md`: initial stopping policy and declared extension.
- `data/archive-recovery.json`: export repair that made no new model calls.
- `data/native-equivalence.json`: prompt, serialized specification, and native
  settlement comparison checks. The earlier walkthrough check is also retained.
- `walkthrough-listings.tex`: generated listing ranges used by `note.tex`.
- `manifest.json`: SHA-256 hashes of code, data, and figures.

Large SQLite histories and the complete raw-call archive remain in the original
workspace at `examples/asset_market/runs/gpt5-short-pilot/`.
The executed runner is frozen, including its original Results export call.
The appendix explains the `allow_new_commit=True` correction used on resumed export.

To regenerate figures and snapshots in the original repository, without model
calls, run `python -m examples.asset_market.build_latex_note`. It audits the saved
run before building. Fresh simulations need that branch's EDSL environment and
hosted-model access; the seed alone does not fix model responses.
