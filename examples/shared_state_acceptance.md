# Run shared-state examples through local coopr

Start with the scripted suite, then inspect a small real-model run. These commands
use the runner at `http://localhost:8001`; they do not use the hosted backend selected
by `ep info` and do not test hosted billing or cloud uploads.

Run from the EDSL repository root with the shared-state coopr services running.
Use a new output directory for each run. Every case gets fresh state identifiers.

```sh
.venv/bin/python -m examples.shared_state_acceptance \
  --output artifacts/shared-state-acceptance/my-scripted-run
```

The scripted suite preserves each example's state machine, survey flow, and schedule.
It substitutes portable `QuestionCompute` answers for the model questions, then
compares local SQLite execution with coopr/PostgreSQL execution. This checks state
semantics and transport, not the original model-question response validators.

| Example | Participants | Acceptance outcome |
| --- | ---: | --- |
| Activity poll | 8 | Two votes for each activity; every vote appears in final state |
| Ultimatum | 4, in two pairs | Offer 40, accept; independent pair state and finalization |
| Quota screening | 27 | Ten A and ten B admitted; seven screened out |
| Posted-price market | 4 | Stock exhausted; seller cash 140; total money conserved |
| Second-price auction | 3 | Price 70; A wins; total money conserved |
| Uniform-price auction | 3 | Price 65; one unit per bidder; total money conserved |
| Appointment booking | 5 | Three confirmed, one released, one unavailable |
| Balanced assignment | 12 | Six Control, six Treatment |

The entire answer table and final state are compared in addition to these checks.
Run a subset by repeating `--case`, for example `--case survey_quota --case ultimatum`.
The output includes `report.md`, `summary.json`, each runner job ID, portable Jobs
packages, and local/coopr Results packages. Failed runs retain diagnostic artifacts.
A timeout does not cancel the remote job; inspect its saved ID before resubmitting.

## Real model behavior

The initial live cases are the activity poll and ultimatum game. These retain the
original multiple-choice/numerical questions, use the actual worker/provider path,
and check valid decisions against the final shared state. They do not require a
predetermined model answer. The worker must have credentials for the named provider.
The local Google credential passed authentication, but Google rejected generation
with the older Gemini 2.5 Flash model for this account and suggested Gemini 3.8 Flash.
The replacement returned HTTP 503 (high demand), including on the delayed poll
retry. The ultimatum retry also encountered HTTP 429 for the account's free-tier
request quota. The local OpenAI credential returned HTTP 401. Real-model acceptance
has not yet passed; the successful scripted suite does not establish model behavior.

```sh
.venv/bin/python -m examples.shared_state_acceptance \
  --live --model gemini-3.8-flash --service google \
  --output artifacts/shared-state-acceptance/my-live-run
```

`--live` makes paid calls: eight poll answers and four ultimatum answers, before
retries. Output is limited to 256 tokens per call, or 1,024 tokens including reasoning
for Gemini 3 models. This is not a dollar spending cap. Use `--case activity_poll`
or `--case ultimatum` to run one at a time.
`live.jobs.ep` files from scripted runs contain a placeholder test model; the live
command replaces it with the explicitly selected model.

Inspect a saved result with the CLI:

```sh
ep results columns --file artifacts/shared-state-acceptance/my-live-run/activity_poll/coopr.results.ep
ep results select --file artifacts/shared-state-acceptance/my-live-run/activity_poll/coopr.results.ep --column 'answer.*'
ep results cost artifacts/shared-state-acceptance/my-live-run/activity_poll/coopr.results.ep
```

Use `runner-response.json` to inspect the full state history under
`results.data.shared_state`, plus recorded prompts and answers. The runner Results
package contains the same provenance and can be loaded with `Results.load(...)`.

Gemini 3.8 parameters follow the [Google migration guide](https://ai.google.dev/gemini-api/docs/generate-content/latest-model):
legacy sampling controls and `thinking_budget` are omitted. Current provider rates
are on [Google’s pricing page](https://ai.google.dev/gemini-api/docs/pricing).
The hosted `ep jobs cost` endpoint returned `JOBS_ERROR` during setup; catalog or
provider estimates must not be described as confirmed billing.

## First acceptance pass

On 2026-09-28 all eight scripted cases passed, totaling 66 result rows in each
execution environment. The pass found and fixed two defects: missing first-question
agent/prior-answer context in portable compute tasks, and missing DAG dependencies
for answer references nested in state command inputs. Regression tests cover both.
The saved [acceptance report](../artifacts/shared-state-acceptance/2026-09-28-scripted/report.md)
and its per-example packages are local artifacts, excluded from Git. Running the
suite creates the same report structure in your chosen output directory.

The systematic-review example currently performs screening and adjudication in two
separate jobs sharing local state. Remote jobs isolate state by job ID, so that
example needs a single-job phase representation before it can join this suite.
Humanize execution and full hosted submission/billing/cloud persistence remain
separate acceptance work.
