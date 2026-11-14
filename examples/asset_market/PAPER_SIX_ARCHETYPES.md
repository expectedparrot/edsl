# Follow-up: the paper's six theory-derived trader archetypes

## Fixed design, before inspecting the new runs

The user requested the behavioral archetypes described in the original PDF.
This follow-up uses **all six theory-derived types from PDF page 14**, with two
traders of each type per 12-trader market:

| Code | Archetype | Paper's description |
|---|---|---|
| RA | Rational Arbitrageur | Buys on expected return above a threshold |
| MC | Momentum Chaser | Buys rising prices and sells on the dip |
| BT | Bubble Timer | Rides up and exits when the rise decelerates |
| PC | Precommitter | Fixes buy and sell periods in advance |
| NT | Noise Trader | Has a vague prior and updates inconsistently |
| OC | Overconfident Contrarian | Buys falling prices and never sells losers |

These are the existing reconstructed `THEORY` prompts in `experiment.py`,
unchanged from the original pilot. The PDF does not supply their complete
original wording. The three evolved prompts on PDF pages 36–38 are a separate
family and are not the population used in this follow-up.

The earlier theory condition included BT, OC, and PC only. The new population
adds RA, MC, and NT, reducing each type's count to two. The all-six mix is one of
the source's 63 compositions; it is **not** the source's highlighted closest
match to human peak timing, which was BT+OC+PC.

Three 30-period sessions use seeds 140926, 140927, and 140928. Each session has
360 actual LLM decisions. Execution continues to use gpt-4o-mini, temperature
0.7, and 650 maximum output tokens per decision. No new behavioral equations,
private signals, liquidity shocks, prescribed price paths, or instructions to
produce a bubble are added. Prompts, initial $14 reference, monetary information,
accounting, and matching rules remain as in the first pilot. The cash-unit
presentation issue identified in that pilot is not changed in this comparison.

The first session shares its dividend/tie-break seed with the earlier pilot.
Model responses are stochastic; the seed does not reproduce model generations.
The three new sessions explore run-to-run variation, but the earlier conditions
have only one session each, so the comparison does not identify a treatment effect.

## Outcome diagnostics

Report transaction prices, volume, no-trade periods, mean relative absolute
deviation from $14, and peak timing. A no-trade period remains missing price data;
terminal redemption is not a transaction or a crash.

Use $17.50 (1.25 × fundamental value, the cutoff appearing in PDF page 31) as a
price-excursion threshold. Separately report whether at least two consecutive
calendar periods transact at or above that threshold, and whether the observed
peak is followed by a transaction at least 20% lower. The duration and drawdown
criteria are diagnostic choices for this follow-up, not definitions supplied by
the paper. Report all three sessions, regardless of the outcomes. A brief high
quote or an unexecuted order is not a price excursion.

## Reproduce

```bash
python -m examples.asset_market.run --backend llm \
  --treatment RA+MC+BT+PC+NT+OC --replicates 3 --workers 3 \
  --output examples/asset_market/runs/paper-six-archetypes

python -m examples.asset_market.audit \
  --runs examples/asset_market/runs/paper-six-archetypes \
  --output examples/asset_market/runs/paper-six-archetypes/audit.json

python -m examples.asset_market.paper_followup_report
```

Raw evidence is preserved in each session's workflow/state databases, model-call
JSONL, Results package, order ledger, and summaries. The new report lives in
`paper-six-report/`; the original pilot report is preserved.
