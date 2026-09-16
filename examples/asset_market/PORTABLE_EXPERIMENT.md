# A portable asset-market experiment

The pilot now has a complete serialized specification in
[`portable/experiment.json`](portable/experiment.json). With **this branch's
updated EDSL installed**, a fresh process can load and execute it without
importing `examples.asset_market` or registering experiment-specific callbacks.
The historical run, raw answers, and fingerprinted source files are preserved.

## What the specification contains

| Component | Serialized representation |
|---|---|
| Participants | Twelve named agents with the actual persona instructions, plus the exchange |
| Questions | All thirty rounds of structured surveys and state-dependent prompt templates |
| Coordination | Sealed order submissions, the all-trader barrier, and deterministic settlement |
| Exchange rules | Standard `call_market_submit@1` and `call_market_settle@1` capabilities |
| Economic choices | Endowments, horizon, price rule, tie-breaking, constraints, monetary rounding, income order, dividend distribution, and terminal redemption |
| Observation | Workflow pause predicates and the condition permitting round-12 continuation |
| Execution | GPT-5 mini model parameters and a literal exchange response |

These are data interpreted by EDSL's versioned operations. EDSL's implementation
code remains a dependency, as it is for any interpreter. The file contains no
embedded Python functions or instructions to import experiment modules.
An unavailable algorithm/version is rejected during loading before creating
execution databases. Custom runtimes remain possible through an explicit
`runtime=` argument; they are not automatically imported by a serialized file.

## Replay the observed market without model calls

From the repository root:

```sh
python -m edsl.workflows.replay \
  --experiment examples/asset_market/portable/experiment.json \
  --responses examples/asset_market/portable/responses.json \
  --output /private/tmp/asset-market-portable-replay
```

The JSON response reports `status: ok`, with `data.status: paused` after round
12 and 156 completed work items (144 trader decisions plus 12 settlements).
Then explicitly acknowledge that observation checkpoint:

```sh
python -m edsl.workflows.replay \
  --experiment examples/asset_market/portable/experiment.json \
  --responses examples/asset_market/portable/responses.json \
  --output /private/tmp/asset-market-portable-replay --resume
```

The next pause is `overpricing-17`: 221 completed work items, 204 trader
decisions, and 17 settlements. The prices are $17.53 and $17.67; inventories
remain live. Replay uses supplied answers and cannot fall back to model calls
when a response is missing. Output directories cannot be silently overwritten.

`responses.json` contains the original 204 structured answers.
`expected.json` contains the archived accounts, full transaction tape, and
admitted orders. The fresh-process acceptance test blocks all `examples.*`
imports and compares these three structures exactly, including private
histories, cash balances, fills, dividends, and interest.

## Authoring the economic rules

[`portable.py`](portable.py) is the complete, self-contained authoring file.
It includes all six persona instructions, the full question template, explicit
economic rules, 30 rounds of workflow dependencies, pause rules, and the EDSL
execution plan. It imports only EDSL and Python's standard library.

Start here to read or modify the experiment:

| Function | Purpose |
|---|---|
| `question_text` | Full rules, private account/history, public tape, and answer request |
| `build_agents` | Two traders per archetype, shuffled into reproducible seats |
| `build_market` | Endowments, clearing rule, interest, dividends, and redemption |
| `add_pause_rules` | Two-price threshold and round-12/20 observation checkpoints |
| `build_execution_plan` | GPT-5 mini traders and a scripted exchange |
| `build` | Assemble the workflow and return a `WorkflowExperiment` |
| `export` | Save the specification and extract original answers for replay |

Build and save a new specification without model calls:

```python
from examples.asset_market.portable import build

experiment = build()
experiment.save("my-market.json")
```

The complete exporter also needs the historical run directory, and is invoked
from the repository root with `python -m examples.asset_market.portable`.
The economic configuration uses ordinary EDSL objects:

```python
from edsl.sharedstate import call_market, SharedState, SharedStateMap

machine = call_market(
    trader_names,
    periods=30,
    seed=140926,
    initial_cash_cents=10000,
    initial_shares=4,
    pricing_rule="marginal_midpoint",
    redemption_cents=1400,
    income_schedule=[
        {"kind": "cash_interest", "rate": 0.05},
        {"kind": "share_dividend", "values_cents": [40, 100],
         "probabilities": [0.5, 0.5],
         "sampling": "python_random_choice_v1"},
    ],
)
states = SharedStateMap(SharedState(market=machine), state_id="market")
```

The saved machine includes explicit defaults such as no borrowing or shorting,
expiry of unfilled orders, price priority with seeded tie-breaking, and half-up
cent rounding. Version 1 supports marginal-midpoint, marginal-bid, and
marginal-ask prices. Unsupported policies fail validation rather than silently
being ignored. Reordering the income schedule changes whether dividends earn
interest in that round. Uniform dividend draws preserve the original pilot's
seeded `random.choice` stream; weighted draws use the separately named
`python_random_choices_v1` sampling method.

## Observation is part of the workflow

`workflow.pause_after(step, name=..., read=market.read(), condition=...)`
stores a predicate over a committed state snapshot. Existing ready work drains
before the check; successors wait. A matching predicate pauses the workflow
without completing or discarding future steps. Checks and pauses are durable,
and explicit `coordinator.resume(instance_id)` acknowledges the pause.
An optional `resume_when=` expression restricts continuation.

The exported pilot encodes the round-12 checkpoint, permits its continuation
only when there have been no transactions, and includes a round-20 cap and
the two-consecutive-prices threshold. The economic horizon remains 30. This is
a retrospective encoding of the policy actually used: the extension was
declared after round 6, not before the original experiment started.

Workflows containing pause rules serialize as version 3. Existing workflows
without them retain their version-2 representation, preserving their stored
definition fingerprints. Version 1 and 2 workflows still load.

## Loading and live execution

```python
from edsl.workflows import WorkflowExperiment

experiment = WorkflowExperiment.load("experiment.json")
experiment.save("experiment-copy.json")
```

`experiment.run("new-output")` executes the configured LLM calls through EDSL
using locally configured provider credentials. It incurs model charges.
`experiment.run("new-output", responses=saved_answers)` performs data replay.
Both open the entire ready batch before submitting answers. The generic runner
creates one EDSL job per compatible workflow step and model configuration.
Each agent is paired with its own frozen scenario using `zip_assign()` from
[PR #2622](https://github.com/expectedparrot/edsl/pull/2622), applied locally on
this branch. EDSL runs the interviews concurrently. The job is saved under
`jobs/`, and `inference-batches.jsonl` records batch membership and timing.
Results are matched to work-item IDs, so completion order does not determine
who receives an answer. Successful submissions survive partial-batch failures;
only unfinished work is retried. Fresh responses need not reproduce the archive.

Live calls and execution attempts are archived. SQLite retains the workflow
and market checkpoints; restoring validates the complete pinned specification.
The replay commands above use the same coordinator and state backend as live
execution, substituting only the answer source.

## Validation

The tests cover JSON round trips, pricing choices, admission limits, sealed
balances, deterministic tie priority, income ordering, final redemption,
pause/resume persistence, continuation guards, missing capabilities, and the
full archived market in a fresh process. They also check compatibility with
the existing workflow and shared-state tests.

```sh
python -m pytest -q tests/sharedstate tests/workflows
```

Some existing local test-model integration tests create object-store files in
EDSL's application-data directory; that directory must be writable when running
the full suite.
