---
name: edsl-results-validation
description: Compare simulated EDSL survey results with human responses. Check survey compatibility, choose population or record-level comparisons, and create a reproducible study-specific analysis script with clear uncertainty and limitations.
tags: [edsl, results, human-data, validation, analysis]
---

# Compare simulated results with human responses

Use this skill when a user wants to understand whether simulated respondents
answer like real respondents, or wants to compare model-generated answers with
human judgments. The first task is to identify what kind of comparison their
study supports. Do not assume every human-versus-simulation comparison is the
same problem.

When analyzing a saved Results package, inspect the typed columns with `ep results columns --file results.ep`. Use `ep results export results.ep --column model.model --column "scenario.*" --column "answer.*" --output responses.csv` or iterate the reloaded Results in Python. Keep groups with missing reviews. Report the denominator for each rate or spread. When comparing treatments across models, calculate within-model differences before pooling and check the direction for each model.

## Choose the estimand before writing code

There are two distinct goals:

- **Population-level response patterns:** compare answer distributions between
  the simulated sample and human sample. This is appropriate when there is no
  one-to-one correct human answer for each simulated respondent. Use marginal
  distributions overall or within comparable subgroups.
- **Record-level agreement:** compare predictions and human labels for the same
  underlying records, cases, or vignettes. This requires a stable shared record
  identifier and a defensible human reference label. Do not describe a marginal
  distribution comparison as record-level accuracy.

Ask one concise question if the user's goal or the shared unit is unclear. If
there are multiple human judgments per record, preserve them for an inter-rater
analysis or document how adjudicated labels were made; do not silently select
the first response or treat an unresolved majority as ground truth.

## Inspect inputs and check comparability

Read the project files and inspect both `Results` objects before choosing
columns or metrics. Use `ep inspect <file.ep>` for local packages and the
available `Results` APIs for loaded objects. Humanize results can be retrieved
with `Coop().get_human_survey_responses(uuid)` when the user supplies or has
already authorized use of the survey UUID. Do not publish data, submit a job,
or contact respondents as part of this analysis.

Before calculating a comparison, make a compact compatibility table for every
question being considered:

| Check | What to verify |
|---|---|
| Identity | Both datasets contain the same intended item; matching names alone are not proof. |
| Type and scale | Question types, option labels, value coding, and scale direction agree. |
| Wording and conditions | Question wording, instructions, question order, and relevant scenario text are equivalent. |
| Routing and missingness | Skips, nonresponse, failed answers, and partial submissions have the same inclusion meaning. |
| Sampling unit | Identify a human respondent, simulated agent, scenario/record, model, and iteration; determine which rows are independent. |
| Subgroups and weights | Verify variables have the same definitions and coding on both sides; inspect missing and invalid weights. |

Stop or narrow the analysis when a material mismatch remains. Explain the
mismatch and either harmonize it with a documented rule, compare only the
compatible questions, or ask the user how to proceed. Never silently equate
different labels or reverse-coded scales.

## Build a study-specific analysis

This capability is an analysis workflow, not a built-in `ResultsFidelity`
method. Create a small, readable Python script in the study's existing analysis
directory (or ask where to save it if there is no clear location). The script
should load the user's existing result artifacts, perform the checks above,
calculate the selected comparison, and save machine-readable tables plus a
short interpretation. Do not rerun model jobs or collect human responses to
complete the comparison unless the user asks.

Prefer the smallest set of methods that answer the research question:

- **Nominal, single-choice answers:** show option shares side by side and a
  per-option difference. Total variation distance (TVD) is a useful compact
  summary: half the sum of absolute share differences, bounded from 0 (same
  shares) to 1 (no overlap). Jensen-Shannon distance is another bounded summary
  when a symmetric information-based measure is useful. Include the option
  table so the summary is interpretable.
- **Ordinal scales:** report the full category distribution and an ordinal
  summary such as mean/median or cumulative-share differences. Treating ordered
  categories as nominal may discard useful information; explain the metric if
  using TVD or Jensen-Shannon distance.
- **Numeric responses:** inspect range, units, and shape; compare meaningful
  summaries or distributions. Bin only with substantively justified cut points
  and report them.
- **Checkbox / multi-select answers:** compare selection rates separately for
  each option. These are not a single-choice distribution and their shares need
  not sum to one.
- **Free text:** use a documented coding rubric or a separate evaluation
  instrument. Do not compare raw string equality as if it measured semantic
  agreement.
- **Same records with reference labels:** join by the stable record identifier,
  validate join cardinality, report unmatched rows, then use a task-appropriate
  agreement measure. Keep human disagreement visible when there is no adjudicated
  reference.

Subgroup comparisons are useful only when the subgroup has the same meaning on
both sides and enough observations to interpret. Always report unweighted row
counts for each side and group. If using survey weights, validate finite,
non-negative values, explain the weighting target, and distinguish respondent
counts from weighted shares. Report effective sample size when weights vary
substantially.

## Uncertainty and dependence

Use uncertainty estimates only after identifying the sampling unit and design.
For independent respondent samples, a respondent-level bootstrap can show how
sample variation affects the distance. For repeated observations of the same
person, multiple iterations of an agent, clustered scenario assignment, or
repeated model runs, resample at the independent cluster (or use a suitable
design-based method); row-wise resampling would understate uncertainty.

A nonnegative distance has finite-sample upward bias, so a percentile bootstrap
interval can remain above zero even when samples come from the same population.
Do not interpret “interval excludes zero” as a test that the distributions
differ. If useful, compute a human split-half reference by repeatedly dividing
the human respondents into two groups and comparing their distributions. Label
it as a descriptive sampling-noise reference, not a significance threshold or
formal pass/fail criterion. State that half-samples are smaller than the full
human sample and therefore generally have more sampling variation.

Report methodological choices alongside results: included questions, exclusions,
missing-answer rule, weight variable, subgroup definitions, resampling unit,
metric, random seed, and number of resamples. Do not claim representativeness or
population validity from a convenience sample or a distance score alone.

## Deliverables

Create a reproducible analysis script and save outputs beside it, typically:

- a question compatibility table;
- a per-question (and per-model/subgroup, when relevant) summary table;
- option-level shares and differences;
- optional uncertainty estimates with the sampling unit stated;
- a concise Markdown interpretation noting limitations and unresolved mismatches.

Keep outputs traceable to source result files and avoid overwriting existing
reports. Before finishing, summarize which comparison was performed, what was
excluded, where the script and outputs were saved, and what the results can and
cannot establish.

## Related EDSL workflows

Use `edsl:edsl-human-survey` for deploying and retrieving human surveys, and
`edsl:edsl-prolific` when the user wants a paid, screened sample.
