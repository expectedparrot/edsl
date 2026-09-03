# Automated Social Science as a Workflow

## Purpose

This proposal maps Manning, Zhu, and Horton’s *Automated Social Science:
Language Models as Scientist and Subjects* onto EDSL’s durable workflow model.
The paper’s pipeline starts with a social scenario, proposes a structural causal
model (SCM), uses it to generate treatments and agents, runs multi-agent social
interactions, measures outcomes, fits the prespecified model, and uses the fitted
SCM for prediction or follow-on experiments.

The central design decision is to keep two directed acyclic graphs distinct:

| Graph | Meaning | Nodes | Edges |
|---|---|---|---|
| Workflow DAG | What happens, when, and who may act | tasks, conversations, measurements, analyses | execution dependencies |
| Causal DAG | What the study claims causes what | scientific variables | direct causal relationships |

The SCM compiles into a workflow, but it is not the workflow. A causal edge such
as `buyer_budget -> deal` does not mean that “measure deal” executes immediately
after “assign budget.” Between them may be recruitment, a conversation, retries,
measurement, and adjudication.

## Current implementation status

The first independent `edsl.causal` slice now exists. It includes:

- `EndogenousVariable`, `ExogenousVariable`, `Measurement`, participant and
  scenario scopes;
- `Equation` and `StructuralCausalModel`, including causal-DAG validation;
- `PathEffect`, `EstimatorSpec`, and `CausalAnalysisPlan`;
- deterministic full or sampled factorial `ExperimentDesign` objects;
- a linear/linear-probability fitting backend and serialized `FittedSCM` with
  specification and data-manifest hashes.
- `ExperimentCompiler`, which produces stable role assignments, separates private,
  public, and system treatment context, and emits measurement manifests;
- `edsl.conversations`, with all six serialized protocols, append-only SQLite
  transcripts, optimistic version checks, semantic/hard stopping rules, and an
  audit trail for unrealized coordinator-after responses.

The authored mug example now combines its SCM, 320-replication design, compiled
role assignments, ordered conversation protocol, semantic judge, and 20-turn cap.
`CausalExperimentRunner` supplies the bridge: it accepts model-independent
speaker, semantic-judge, and measurement callbacks; resumes durable transcripts;
and returns typed treatment/outcome observations to the frozen analysis plan.
`EDSLCausalAdapter` now supplies those callbacks through EDSL's ordinary
agent/survey/model pipeline, performs strict type conversion for measurements,
and retains a serializable provenance record of every speaker, judge, and
measurement call. The remaining work before a pilot is a small run manifest and
cost check rather than immediately launching all 320 replications.

## Proposed end-to-end flow

```text
Scenario
   |
   v
LLM proposes roles, variables, paths, operationalizations
   |
   v
Researcher/LLM review gate -----> frozen SCM + pre-analysis plan
   |
   v
Experiment compiler
   |---- treatment cells / sampled design
   |---- agent traits, goals, constraints, information policy
   |---- conversation protocol and stopping rule
   `---- outcome measurement surveys
   |
   v
Parallel workflow instances, one per treatment-cell replication
   |
   v
Typed observation table + transcripts + complete provenance
   |
   v
Prespecified SCM fit -----> coefficient predictions / outcome predictions
   |
   v
Human or LLM proposes a follow-on SCM revision
```

Every box is a durable workflow step or a serializable compiler artifact. Human
review can be inserted at any boundary without changing the surrounding model.

## SCM data model

The paper stores considerably more than a causal graph. Each variable needs an
operationalization, type, units, levels, scope, proxy attributes, treatment
values, measurement questions, and an aggregation rule. Those fields should be
native data rather than prose hidden in prompts.

```python
deal = EndogenousVariable(
    name="deal_occurred",
    dtype="binary",
    units="indicator",
    levels=[0, 1],
    operationalization="1 if buyer and seller agree to a sale; 0 otherwise",
    measurement=Measurement(
        respondent_role="buyer",
        survey=deal_survey,
        field="deal",
        aggregation="single",
        missing="allow_if_not_applicable",
    ),
)

budget = ExogenousVariable(
    name="buyer_budget",
    dtype="continuous",
    units="USD",
    scope=ParticipantScope("buyer"),
    visibility="private",
    operationalization="Maximum amount the buyer may pay",
    proxy_attribute="Your maximum budget is {{ value }} USD.",
    treatments=[5, 10, 20, 40],
)

attachment = ExogenousVariable(
    name="seller_attachment",
    dtype="ordinal",
    units="attachment_level",
    levels=["none", "low", "high", "extreme"],
    scope=ParticipantScope("seller"),
    visibility="private",
    proxy_attribute="Your sentimental attachment is {{ value }}.",
    treatments=["none", "low", "high", "extreme"],
)

scm = StructuralCausalModel(
    variables=[budget, attachment, deal],
    equations=[
        Equation(
            outcome=deal,
            parents=[budget, attachment],
            family="linear_probability",
            interactions=[],
        )
    ],
)
```

`StructuralCausalModel.to_dict()` must contain only data. Equations use an
allowlisted expression language; arbitrary Python formulas are rejected. The
model validates unique names, compatible units and types, acyclicity, equation
coverage, and whether each proposed estimand is identified under the declared
design.

## Estimands and pre-analysis plan

The causal graph alone does not fully specify analysis. The durable study object
should freeze estimands, estimators, interactions, missing-data handling, and
standard-error choices before execution.

```python
plan = CausalAnalysisPlan(
    scm=scm,
    estimands=[
        PathEffect(cause=budget, outcome=deal),
        PathEffect(cause=attachment, outcome=deal),
    ],
    estimator=LinearSCM(
        include_intercept=True,
        standardize=False,
        covariance="HC3",
    ),
    multiplicity="report_all",
    missing="complete_case_by_equation",
)

study.freeze(
    scm=scm,
    analysis_plan=plan,
    evidence="Approved by researcher at design review",
)
```

The freeze should use workflow gates. Revisions create a new version rather than
silently changing a running study.

## Compiling an SCM into an experiment

```python
design = ExperimentDesign.factorial(
    factors=scm.exogenous_variables,
    replications=20,
    seed="mug-study-v1",
).sample(max_cells=200, balance="orthogonal")

compiled = ExperimentCompiler().compile(
    scm=scm,
    design=design,
    interaction=mug_conversation,
    analysis_plan=plan,
)
```

The compiler produces:

1. A treatment manifest with stable cell and replication IDs.
2. Scenario traits and role-specific agent traits.
3. Visibility capabilities for private, public, and scenario-level causes.
4. One workflow instance specification per sampled replication.
5. Prespecified post-interaction measurement steps.
6. A typed observation schema and analysis job.

It must never infer treatments from fitted outcomes. Assignment happens once,
is persisted, and is reproducible from the study seed.

## Native conversation step

A conversation is more dynamic than a conventional survey step. It produces an
ordered transcript, repeatedly assigns the right to speak, and may terminate
before its maximum length.

```python
mug_conversation = Conversation(
    name="negotiate",
    participants=[role("buyer"), role("seller")],
    protocol=OrderedTurns([role("buyer"), role("seller")]),
    prompt=ConversationPrompt(
        scenario="Negotiate the sale of a mug.",
        include_private_traits=True,
        include_other_roles=True,
        transcript_view="public_only",
        remaining_turns=True,
    ),
    stop=AnyStop(
        SemanticStop(
            judge=llm("conversation-coordinator"),
            question="Should this interaction continue?",
        ),
        MaxUtterances(20),
    ),
)

interaction = workflow.conversation(
    mug_conversation,
    assigned_to=roles("buyer", "seller"),
)
```

Each utterance is an append-only event containing speaker, public text, private
model trace reference, sequence number, timestamp, model/executor resolution,
and the transcript version observed. The conversation’s final transcript is a
typed artifact, not a concatenated string stored only in prompts.

### Serializable protocol menu

The paper’s six protocols map directly to data:

```python
OrderedTurns(order=[buyer, seller])
RandomTurns(seed="turns", no_immediate_repeat=True)
CentralOrdered(center=judge, others=[defense, prosecution])
CentralRandom(center=auctioneer, others=bidders, seed="turns")
CoordinatorBefore(coordinator=llm("coordinator"), no_immediate_repeat=True)
CoordinatorAfter(coordinator=llm("coordinator"), candidates="all_other_agents")
```

`CoordinatorBefore` asks a hidden coordinator who should speak next.
`CoordinatorAfter` privately obtains candidate responses from eligible agents,
persists them as unrealized proposals, and lets the coordinator select exactly
one. Unselected proposals remain in the audit log but never enter participants’
transcript views. They must not simply be deleted.

### Concurrency and leases

Only one transcript append may win for a given sequence number. Speaking turns
are leased work items. Submission uses an expected transcript version, making a
late or duplicated utterance fail safely. This reuses the workflow’s durable
attempt and idempotency machinery.

## Measurement

Outcome measurement is an ordinary workflow stage after the conversation:

```python
measured = workflow.measure(
    variable=deal,
    after=interaction,
    transcript=interaction.transcript,
)
```

The measurement contract should prefer typed survey questions and deterministic
aggregation. If an LLM must convert free text into a number, the raw response,
conversion prompt, converted value, model, and validation result are all stored.
An LLM conversion is a provenance-bearing work item, never an invisible parser.

The existing workflow expression DSL already supports `mean`, `median`,
`minimum`, `maximum`, `sum`, counts, lookup tables, and participant-keyed joins.
Those operators cover most of the paper’s six measurement aggregation choices;
`mode` is the only missing reduction.

## Data and fitting

```python
observations = compiled.collect(
    columns=scm.observation_schema(),
    include=["cell_id", "replication", "transcript_id", "model_id"],
)

fit = plan.fit(observations)
fit.save("mug-study/fitted-scm.ep")
```

A fitted SCM is a first-class versioned object:

```python
FittedSCM(
    specification_hash="...",
    data_manifest_hash="...",
    coefficients={"buyer_budget -> deal_occurred": 0.037},
    standard_errors={...},
    fit_statistics={...},
    estimator={...},
    exclusions={...},
)
```

The first implementation can support the paper’s linear and linear-probability
models with interactions. A later backend may add generalized linear equations,
mediation, do-calculus queries, and alternative estimators. Backend choice is
serialized in the analysis plan.

## Prediction experiments

The paper compares three distinct tasks, which should remain distinct workflow
steps:

```python
direct_y = workflow.predict_outcomes(
    scenarios=design.cells,
    evidence=None,
)

predicted_paths = workflow.predict_coefficients(
    scm=scm,
    design=design,
)

model_assisted_y = workflow.predict_outcomes(
    scenarios=design.cells,
    evidence=fit.leave_one_out(),
)
```

Leave-one-out fits are child analysis jobs keyed by held-out observation. This
prevents leakage: the fitted model shown for observation `i` must carry a data
manifest proving that `i` was excluded.

## Follow-on experiments

Follow-on design should be proposed, not silently enacted:

```python
proposal = FollowOnDesigner().propose(
    prior_scm=scm,
    fitted=fit,
    policy=RevisionPolicy(
        retain_significant_paths=True,
        propose_new_causes=3,
        permit_mediators=False,
    ),
)

workflow.step("review-follow-on", proposal.review_survey(), assigned_to=human("researcher"))
```

Approval creates SCM version 2 and a new experiment manifest linked to version
1. The audit trail distinguishes LLM proposals, human edits, and mechanically
compiled consequences.

## What EDSL already provides

- Durable dependency DAGs, conditional branches, retries, leases, and idempotency.
- Explicit human, LLM, and scripted execution channels.
- Agent roles and traits plus private output visibility.
- Serializable derived arithmetic and aggregation.
- Stable random draws, parameters, lookups, structured tables, and identity joins.
- Humanize delivery for real participants.
- Persisted transcripts can be represented as typed artifacts and visualized.

## What must be added

### Essential

1. **SCM objects:** typed variables, causal edges/equations, estimands, validation,
   and serialization.
2. **Experiment compiler:** SCM/design to treatment manifests, agents, workflow
   instances, observation schemas, and analysis jobs.
3. **Conversation runtime:** durable transcript events, six speaker protocols,
   semantic and hard stopping rules, and race-safe next-speaker assignment.
4. **Measurement contracts:** variable-to-question mappings with deterministic
   aggregation and auditable LLM conversions.
5. **Fitted SCM artifacts:** specification/data hashes, estimates, uncertainty,
   diagnostics, and prediction interfaces.

### Soon after

- `mode` reduction for measurement.
- Factorial, fractional-factorial, and sampled treatment designs.
- Treatment overlap and support diagnostics.
- Interaction terms and nonlinear basis terms in the expression DSL.
- Transcript confidentiality policies and redacted views.
- Clustered and repeated-measures analysis.
- Cost estimation before compiling large factorial designs.

## Recommended implementation slices

### Slice 1: authored SCM, scripted interaction

Implement serialized variables, equations, design matrices, measurement, and a
linear fitting backend. Use an existing fixed workflow rather than conversation.
This tests the scientific object model and provenance.

### Slice 2: two-agent ordered conversation

Add append-only transcripts, ordered turns, semantic stopping, and a hard cap.
Reproduce the mug negotiation with an authored SCM.

### Slice 3: SCM-to-experiment compiler

Generate treatment cells, role-specific agent traits, measurements, and parallel
workflow launches. Fit the prespecified SCM.

### Slice 4: automated scientist

Use LLM steps to propose roles, variables, operationalizations, treatments, and
protocols. Put a review/freeze gate after every scientific commitment.

### Slice 5: richer interaction and prediction

Add all six protocols, coefficient prediction, direct outcome prediction,
leakage-safe leave-one-out model-assisted prediction, and follow-on proposals.

## First pilot

The mug negotiation is the best first pilot because it uses two roles, ordered
turns, private individual treatments, a binary outcome, and a simple linear SCM.
The acceptance criterion should be stronger than “the conversations ran”:

1. The complete study round-trips through JSON before execution.
2. Every treatment assignment is stable and auditable.
3. Buyer and seller see only authorized attributes.
4. A resumed conversation produces no duplicate utterance.
5. The semantic judge or hard cap always terminates the interaction.
6. Measurements retain raw answers and conversion provenance.
7. The fitted model references the frozen specification and exact data manifest.
8. Re-running analysis from those artifacts reproduces coefficients exactly.

That pilot would establish the reusable substrate. Bail hearings, interviews,
and auctions would then test central-agent protocols, larger role sets, and
interaction-specific measurements without changing the SCM core.
