# Run shared-state examples through local coopr

The [2026-09-29 hosted smoke report](../artifacts/shared-state-acceptance/2026-09-29-hosted/report.md)
records a separate test against the actual chick environment using normal CLI
submission and persisted Results downloads: sequential poll, dynamic-price market,
and three snapshot rounds all passed (18 final result rows). It found two client
transport gaps: `.ep` persistence dropped state definitions/schedules, and `run()`
reset saved schedules. Both now have regression coverage. Rebuild shared-state
packages saved before these fixes; missing definitions cannot be recovered from
those packages alone. The report also records restoration of the prior chick
application and the retained additive migration history.

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

You can also rerun a saved scripted package through the normal CLI without coopr
or model calls:

```sh
ep run artifacts/shared-state-acceptance/my-scripted-run/activity_poll/scripted.jobs.ep \
  --model test --local --fresh \
  --output artifacts/shared-state-acceptance/my-scripted-run/activity_poll/cli.results.ep
```

All eight scripted examples have regression coverage for this path, including
package reload, a model override, execution, and saved-result checks. Model, agent,
and scenario overrides retain the job's schedule and explicit assignment plan.
Replacing a collection with a different length is rejected when an explicit
assignment plan depends on its positions.

Use `run()` for shared-state or ordered jobs. `run_batch(num_batches=1)` also
preserves the complete job. Splitting such a job into multiple batches is rejected:
batching shuffles interviews and creates independent jobs, which would change the
state scope and turn order.

## Real model behavior

All eight examples support live mode. They retain the original model questions,
use the actual worker/provider path, and check decisions against the final shared
state. They do not require predetermined answers. The default live selection is
still the small activity poll and ultimatum game. The worker must have credentials
for the named provider. Both initial cases passed with GPT-4o mini on 2026-09-28
after correcting the worker's
OpenAI credential. EDSL's `.env` had a working key; coopr's configured key returned
HTTP 401. The worker currently uses the working key through a temporary Compose
override at `/private/tmp/coopr-shared-state-provider.yml`. The override contains
only an environment-variable reference, not the key itself. For persistent setup,
configure `OPENAI_API_KEY` in coopr's `backend/.env` and recreate `runner-worker`.
Recreating it without the override otherwise restores the old credential.

```sh
.venv/bin/python -m examples.shared_state_acceptance \
  --live --model gpt-4o-mini --service openai \
  --output artifacts/shared-state-acceptance/my-live-run
```

The default `--live` selection makes paid calls: eight poll answers and four ultimatum answers, before
retries. Output is limited to 256 tokens per call, or 1,024 tokens including reasoning
for Gemini 3 models. This is not a dollar spending cap. Use `--case activity_poll`
or `--case ultimatum` to run one at a time.
`live.jobs.ep` files from scripted runs contain a placeholder test model; the live
command replaces it with the explicitly selected model.

Run all eight, or select any of the case names in the table above using `--case`:

```sh
.venv/bin/python -m examples.shared_state_acceptance \
  --live --all --model gpt-4o-mini --service openai --timeout 600 \
  --output artifacts/shared-state-acceptance/my-live-all
```

The full roster has 66 participants and at most 118 model answers before retries;
screening and capacity limits can reduce that count. Live checks independently
reconstruct quota admissions, purchases and cash balances, auction clearing prices
and allocations, booking availability, and greedy assignment scores. They also
check the historical purchase/appointment choices stored with each answer.

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

The successful [live report](../artifacts/shared-state-acceptance/2026-09-28-live-openai/report.md)
and [walkthrough](../artifacts/shared-state-acceptance/2026-09-28-live-openai/walkthrough.md)
contain 12 uncached answers. The poll ended with seven beach-day votes and one hike
vote. The two ultimatum pairs offered $83 (rejected) and $54 (accepted). Inspection
of every recorded prompt confirmed the prior votes or partner's offer were visible.
The rejection explanation misinterpreted who received the larger share; the
walkthrough preserves that model behavior for follow-up prompt experiments.

The [complete live acceptance report](../artifacts/shared-state-acceptance/2026-09-28-live-all.md)
now records successful runs for all eight examples: 66 participants and 113
uncached model answers. The expanded run exposed a coopr transport defect:
resolved question definitions and historical choices were dropped between prompt
rendering and worker validation. After preserving them through dispatch, validation,
completion, and cache-hit completion, the market and booking examples both passed.
Six new worker regression cases cover numeric/text choices, answer codes, saved
presentation, legacy tasks, and rejection of choices that were not shown.

The ultimatum responder question now spells out both acceptance payoffs. A rerun
produced the same $83 and $54 offers with both accepted. This is a useful prompt
check, not a controlled estimate of how the wording affects decisions.

Earlier Google attempts failed: Gemini 2.5 Flash was unavailable for this account,
and its suggested replacement, Gemini 3.8 Flash, returned HTTP 503 (high demand)
and HTTP 429 (free-tier request quota). Those failures remain saved separately.

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

## Adaptive questions, rounds, and concurrent claims

Six more live cases use a separate small suite:

```sh
.venv/bin/python -m examples.shared_state_advanced_acceptance \
  --live --model gpt-4o-mini \
  --output artifacts/shared-state-acceptance/my-advanced-run
```

This uses the same local coopr endpoint and OpenAI worker credential. It has 34
result rows, including repeated participants across rounds, and at most 72 model
answers before retries. Output is capped at 256 tokens per answer. Repeat `--case`
to choose a subset; without it, all six run. Outputs include `.ep` jobs/results,
raw runner responses, a report, and a readable `transcript.md` for each case.

| Case name | Check |
| --- | --- |
| `pairwise_comparisons` | Six comparisons across three products; exploration and adaptive selection; two remaining participants stopped; historical options preserved |
| `price_elicitation` | Four independent price intervals reconstructed from actual answers; early completion skips later questions |
| `team_formation` | Eligible choices and membership agree; at most one designer and two builders per team |
| `message_board` | Three participants over two rounds; prompts and snapshots contain exactly the earlier messages |
| `repeated_matrix` | Two players over three rounds; both see completed prior rounds, with no current-round action leaking |
| `work_pool` | Concurrent workers claim different items; prompts and completions use the authoritative assignment |

Recheck existing responses without making model calls:

```sh
.venv/bin/python -m examples.shared_state_advanced_acceptance \
  --verify --output artifacts/shared-state-acceptance/my-advanced-run
```

Verification writes `verification.json` and `verification.md`, preserving the
original run summary. It can regenerate transcripts even when report generation
failed after the remote job completed. It does not resume a failed remote job.

All six have passed; the [advanced results](../artifacts/shared-state-acceptance/2026-09-28-live-advanced-all.md)
link to each transcript. The price persona now explicitly defines its `value` as
maximum willingness to pay. The rerun elicited 0, 37, 65, and 100, matching the four
personas. The verifier checks state transitions against actual choices; it does
not force models to make those choices or certify their behavioral realism.

## Restart recovery

The opt-in Docker restart tests in coopr's
`backend/runner_services/tests/test_api_recovery.py` passed for the API, dispatcher,
and worker. Each abruptly restarts a service during a five-round job, then checks
both scopes, task accounting, write versions, and round order.

To exercise recovery with real model decisions as well:

```sh
.venv/bin/python -m examples.shared_state_restart_acceptance \
  --live --restart runner-api --restart runner-dispatcher --restart runner-worker \
  --output artifacts/shared-state-acceptance/my-live-restarts
```

This explicitly restarts the named local Compose services with zero shutdown grace.
It uses the two-round message board for the API, the snapshot game for the
dispatcher, and adaptive product comparisons for the worker. A restart is triggered
only after some tasks complete while another task is running. The suite records
the trigger, restart exit status, progress history, full results, and transcripts.
It requires a local runner URL and stops the batch if a case fails. A timeout
preserves the job ID and does not cancel the job.

The three cases target 18 model decisions and bypass the API inference caches.
Interrupted provider calls can repeat, so this does not assert exactly-once calls
or billing. Acceptance requires six committed decisions per case, correct state
and historical visibility, and complete task accounting without failed or blocked
tasks. Redis and PostgreSQL remain running throughout these service restarts;
infrastructure failover and loss of the PostgreSQL transition-lock connection are
separate failure scenarios.

All three live restart cases passed on 2026-09-28, with 18 uncached recorded model
answers and no duplicate committed decisions. The worker-interruption case finished
in about 75 seconds, including the wait for takeover after interruption. The
[restart report](../artifacts/shared-state-acceptance/2026-09-28-live-restarts/report.md)
links to per-service progress and transcripts; the
[Docker regression results](../artifacts/shared-state-acceptance/2026-09-28-restart-tests.xml)
record the three corresponding mock-model tests.

## Backend submission and streamed results

On 2026-09-29 the local backend acceptance pass exposed and fixed two retrieval
problems: temporary-token result endpoints referenced the wrong owner field, and
paginated results discarded the captured question text/options and shared-state
read versions. The latter required changes in both coopr's Redis reader and EDSL's
streamed Results construction. Legacy responses without presentation metadata keep
their survey-derived attributes.

Validation passed 54 checks: 44 hosted-runner/writer regressions, four backend
submission cases, two completion/billing retry cases, two Docker result-reader
cases, and two EDSL streaming cases. The backend submission tests use real
PostgreSQL, Redis, route handlers, and compute execution, with adapters for
authentication identity, cloud storage, and the backend-to-runner HTTP hop.
They check serial and snapshot rounds, both credential types, state history,
pagination, and denial of another account's result reads. They do not validate
real credentials or signed cloud URLs.

A separate recheck streamed all six saved advanced live jobs through the updated
backend Redis reader and EDSL client: 34 rows and 64 captured question presentations
matched the original results, and every example's semantic checks passed. It made
no new model calls. See the local [backend acceptance report](../artifacts/shared-state-acceptance/2026-09-29-backend-acceptance.md).

Real hosted authentication, GCS permissions, and the complete deployed lifecycle
remain to be tested together. Native Humanize state execution also remains open.
