# Calibration, overrides, and branching

## Contents

- Pilot calibration
- Manual overrides
- Skip logic
- Looped surveys

## Pilot calibration

Use `calibrate_from_results(pilot_results, percentile=...)` when a pilot exists.
Higher percentiles are conservative. Record the percentile and assumptions.

## Manual overrides

Use `TokenOverride` for questions whose expected answer, comment, or thinking
length clearly differs from defaults. Scope by service/model when needed and
always provide a note explaining the override.

## Skip logic

`branch_weights` are conditional probabilities among respondents reaching a
question. Weights from one question sum to at most 1; the remainder continues
normally. Report both worst-case ceiling and weighted expectation.

## Looped surveys

`Survey.loop_over` expands all copies at build time, so the default estimate is
a maximum-length ceiling. Derive iteration survival from a pilot or explicit
list-length assumptions. Place an early-exit weight on the last question of a
multi-question block and target the first question after the loop (or end only
when the loop is terminal). Verify reach probabilities for the final loop
iterations and the first post-loop question.
