# GPT-5 mini: short observation of a 30-period market

User request: use GPT-5 mini and observe a bubble inflating without running all
30 rounds. This is one exploratory market, seed 140926, with the unchanged
speculative-v1 prompts and two each of the six archetypes. Model settings match
the successful comprehension diagnostic: medium reasoning, temperature 1,
8,000 completion tokens including reasoning. Expected cost roughly $1–2.

The economic horizon remains **30 periods**. Dividends, interest, endowments,
clearing, forecasts, and period-30 redemption remain unchanged. Deliver and
settle at most **12 periods**, then pause with live inventories and no early
redemption. Stop sooner if two consecutive actual transaction prices are at
least **$17.50**, the previously chosen 25%-above-fundamental threshold. This
early-stop rule is for an exploratory demonstration, not inference about bubble
frequency, peak timing, or crashes. Record all observations and the stop reason.

Each round's 12 questions are opened from the shared state before any of that
round's answers are committed. EDSL runs those independent interviews
concurrently; shared-state submissions and settlement commit serially. The
exchange waits for all 12 submissions. Record raw responses and finish reasons.
Do not supply comprehension answers, force trades, change prompts after seeing
prices, or invent a rising price history.

The saved workflow contains all 30 periods and can later resume. An intentionally
paused observation is distinguished from a completed 30-period market.
The local scripted check pauses after two rounds and resumes to round three,
without redeeming or regenerating earlier orders. Audit the observed prefix
for accounting, constraints, private observations, calls, and exactly-once
settlement before reporting the result.

## Observation extension declared after round 6

The first six rounds had no transactions. The first-period precommitments put
scheduled sales in rounds 16–30 for trader-09 and rounds 26–30 for trader-06.
To reach the first planned supply without changing any trader prompt or market
rule, preserve the round-12 checkpoint and **resume through round 20 only if
there are still zero transactions at round 12**. Keep the same two-consecutive-
prices early-stop rule. This outcome-dependent extension is exploratory and
must be disclosed; it is not part of a fixed-horizon statistical comparison.

```bash
python -m examples.asset_market.run_gpt5_pilot --stop-after 12 \
  --output examples/asset_market/runs/gpt5-short-pilot
python -m examples.asset_market.gpt5_pilot_report
```
