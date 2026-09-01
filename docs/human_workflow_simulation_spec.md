---
title: "Dependency-Aware Human Workflows and Agent Simulation"
subtitle: "A shared execution model for real respondents and simulated inbox-driven agents"
author: "Expected Parrot"
date: "August 2026"
lang: en-US
documentclass: report
papersize: letter
fontsize: 11pt
geometry:
  - margin=0.85in
colorlinks: true
linkcolor: MidnightBlue
urlcolor: MidnightBlue
toc: true
toc-depth: 2
numbersections: true
---

# Status

This document is both the target specification and the design record for an
initial local vertical slice. The current `edsl.workflows` implementation
includes serializable workflow/step definitions, fixed participant selection,
ordered dependencies, SQLite work items/events/submissions/outbox storage,
shared-state reads and writes, idempotent submission, a delivery adapter port,
and virtual-clock EDSL-agent simulation. Later sections explicitly identify
production features that remain, including conditional predicates, deadlines,
replacement policies, and a remote Coop coordinator.

The normative terms **MUST**, **SHOULD**, and **MAY** have their usual RFC-style
meaning.

# Executive summary

EDSL currently has two useful but separate execution models:

1. The local runner executes AI-agent interviews and can impose serial or
   round-based schedules.
2. Humanize creates surveys, respondents, deliveries, schedules, and callbacks
   for real people.

Neither model is sufficient for a long-lived workflow in which one participant's
submission enables another participant's work. A human may take hours or days to
respond, so the system cannot hold a worker or interview open. A command
`require` expression can protect state integrity, but it does not suspend and
wake a participant. A serial interview schedule can enforce fixed ordering for
AI runs, but it serializes too much work and does not represent durable human
eligibility.

This specification introduces `HumanWorkflow`, a serializable workflow graph
whose work items become eligible from shared-state predicates. The workflow
engine persists eligibility, renders only authorized state, accepts idempotent
submissions, commits shared-state transitions, and activates downstream work.

The same workflow is executed through two adapters:

- `HumanizeWorkflowAdapter` sends real email/SMS/web deliveries and accepts
  browser submissions.
- `AgentWorkflowSimulator` uses a virtual clock, simulated inboxes, and EDSL
  agents while exercising the same open/render/submit APIs.

The simulator is therefore an end-to-end rehearsal of the human workflow, not a
separate approximation of its control flow.

# Proposed API quick tour

The proposal has three layers. Each layer answers a different question:

| Layer | Proposed API | Responsibility |
|---|---|---|
| Domain state | `Machine`, `SharedStateMap` | What facts exist and which transitions are legal? |
| Workflow | `HumanWorkflow`, `HumanStep` | Who may do what, and when does their work become ready? |
| Execution adapter | `HumanizeWorkflowAdapter`, `AgentWorkflowSimulator` | Who receives the task and how is the response collected? |

The central execution cycle is:

```text
state changes
    |
    v
ready_when predicates are reevaluated
    |
    v
newly eligible work items become ready
    |
    v
an invitation enters the delivery outbox
    |
    +-----------------------------+
    |                             |
    v                             v
real email/SMS              simulated inbox
    |                             |
    +-------------+---------------+
                  v
          participant opens task
                  |
                  v
       authorized state is rendered
                  |
                  v
          participant submits
                  |
                  v
      state command commits atomically
                  |
                  +---- turns the crank again
```

## API 1: define legal state transitions

The machine is independent of humans, email, and AI models:

```python
sequence_machine = Machine(
    name="DependentAnswers",
    fields={
        "first_answer": state_field(T.optional(T.text()), None),
        "second_answer": state_field(T.optional(T.text()), None),
    },
    commands={
        "submit_first": Command(
            inputs={"answer": T.text()},
            effects=(set_once("first_answer", input_("answer")),),
        ),
        "submit_second": Command(
            inputs={"answer": T.text()},
            require=field("first_answer") != None,
            effects=(set_once("second_answer", input_("answer")),),
        ),
    },
    view={
        "first_answer": field("first_answer"),
        "second_answer": field("second_answer"),
    },
    complete_when=field("second_answer") != None,
)
```

The `require` expression is the final safety check. It does not send an
invitation or make a participant wait.

## API 2: define participant eligibility and work

`HumanStep.ready_when` is what turns a state fact into durable work eligibility:

```python
workflow = HumanWorkflow(
    name="dependent-answer-workflow",
    state=states,
    steps=[
        HumanStep(
            name="first_response",
            assignee=ParticipantSelector.role("first"),
            survey=first_survey,
            writes=[sequence.submit_first(answer=first.answer)],
            delivery=DeliveryPolicy.email(on="ready"),
        ),
        HumanStep(
            name="second_response",
            assignee=ParticipantSelector.role("second"),
            ready_when=sequence.condition(
                field("first_answer") != None
            ),
            reads=[sequence.read()],
            survey=second_survey,
            writes=[sequence.submit_second(answer=second.answer)],
            delivery=DeliveryPolicy.email(on="ready"),
        ),
    ],
    complete_when=sequence.is_complete(),
)
```

At launch, `first_response` is `ready` and `second_response` is `blocked`.
Completing the first item commits `first_answer`, which makes the second item
ready and queues its invitation.

## API 3: choose humans or simulated respondents

Production execution binds the workflow to Humanize respondents and routes:

```python
run = HumanizeWorkflowAdapter(
    workflow=workflow,
    participants=human_respondents,
    delivery_routes=[respondent_email_route],
).launch()
```

Simulation binds the same frozen workflow to EDSL agents and a virtual inbox:

```python
simulation = AgentWorkflowSimulator(
    workflow=workflow,
    participants=agent_list,
    model=model,
    inbox=SimulatedInbox(),
    clock=VirtualClock(start="2026-09-01T09:00:00Z"),
    behavior=RespondentBehavior.immediate_and_reliable(),
    seed=1234,
)

result = simulation.run(
    until=workflow.is_complete(),
    max_events=10_000,
)
```

The simulator does not call machine commands directly. A simulated agent must
receive a message, open its task, view the rendered survey, answer it, and submit
through the same coordinator contract used by a human browser.

## What exists today versus what is proposed

| Capability | Current repository | Proposed here |
|---|---:|---:|
| Typed shared-state machines and commands | Yes | Reused unchanged |
| Explicit state reads and answer-bound writes | Yes | Reused unchanged |
| Local serial/concurrent AI interview schedules | Yes | Still supported |
| Humanize respondents, links, deliveries, schedules, callbacks | Yes | Used by adapter |
| Durable dependency-aware human work items | No | `HumanStep` instances |
| State-based participant readiness | No | `ready_when` |
| Waiting pages and revocable task capabilities | No | Coordinator/browser contract |
| Virtual inbox and virtual clock | No | Simulation adapter |
| One workflow definition for humans and agents | No | Primary acceptance criterion |

# Goals

The design MUST:

1. Express dependencies such as “reviewer B becomes eligible after reviewer A
   submits” and “adjudication becomes eligible after two conflicting reviews.”
2. Preserve valid parallelism: unrelated ready work runs concurrently.
3. Persist workflow progress across process restarts and arbitrarily long human
   delays.
4. Use the same workflow definition for humans and simulated AI respondents.
5. Keep shared-state machines authoritative for domain state and transition
   invariants.
6. Keep workflow scheduling authoritative for eligibility, assignment, delivery,
   deadlines, and failure policy.
7. Recheck authorization and readiness when a submission commits.
8. Make retries and duplicate delivery/submission requests idempotent.
9. Expose a complete audit trail sufficient to reproduce why work became ready,
   blocked, expired, or completed.
10. Support serialization and remote execution without arbitrary Python callbacks.
11. Preserve privacy by rendering only the state view authorized for the current
    work item and participant.
12. Detect deadlocks and terminally blocked workflows.

# Non-goals

The first implementation does not need to:

- implement a general business-process notation language;
- allow arbitrary Python callbacks in eligibility expressions;
- provide exactly-once email delivery (submission and state effects are
  idempotent; transport delivery is at least once);
- infer a workflow graph from natural-language prompts;
- model a human continuously observing state;
- let AI respondents poll for work;
- support editing an upstream response after dependent work has completed unless
  the workflow explicitly declares a revision policy;
- replace existing one-shot Humanize surveys or local `InterviewSchedule` runs.

# Design principles

## State facts and workflow control are separate

A `Machine` defines domain facts and legal transitions. A `HumanWorkflow`
defines who may perform which work, when it becomes eligible, and what happens
when it is not completed.

For example, `field("draft") != None` can appear in both places for different
reasons:

- as a workflow `ready_when` predicate, it controls whether a reviewer receives
  and can open a task;
- as a command `require` predicate, it protects the state transition against
  stale pages, races, forged requests, and programming errors.

The two checks are intentionally redundant. Eligibility provides orchestration
and a good participant experience. Command requirements provide transactional
safety.

## Humans do not wait inside a process

Blocked work is a durable row with status `blocked`. No worker, request, model
call, or browser session remains open. A committed event causes the coordinator
to reevaluate affected predicates and atomically mark newly eligible work
`ready`.

## Deliveries announce work; they do not define work

An email contains a capability URL or task identifier. It is not the
authoritative survey payload. Opening the URL rechecks eligibility and renders a
fresh authorized view. Delayed or duplicated email cannot bypass workflow state.

## Simulated agents react to deliveries

An AI respondent MUST NOT poll shared state or choose when to act. It receives a
simulated delivery, opens the referenced task through the normal workflow API,
and submits through the normal submission API. This preserves the causal model
experienced by humans.

## Every decision is serializable

Selectors, predicates, timing policies, retry policies, and adapter configuration
compile to versioned data. Runtime services may use code internally, but workflow
authors do not need arbitrary callbacks for the normal path.

# Conceptual model

```text
HumanWorkflow
+-- workflow definition
|   +-- participant roles and selectors
|   +-- work-item templates
|   +-- state bindings
|   +-- readiness and completion predicates
|   +-- delivery, deadline, and failure policies
|
+-- workflow instance (one study/group/case)
    +-- participant bindings
    +-- shared-state scope(s)
    +-- work-item instances
    +-- submissions
    +-- delivery outbox
    +-- event log
    +-- timers
```

The principal terms are:

- **Workflow definition**: immutable, serializable authoring object.
- **Workflow instance**: one durable execution of a definition.
- **Participant**: a human respondent or simulated EDSL agent with a stable ID,
  traits, roles, and delivery endpoints.
- **Work-item template**: declarative definition of a step.
- **Work-item instance**: a template bound to a workflow instance, participant,
  and optional iteration/key.
- **Eligibility**: whether a work item is allowed to become `ready`.
- **Capability**: an opaque, revocable credential granting access to one work
  item for one participant.
- **Submission**: a versioned attempt to answer a work item.
- **Outbox event**: a durable request to deliver a notification after the
  transaction that created it commits.
- **Adapter**: implementation of delivery and respondent behavior.

# Authoring API

## Minimal sequential example

```python
from edsl import QuestionFreeText, Survey
from edsl.sharedstate import (
    Command, Machine, SharedState, SharedStateMap, T,
    field, input_, set_once, state_field,
)
from edsl.workflows import (
    HumanWorkflow, HumanStep, ParticipantSelector,
    DeliveryPolicy, DeadlinePolicy,
)

sequence_machine = Machine(
    name="DependentAnswers",
    constants={},
    fields={
        "first_answer": state_field(T.optional(T.text()), None),
        "second_answer": state_field(T.optional(T.text()), None),
    },
    commands={
        "submit_first": Command(
            inputs={"answer": T.text()},
            effects=(set_once("first_answer", input_("answer")),),
        ),
        "submit_second": Command(
            inputs={"answer": T.text()},
            require=field("first_answer") != None,
            effects=(set_once("second_answer", input_("answer")),),
        ),
    },
    view={
        "first_answer": field("first_answer"),
        "second_answer": field("second_answer"),
    },
    complete_when=field("second_answer") != None,
)

states = SharedStateMap(
    SharedState(sequence=sequence_machine),
    state_id="dependent-answer-study",
)
sequence = states.by_current_instance().sequence

first = QuestionFreeText(
    question_name="answer",
    question_text="Give the initial answer.",
)
second = QuestionFreeText(
    question_name="answer",
    question_text=(
        "The first participant answered: "
        "{{ shared_state.sequence.first_answer }}. Give your response."
    ),
)

workflow = HumanWorkflow(
    name="dependent-answer-workflow",
    state=states,
    steps=[
        HumanStep(
            name="first_response",
            assignee=ParticipantSelector.role("first"),
            survey=Survey([first]),
            writes=[sequence.submit_first(answer=first.answer)],
            delivery=DeliveryPolicy.email(on="ready"),
        ),
        HumanStep(
            name="second_response",
            assignee=ParticipantSelector.role("second"),
            ready_when=sequence.condition(field("first_answer") != None),
            reads=[sequence.read()],
            survey=Survey([second]),
            writes=[sequence.submit_second(answer=second.answer)],
            delivery=DeliveryPolicy.email(on="ready"),
        ),
    ],
    complete_when=sequence.is_complete(),
)
```

Names above are proposed APIs. `by_current_instance()` means that the workflow
instance supplies the concrete shared-state scope; an explicit serializable
scope reference may be used instead.

## `HumanWorkflow`

Proposed constructor:

```python
HumanWorkflow(
    name: str,
    steps: Sequence[HumanStep],
    state: SharedStateMap | Sequence[SharedStateMap],
    complete_when: WorkflowCondition | StateCondition | None = None,
    on_deadlock: DeadlockPolicy = DeadlockPolicy.fail(),
    metadata: Mapping[str, JSONValue] | None = None,
)
```

Normative behavior:

- `name` MUST be a stable nonempty identifier.
- Step names MUST be unique.
- The workflow MUST be serializable before it is launched.
- All state references MUST resolve to declared state bindings.
- Every answer reference in a write MUST refer to a question in that step.
- A workflow MUST reject statically detectable dependency cycles unless a cycle
  contains a timer, retry, or explicit iterative transition that can make
  progress.
- `complete_when` SHOULD be explicit. If omitted, completion means every
  non-optional instantiated work item is terminal and no future work can be
  generated.
- Definition serialization MUST exclude runtime participant records,
  submissions, and state snapshots.

## `HumanStep`

```python
HumanStep(
    name: str,
    assignee: ParticipantSelector,
    survey: Survey,
    ready_when: WorkflowCondition | StateCondition | None = None,
    reads: Sequence[StateRead] = (),
    writes: Sequence[StateWrite] = (),
    cardinality: StepCardinality = StepCardinality.one_per_assignee(),
    delivery: DeliveryPolicy | None = None,
    deadline: DeadlinePolicy | None = None,
    retry: RetryPolicy = RetryPolicy.default(),
    failure: FailurePolicy = FailurePolicy.block_dependents(),
    revision: RevisionPolicy = RevisionPolicy.immutable_after_submit(),
    visibility: VisibilityPolicy = VisibilityPolicy.public_view(),
    optional: bool = False,
    metadata: Mapping[str, JSONValue] | None = None,
)
```

`ready_when=None` means initially eligible after assignment. Readiness is a pure
predicate over durable workflow metadata, participant bindings, timers, and
authoritative shared state. It MUST NOT make network calls or mutate state.

`reads` specify which state snapshots are available while rendering. Merely
mentioning a field in Jinja does not grant visibility.

`writes` are resolved from validated answers and committed only after the
submission transaction passes its final eligibility check.

## Participant selectors

Selectors bind templates to participants without embedding database queries or
callbacks:

```python
ParticipantSelector.role("reviewer")
ParticipantSelector.trait("team_id", equals=current.instance.team_id)
ParticipantSelector.all_of(
    ParticipantSelector.role("reviewer"),
    ParticipantSelector.trait("seniority", in_=("senior", "lead")),
)
ParticipantSelector.named("alice")
ParticipantSelector.unassigned_pool("replacement-reviewers")
```

Initial implementation SHOULD support exact role, stable participant ID, and
equality filters over declared traits. Richer selection can be added without
changing work-item semantics.

Assignment occurs separately from eligibility:

- an assigned blocked item has an owner but cannot yet be opened;
- an unassigned ready item can be claimed from a pool;
- a replacement policy may revoke one assignment and create another.

## Conditions

Conditions MUST be typed, serializable expression trees. Required operands:

- state field comparisons and collection operations already supported by the
  shared-state DSL;
- work-item status and count operations;
- submission counts and selected answer values where explicitly exposed;
- participant and workflow-instance metadata;
- timer/deadline predicates;
- boolean composition.

Examples:

```python
step("review_a").is_completed()
completed(role="reviewer", key=current.paper.id).count() >= 2
state.screening.reviews.length() >= 2
timer("review_deadline").is_due()
```

Conditions MUST declare their dependency keys so the coordinator can reevaluate
only affected work instead of scanning every item after every event.

# Runtime state model

## Work-item statuses

Every work-item instance has exactly one status:

```text
planned     Template is known but participant/key expansion is incomplete.
blocked     Assigned or instantiated, but ready_when is false.
ready       Eligible to open; delivery may be pending.
notified    At least one delivery was accepted by an adapter.
in_progress Participant opened the item or saved a draft.
submitting  A submission transaction is being processed.
completed   A valid submission and all required writes committed.
expired     Deadline policy made the item terminal.
cancelled   Administrator or workflow policy cancelled it.
failed      Non-retryable processing failure.
superseded  A replacement or revision policy replaced this instance.
```

`ready`, `notified`, and `in_progress` are all eligible states. A participant
opening an item may transition `ready -> in_progress` directly if notification
tracking is disabled.

Terminal statuses are `completed`, `expired`, `cancelled`, `failed`, and
`superseded`. Whether a terminal non-completion satisfies dependents is an
explicit failure policy, never an implicit assumption.

## Required persistent records

The storage model MUST include logical equivalents of:

### Workflow instance

```text
workflow_instance_id
definition_id and definition_version
status
created_at, started_at, completed_at
instance metadata
state bindings
current event sequence
```

### Participant binding

```text
workflow_instance_id
participant_id
role(s)
traits or trait reference
delivery endpoints
adapter type
consent/activation status
```

### Work-item instance

```text
work_item_id
workflow_instance_id
step_name
participant_id or pool_id
logical key / iteration
status and status reason
eligibility version
state read versions
attempt count
deadline and reminder metadata
capability generation
created_at, ready_at, opened_at, completed_at
```

### Submission

```text
submission_id
work_item_id
attempt number
idempotency key
render version / eligibility version
raw response
validated response
validation status
state write IDs and resulting authoritative versions
created_at, committed_at
```

### Outbox record

```text
outbox_id
workflow_instance_id
work_item_id
event type
adapter and route
payload reference
deduplication key
available_at
attempt count
status
last error
```

### Audit event

```text
sequence
event_id
workflow_instance_id
event type
actor type and actor ID
causation_id and correlation_id
subject IDs
redacted payload
timestamp
```

# Coordinator semantics

## Launch

Launching a workflow MUST:

1. Validate and freeze the serialized definition.
2. Bind participants and shared-state scopes.
3. Expand statically known work-item instances.
4. Evaluate initial readiness in one transaction.
5. Create `ready` and `blocked` records.
6. Insert delivery outbox records for newly ready work.
7. Commit before any adapter sends a message.

Launch is idempotent under a caller-supplied idempotency key.

## Eligibility evaluation

Eligibility is level-triggered, not edge-triggered. If `ready_when` is true, the
item is eligible regardless of whether the coordinator observed the exact event
that first made it true. This makes recovery after downtime straightforward.

The coordinator MUST reevaluate an item when one of its declared dependency keys
changes. It SHOULD also provide a repair scan that recomputes all nonterminal
items and reports drift.

The transition `blocked -> ready` and insertion of the initial delivery outbox
record MUST occur atomically. Repeated evaluation MUST NOT create duplicate
logical deliveries.

An item that becomes ineligible after reaching `ready` follows its declared
revocation policy. The safe default is to revoke the current capability,
transition back to `blocked`, and reject stale submissions.

## Open and render

Opening a capability MUST:

1. Authenticate or validate the opaque capability.
2. Confirm that it is bound to the participant and work item.
3. Confirm that the capability generation is current and not revoked.
4. Reevaluate readiness against authoritative state.
5. If blocked, return a stable waiting/status page with no protected survey
   content.
6. Resolve declared state reads and record their versions.
7. Render the survey using only the authorized state view.
8. Record a render/eligibility version used for optimistic submission checks.

A blocked response SHOULD distinguish `waiting`, `expired`, `cancelled`, and
`already_completed`, without disclosing private dependency details.

## Drafts

Draft saving MAY be supported. Draft writes:

- do not execute domain state commands;
- are idempotent and versioned;
- do not activate dependent work;
- remain subject to capability and participant authorization;
- may be deleted according to retention policy.

## Submit

Submission processing MUST use a transaction with the following logical steps:

1. Deduplicate by `(work_item_id, idempotency_key)`.
2. Lock or compare-and-swap the work-item eligibility version.
3. Reauthenticate the participant/capability.
4. Reevaluate `ready_when` against authoritative state.
5. Validate the submitted survey answers against the exact rendered question
   definitions when required.
6. Resolve declared state writes from validated answers and runtime context.
7. Apply writes using stable state idempotency keys.
8. Authoritatively reread required state because shared-state write outcomes are
   advisory and a false machine `require` may produce a no-op transition.
9. Verify the step's declared success postcondition, or at minimum that all
   required effects are present.
10. Mark the work item `completed` and store the submission.
11. Append audit events.
12. Reevaluate directly affected work items.
13. Insert new delivery/timer outbox records.
14. Commit.

If a machine requirement produces a no-op, the workflow layer MUST NOT silently
mark the item completed unless the declared postcondition is already satisfied.
It returns a stable conflict result such as `STATE_PRECONDITION_CHANGED`, then
either rerenders, blocks, or applies the step's retry policy.

## Completion

After every successful transition the coordinator evaluates workflow completion.
When complete it MUST:

- atomically mark the workflow instance completed;
- revoke outstanding capabilities that cannot be used after completion;
- cancel unnecessary reminders and timers;
- optionally finalize scoped machines using typed `StateCondition` objects;
- enqueue completion callbacks through the outbox;
- retain the audit trail and final state references.

# Delivery system

## Adapter protocol

```python
class WorkflowDeliveryAdapter(Protocol):
    adapter_name: str

    def deliver(self, message: DeliveryMessage) -> DeliveryReceipt: ...
    def cancel(self, receipt_id: str) -> None: ...
```

Adapters are called only by an outbox worker after the creating transaction
commits. A delivery receipt means the adapter accepted the request, not that the
human read it.

Required initial adapters:

- Humanize respondent email;
- Humanize respondent link without proactive email;
- simulated inbox;
- no-op/test capture adapter.

SMS and external task-market adapters may follow.

## Delivery message

```python
DeliveryMessage(
    message_id: str,
    workflow_instance_id: str,
    work_item_id: str,
    participant_id: str,
    kind: Literal["invitation", "reminder", "replacement", "cancellation"],
    subject: str | None,
    template_id: str,
    template_context: Mapping[str, JSONValue],
    capability_url: str,
    available_at: datetime,
    expires_at: datetime | None,
    deduplication_key: str,
)
```

Sensitive shared state SHOULD NOT be copied into delivery payloads. The normal
message points to the task, whose content is rendered at open time.

## Delivery guarantees

- Outbox processing is at least once.
- Logical messages are deduplicated by a stable key.
- Providers may still produce duplicate email; opening either copy reaches the
  same idempotent task.
- Delivery failures do not roll back workflow readiness.
- Retry and terminal-delivery-failure policies are explicit.

# Deadlines, reminders, and replacement

Example policy:

```python
DeadlinePolicy(
    due_after="72 hours",
    reminders=["24 hours", "48 hours"],
    on_due=FailurePolicy.assign_replacement(pool="backup-reviewers"),
)
```

Timers are durable scheduled events interpreted against an injected clock.
Production uses UTC wall time. Simulation uses a virtual clock.

Supported first-version terminal policies SHOULD include:

- `block_dependents`;
- `skip_and_satisfy` for explicitly optional work;
- `fail_workflow`;
- `assign_replacement`;
- `route_to(step_name)` for adjudication or manual intervention;
- `cancel_scope` for one group/case without cancelling the full study.

Policies MUST state whether the original capability remains valid and whether a
late response can supersede a replacement.

# Revisions and invalidation

The default is immutable completion. Allowing an upstream human to revise after
downstream activation creates a new causal branch and cannot be treated as an
ordinary resubmission.

Supported policies:

```python
RevisionPolicy.immutable_after_submit()
RevisionPolicy.allow_until_dependents_open()
RevisionPolicy.versioned(
    downstream="invalidate_unstarted",
    completed_downstream="manual_review",
)
```

A versioned revision MUST:

- preserve the original submission and state history;
- increment the work-item result version;
- identify affected downstream work;
- revoke stale capabilities where policy permits;
- never silently erase completed human work;
- record the invalidation decision in the audit log.

# Humanize integration

## Relationship to current Humanize objects

The workflow layer SHOULD reuse existing Humanize capabilities:

- human survey rendering and schemas;
- respondent and agent-list records;
- personal respondent links;
- delivery routes and templates;
- scheduled deliveries;
- callbacks;
- response export.

It MUST NOT model a multi-step workflow as one ordinary Humanize respondent
completion flag. A workflow work item needs its own durable identity and status.

Proposed service resources:

```text
human_workflow_definition
human_workflow_instance
human_workflow_participant
human_work_item
human_work_item_submission
human_workflow_delivery
human_workflow_event
```

A work item may internally create or reference a Humanize survey session, but the
workflow service remains authoritative about whether that session can be opened
or submitted.

## Browser behavior

Participant URLs resolve to one of:

- ready survey;
- waiting page;
- completed receipt;
- expired/cancelled page;
- replacement/superseded notice;
- authentication error.

Waiting pages MAY offer an opt-in notification when work becomes ready. They MUST
not expose the names, answers, or detailed status of prerequisite participants
unless the workflow's visibility policy explicitly allows it.

## Callbacks

Workflow callbacks SHOULD include:

```text
human_workflow.instance.started
human_workflow.work_item.ready
human_workflow.work_item.opened
human_workflow.work_item.completed
human_workflow.work_item.expired
human_workflow.instance.blocked
human_workflow.instance.completed
```

Callbacks use the same outbox and deduplication rules as deliveries.

# Agent workflow simulation

## Purpose

The simulator validates orchestration and participant experience before a real
launch. It can also generate pilot data, estimate completion time, test reminder
strategies, and reproduce race/failure cases.

It MUST run the same frozen workflow definition and coordinator semantics as the
human adapter. A simulator that directly calls machine commands or skips task
open/render/submit is not conforming.

## Proposed API

```python
from edsl.workflows.simulation import (
    AgentWorkflowSimulator,
    SimulatedInbox,
    VirtualClock,
    RespondentBehavior,
)

simulation = AgentWorkflowSimulator(
    workflow=workflow,
    participants=agent_list,
    model=model,
    inbox=SimulatedInbox(),
    clock=VirtualClock(start="2026-09-01T09:00:00Z"),
    behavior=RespondentBehavior(
        open_delay={"distribution": "lognormal", "median": "20 minutes"},
        completion_delay={"distribution": "lognormal", "median": "8 minutes"},
        open_probability=0.95,
        completion_probability=0.90,
        reminder_open_probability=0.35,
    ),
    seed=1234,
)

result = simulation.run(
    until=workflow.is_complete(),
    max_events=10_000,
    max_virtual_time="30 days",
)
```

## Simulator event loop

The simulator owns a priority queue ordered by `(virtual_time, sequence)`. The
sequence tie-breaker makes equal-time behavior deterministic.

```text
launch workflow
enqueue outbox deliveries and timers

while queue is not empty:
    advance virtual clock to next event
    dispatch all coordinator timers due at that instant
    deliver due messages to simulated inboxes
    schedule opens according to respondent behavior
    on open, call workflow.open_task(...)
    schedule completion according to behavior
    on completion, ask EDSL Agent to answer rendered Survey
    call workflow.submit(...)
    enqueue downstream outbox/timer events
    stop on completion, declared limit, or deadlock
```

The simulator MUST NOT sleep in wall-clock time.

## Simulated inbox

Each participant has a persistent ordered inbox:

```python
InboxMessage(
    message_id="msg-1",
    recipient_id="bob",
    delivered_at=clock.now,
    kind="invitation",
    work_item_id="item-2",
    capability="opaque-simulation-capability",
    read_at=None,
)
```

The inbox is part of simulation state and audit output. Messages may be delayed,
duplicated, lost, opened, ignored, or acted on according to the configured
behavior model.

## Agent answering semantics

When a simulated respondent opens an eligible task:

1. The coordinator renders the task through the normal state-read and visibility
   path.
2. The adapter constructs a normal EDSL job from the rendered Survey, bound
   participant Agent, scenario, and configured model.
3. Only that task's survey is answered. The agent does not receive future steps.
4. Stable participant traits and optional prior personal transcript/memory are
   included according to policy.
5. The validated result is submitted through the normal workflow endpoint.

The simulation SHOULD support two memory modes:

- `task_local`: only traits and the current task are visible;
- `participant_history`: the participant's own prior prompts, answers, and
  deliveries are available, subject to privacy policy.

Shared state is never added to agent memory unless exposed through declared
reads and views.

## Behavior model

Behavior is separate from respondent substantive traits. Required deterministic
test behavior:

```python
RespondentBehavior.immediate_and_reliable()
```

Optional stochastic fields:

- delivery latency;
- open delay;
- completion delay;
- probability of opening initial invitations and reminders;
- abandonment after opening;
- invalid-answer probability;
- duplicate-submit probability;
- stale-page delay;
- late-response probability;
- channel preference;
- availability windows and timezone.

Every stochastic decision MUST be derived from a recorded seed context containing
at least workflow instance, work item, participant, event kind, and attempt. Adding
unrelated participants MUST NOT perturb existing participants' random draws.

## Simulation result

```python
WorkflowSimulationResult(
    workflow_definition,
    final_instance,
    participants,
    work_items,
    submissions,
    shared_state,
    deliveries,
    events,
    metrics,
    termination,
    seed,
)
```

Required termination reasons:

- `completed`;
- `deadlocked`;
- `max_events`;
- `max_virtual_time`;
- `failed`;
- `cancelled`.

The result MUST serialize durably and SHOULD integrate with EDSL `Results` by
either embedding workflow provenance or providing a lossless conversion of
completed survey submissions.

# Concurrency and consistency

## Atomicity boundary

For one submission, the following are one logical transaction:

- submission deduplication;
- work-item eligibility/version check;
- shared-state transition application or durable linkage to its transaction;
- work-item completion;
- downstream eligibility changes;
- outbox insertion;
- audit append.

If shared state and workflow metadata cannot share one database transaction, the
implementation MUST use a recoverable saga with stable operation IDs and a
reconciler. It MUST NOT mark a work item completed before the required state
effect is durably recoverable.

## Optimistic concurrency

Rendered tasks include an opaque render version. Submission compares that version
against current work-item eligibility and relevant state versions. A mismatch
does not always require rejection: the workflow may declare that unrelated state
changes are harmless. The safe default is rerender/reconfirm.

## Fan-out

One completion may activate many work items. All newly ready rows and logical
outbox messages are created in one coordinator transaction, then delivered in
parallel.

## Fan-in

Readiness predicates can depend on counts or state aggregates. Simultaneous final
prerequisite submissions may both reevaluate the dependent item; compare-and-swap
and delivery deduplication guarantee one transition to `ready` and one logical
invitation.

# Failure handling

## Failure classes

The runtime distinguishes:

- validation failure: participant can usually correct and resubmit;
- stale eligibility/state: rerender, block, or conflict;
- transient model/provider failure in simulation: retry according to policy;
- transient delivery failure: outbox retry;
- terminal delivery failure: replacement/escalation policy;
- participant timeout: deadline policy;
- machine precondition no-op: workflow conflict unless postcondition already
  holds;
- coordinator failure: transaction rollback and retry;
- definition error: fail before launch;
- deadlock: explicit terminal or intervention state.

## Deadlock detection

A workflow instance is deadlocked when:

1. it is not complete;
2. it has no eligible nonterminal work;
3. it has no pending timer, retry, delivery capable of changing state, or
   unassigned claimable work;
4. no in-flight submission can commit.

Deadlock output MUST identify blocked work and sanitized predicate explanations.
Production may route deadlocks to manual intervention. Simulation terminates with
`deadlocked` unless configured otherwise.

## Retries

Retries preserve stable logical operation IDs but increment attempt numbers.
Model calls may execute more than once; only one validated submission is committed
for an idempotency key. Retry budgets and backoff use the injected clock.

# Privacy and security

The implementation MUST:

- use opaque, high-entropy capabilities or authenticated participant sessions;
- bind capabilities to workflow, work item, participant, and generation;
- support revocation on cancellation, replacement, invalidation, and completion;
- evaluate readiness server-side at both open and submit;
- never trust participant-supplied role, scope, work-item, or state version;
- derive state scopes from server-side participant/instance bindings;
- render only declared state reads and visibility views;
- keep private machine fields out of prompt, browser, delivery, callback, and
  ordinary audit payloads;
- encrypt or appropriately protect contact endpoints and raw responses;
- redact secrets and personal data from logs;
- separate administrator, coordinator, participant, and simulation credentials;
- record consent and retention metadata for real-human runs.

Simulation capabilities are not production credentials. Simulation output SHOULD
use synthetic contact endpoints by default.

# Observability and audit

## Event vocabulary

Required events include:

```text
workflow.created
workflow.started
participant.bound
work_item.created
work_item.blocked
work_item.ready
delivery.queued
delivery.accepted
delivery.failed
work_item.opened
submission.received
submission.validation_failed
submission.conflicted
state.write_committed
work_item.completed
work_item.expired
work_item.replaced
workflow.deadlocked
workflow.completed
workflow.failed
```

Events have monotonic per-instance sequence numbers and causal links. Replayed or
duplicate operations MAY append a deduplication observation but MUST NOT duplicate
domain effects.

## Timeline

Both adapters SHOULD expose the same bounded timeline representation:

```text
09:00  workflow started
09:00  Alice/first_response became ready
09:00  invitation queued for Alice
09:01  invitation delivered
09:18  Alice opened first_response
09:25  Alice submitted
09:25  sequence.first_answer committed at version 1
09:25  Bob/second_response became ready
09:26  invitation delivered to Bob
09:44  Bob submitted
09:44  workflow completed
```

## Metrics

Required metrics:

- counts by work-item status;
- readiness-to-delivery, delivery-to-open, open-to-submit, and total cycle time;
- reminder and replacement counts;
- validation and conflict rates;
- completion and dropout rates by step and declared cohort;
- deadlock count;
- state transition count;
- simulation model calls, tokens, and cost;
- virtual and wall-clock runtime.

# Serialization

Every new authoring object MUST use a versioned tagged representation. Example:

```json
{
  "type": "human_workflow",
  "version": 1,
  "name": "dependent-answer-workflow",
  "state_bindings": [],
  "steps": [],
  "complete_when": null,
  "deadlock_policy": {"type": "fail"},
  "metadata": {}
}
```

Runtime snapshots use separate schemas and MUST include definition identity.
Definition equality must not depend on generated UUIDs, timestamps, provider
receipts, or current state.

Round-trip tests are required for:

- workflow definitions;
- all selectors and conditions;
- delivery/deadline/failure/revision policies;
- participant bindings;
- work-item records;
- simulation configuration and results;
- historical version migration.

# Proposed CLI

The CLI follows the JSON-envelope conventions used by `ep`.

```bash
ep workflow-human validate workflow.json
ep workflow-human inspect workflow.ep
ep workflow-human launch workflow.ep --participants participants.ep
ep workflow-human status <instance_uuid>
ep workflow-human items <instance_uuid> --status blocked --page 1 --page_size 50
ep workflow-human events <instance_uuid> --after 0 --page_size 100
ep workflow-human cancel <instance_uuid> --yes
ep workflow-human intervene <instance_uuid> --action assign-replacement --item <id>

ep workflow-human simulate workflow.ep \
  --agents agents.ep \
  --model gpt-4o-mini \
  --seed 1234 \
  --max-events 10000 \
  --output simulation-results.ep
```

The final command name may instead be nested under `ep humanize workflow`; the
object model and service semantics do not depend on that naming choice.

Blocking simulation runs MUST require `--output`. Long simulations SHOULD support
background submission and later result retrieval, consistent with `ep run`.

# Python service boundaries

Suggested package layout:

```text
edsl/workflows/
    definition.py       HumanWorkflow, HumanStep
    conditions.py       typed eligibility expressions
    selectors.py        participant selectors
    policies.py         delivery/deadline/failure/revision policies
    serialization.py
    validation.py
    coordinator.py      state transitions and readiness
    stores.py            workflow persistence protocols
    events.py
    adapters/
        base.py
        humanize.py
        simulated_inbox.py
        capture.py
    simulation/
        simulator.py
        clock.py
        behavior.py
        inbox.py
        result.py
```

Core protocols:

```python
class WorkflowStore(Protocol):
    def launch(...) -> WorkflowInstance: ...
    def transact_submission(...) -> SubmissionOutcome: ...
    def claim_due_outbox(...) -> list[OutboxRecord]: ...
    def append_event(...) -> WorkflowEvent: ...
    def snapshot(...) -> WorkflowSnapshot: ...

class WorkflowClock(Protocol):
    def now(self) -> datetime: ...

class WorkflowRespondentAdapter(Protocol):
    def on_delivery(self, message: DeliveryMessage) -> None: ...
```

The coordinator depends on protocols, not Humanize HTTP clients or model classes.
The production service and local simulator can therefore share conformance tests.

# Validation and preflight

Before launch, validation MUST check:

- unique workflow and step identifiers;
- serializability;
- valid participant selectors and required traits;
- every step has a survey;
- answer references belong to the step;
- state references and commands exist;
- condition types are valid;
- reads authorize all shared-state prompt references;
- command requirements have an orchestration guard or an explicit declaration
  that conflict is acceptable;
- delivery routes exist for real-human participants;
- deadline and retry values are bounded and nonnegative;
- replacement pools cannot select the same disallowed participant;
- completion and deadlock policies are coherent;
- obvious dependency cycles and unreachable required steps;
- revision policies specify downstream handling;
- simulation agents cover all required participant bindings;
- production runs do not use simulation-only capabilities.

Warnings SHOULD flag:

- a serial chain that could use fan-out/fan-in parallelism;
- state exposed in a view but unused by the survey;
- steps with no deadline or intervention path;
- completion predicates that can become true while required work remains;
- stochastic simulation behavior without an explicit seed.

# Testing strategy

## Unit tests

- condition evaluation and dependency-key extraction;
- selector binding;
- status transition table;
- idempotency and optimistic version checks;
- policy serialization;
- virtual-clock ordering;
- per-participant stable random streams;
- capability validation and revocation;
- privacy filtering.

## Store/coordinator contract tests

Run the same suite against in-memory, SQLite, and remote implementations:

- duplicate launch;
- duplicate submission;
- crash after state write but before completion record;
- crash after readiness but before delivery;
- two prerequisites completing concurrently;
- two replacements racing;
- stale open page submitted after revocation;
- machine `require` no-op;
- repair scan after missed event;
- deadlock detection.

## Adapter conformance tests

Each adapter must prove:

- it receives only committed outbox messages;
- retries preserve logical message identity;
- open and submit go through coordinator authorization;
- cancellation/revocation is honored;
- private state is absent from transport payloads.

## End-to-end examples

Required acceptance workflows:

1. Two-person sequential response.
2. Parallel independent respondents followed by one aggregator.
3. Two blinded reviewers followed by adjudication only on disagreement.
4. Timeout and replacement reviewer.
5. Reminder-driven completion.
6. Late stale submission after replacement.
7. Upstream failure that blocks dependents and produces intervention output.
8. Same frozen definition run once with simulated agents and once through a
   capture Humanize adapter, producing equivalent workflow event shapes.

# Incremental implementation plan

## Phase 0: Freeze semantics

- Adopt the status transition table and event vocabulary.
- Decide package and CLI names.
- Define version-1 serialization schemas.
- Add examples for sequential and review/adjudication workflows.

## Phase 1: Local deterministic core

- Implement definitions, selectors, conditions, and validation.
- Implement SQLite workflow store and coordinator.
- Implement capture adapter and virtual clock.
- Support fixed participants, one work item per assignee, readiness predicates,
  immutable completion, and no deadlines.
- Prove duplicate submission and fan-in correctness.

## Phase 2: Agent simulator

- Add simulated inbox adapter.
- Convert opened work items into ordinary EDSL jobs.
- Add immediate deterministic behavior, then stochastic delay/dropout behavior.
- Add simulation result packages, timelines, costs, and CLI.
- Run the systematic-review workflow end to end.

## Phase 3: Humanize pilot

- Add workflow instance and work-item service resources.
- Bind Humanize respondents and personal links.
- Add waiting/completed/expired browser states.
- Connect delivery outbox to existing Humanize delivery routes.
- Add callbacks and response export.
- Pilot sequential two-person workflows with immutable submissions.

## Phase 4: Operational policies

- Durable reminders and deadlines.
- Replacement pools and manual intervention.
- Deadlock diagnostics and repair scans.
- Administrator status and audit interfaces.

## Phase 5: Advanced workflows

- Dynamic cardinality and claimable pools.
- Versioned revisions and downstream invalidation.
- Iterative workflows and bounded loops.
- Remote/background simulation execution.
- Cross-study reusable workflow templates.

# Acceptance criteria for version 1

Version 1 is complete when all of the following are true:

1. One serialized workflow can run unchanged with a Humanize adapter and an
   EDSL-agent simulator.
2. A dependent participant cannot view or submit a task before its readiness
   predicate is true.
3. Completing a prerequisite atomically makes downstream work ready and queues
   exactly one logical invitation.
4. Duplicate or stale submissions do not duplicate state effects.
5. Two concurrent prerequisite completions activate one fan-in task.
6. The simulator advances entirely through virtual events and performs no
   wall-clock sleeps.
7. AI respondents act only after simulated delivery and use the normal
   open/render/submit path.
8. A machine requirement no-op cannot silently complete a work item.
9. Privacy tests prove undeclared state is absent from delivery, prompt, page,
   callback, and ordinary audit output.
10. Deadlocked workflows terminate with actionable diagnostics.
11. The final result contains lossless workflow, submission, delivery, state, and
    event provenance.
12. Serialization compatibility and store/adapter conformance suites pass.

# Open design decisions

The following decisions should be resolved during Phase 0:

1. Whether the public name is `HumanWorkflow`, `ParticipantWorkflow`, or
   `SurveyWorkflow`. This spec uses `HumanWorkflow` while allowing simulated
   respondents.
2. Whether workflow CLI commands live under `ep humanize workflow` or a new
   top-level namespace.
3. Whether workflow metadata and shared state share one database transaction in
   the remote service or use a reconciled saga.
4. Whether each work item references a full Survey or a reusable survey template
   plus scenario binding.
5. Which condition expressions may inspect prior answer values directly versus
   requiring those values to be projected into shared state.
6. The minimum acceptable participant authentication for multi-person pilots.
7. Whether simulation participant history is represented as EDSL targeted memory,
   a scenario projection, or a dedicated respondent-history object.
8. How workflow submissions appear in ordinary EDSL `Results` without losing
   work-item and delivery provenance.
9. Whether `ready_when` false after readiness always revokes an item or may be
   declared monotonic at authoring time.
10. Whether completion finalization is owned by `HumanWorkflow` or delegated to a
    generalized state coordinator shared with model-run schedules.

# Recommended first vertical slice

The first implementation should be the systematic-review screening example:

1. Two reviewer participants are assigned the same paper independently.
2. Both receive simulated email when their review becomes ready.
3. Each EDSL agent opens and completes only its assigned review.
4. Reviews commit to the existing shared screening machine.
5. Agreement finalizes the paper automatically.
6. Disagreement activates an adjudicator work item and simulated invitation.
7. The adjudicator sees the two reviews through an explicit authorized read.
8. The workflow completes with a timeline, final state, survey results, delivery
   history, and model cost.

This slice exercises assignment, parallel readiness, fan-in, conditional
activation, privacy, delivery, AI answering, state transitions, and completion
without requiring revisions or replacement policies. The same frozen definition
can then be connected to Humanize respondents for the first real-human pilot.
