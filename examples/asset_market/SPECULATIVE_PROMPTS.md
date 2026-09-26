# Speculative prompt intervention, version 1

Fixed before new LLM results: three 30-period sessions, seeds 140926–140928,
two each of RA/MC/BT/PC/NT/OC, gpt-4o-mini, temperature 0.7, 650 output tokens.
The comparison is the completed all-six treatment on the same three seeds.
Budget: 1,080 new decisions, roughly $1 in model calls based on the earlier runs.

## Changes

- Remove the supplied fundamental-value answer and the artificial opening quote.
  Show actual transaction prices and explicit no-trade periods. The internal
  exchange reference remains unused by the new prompts; neither `last_price`
  nor tape `reference_price` is rendered. All financial rules, including $14
  redemption, remain disclosed and unchanged.
- Present current cash and all private order prices in dollars, with labeled
  decisions, fills, forecasts, and remembered plans.
- Ask for expected transaction prices and emphasize possible resale profits.
  Strengthen momentum, early optimism, speculative timing, variable hunches,
  and loss aversion in the corresponding personas. Retain an arbitrage type.
- Give no target trading price, guaranteed future demand, invented price history,
  or instruction to produce a bubble. Optimistic beliefs are explicitly beliefs.

These are newly authored prompts, not prompts from the paper. This is a joint
intervention: results cannot isolate anchor removal from stronger personas or
clearer account presentation. Matching seeds fixes dividends, assignments, and
exchange tie breaks; model outputs remain stochastic. Report all three seeds,
including failures to produce a bubble. Do not tune this version after seeing
its outcomes.

The original experiment, runner, persona files, and run archives are preserved.
The new workflow reuses their shared-state machine and exchange, replacing only
the trader instructions and question surveys. Both implementations are hashed
in new run configs. The workflow, actual raw prompts, answers, orders, account
histories, and settlement events remain saved.

## Outcomes and validation

Use the previous follow-up diagnostics: actual transactions at or above $17.50;
at least two consecutive calendar periods at that level; and a subsequent
20% peak-to-trough fall. No-trade periods interrupt a consecutive run; terminal
redemption does not count as a transaction or a crash. The latter two diagnostics
are ours. Also show prices, volume, all orders, forecasts, and account outcomes.

Before calling models, verify a two-period scripted workflow, unchanged machine
definitions and settlement steps, serialization, absence of artificial reference
quotes in rendered prompts, and exact accounting. After completion, audit the
full run and verify the saved actual prompts against the intended variant.

```bash
python -m examples.asset_market.run_speculative --backend llm --workers 3 \
  --output examples/asset_market/runs/speculative-v1
python -m examples.asset_market.speculative_report
```
