# Shared State Surveys Spec

## Summary

Add opt-in shared state support for EDSL surveys.

Today, EDSL survey responses are normally isolated: one interview's answers do not affect another interview. Shared state would allow a survey to read from and write to a scoped common state during collection, enabling coordinated, interdependent, and live multi-respondent workflows.

The core idea:

> A survey can declare named shared state primitives. Questions can read those primitives through `shared_state` template variables. Validated answers can trigger declared writes to those primitives.

Reads should be easy:

```jinja2
{{ shared_state.slot_counts.top_k }}
{{ shared_state.topics.members }}
{{ shared_state.high_bid.value }}
```

Writes should be explicit:

```python
survey.add_shared_state_write(
    after_question="availability",
    target="slot_counts",
    operation="increment_many",
    values="{{ availability.answer }}",
)
```

This should work for both LLM/agent surveys and human surveys, with local deterministic stores for testing and a Coop-backed store for live shared state.

## Motivation

Some workflows are not independent surveys. The state created by one response should influence later responses.

Examples:

- scheduling and availability collection
- collaborative agenda building
- live voting and prioritization
- auctions and bidding
- task claiming and peer review assignment
- collaborative annotation
- capacity-limited booking
- multi-agent simulations with a shared environment
- market, game, and allocation experiments

These workflows need a shared state space that is scoped to a group, study, auction, meeting, assignment pool, or experiment cell.

## Non-Goals

- Do not make all surveys stateful by default.
- Do not silently allow shared state to affect ordinary survey runs.
- Do not make shared state an arbitrary Python callback system.
- Do not require Coop for local testing.
- Do not make domain-specific primitives such as `SharedAuction` the core abstraction in v1.
- Do not solve multi-round batch study workflows here; those can be built from existing EDSL objects.

## Design Principles

- Shared state is opt-in and serialized with the survey/job.
- Reads are render-time inputs exposed as `shared_state`.
- Writes are declared side effects executed only after answer validation.
- Shared state is scoped.
- Shared state uses typed computational primitives, not arbitrary unstructured mutation.
- Result metadata records reads and writes.
- Stores are pluggable.
- Local stores support deterministic tests.
- Coop-backed stores support live human workflows.

## Core Abstraction

Shared state is a scoped collection of named primitives.

Example:

```python
survey = survey.with_shared_state(
    scope="{{ scenario.meeting_id }}",
    store="coop",
    primitives={
        "slot_counts": SharedCounterMap(),
        "submissions": SharedLog(),
    },
)
```

Questions read from:

```jinja2
{{ shared_state.slot_counts.counts }}
{{ shared_state.submissions.count }}
```

Questions write through declarations:

```python
survey.add_shared_state_write(
    after_question="availability",
    target="slot_counts",
    operation="increment_many",
    values="{{ availability.answer }}",
)
```

## Shared State Primitives

The core should be a small set of general concurrent data structures.

### SharedRegister

A single value.

Useful for:

- current high bid
- current selected option
- current round
- global status
- winning item

Operations:

```text
get
set
compare_and_set
clear
```

Read view:

```jinja2
{{ shared_state.high_bid.value }}
{{ shared_state.high_bid.version }}
```

### SharedLog

Append-only event stream.

Useful for:

- bid history
- submissions
- comments
- proposals
- peer reviews
- audit trail
- messages

Operations:

```text
append
tail
filter
clear? maybe not v1
```

Read view:

```jinja2
{{ shared_state.proposals.entries }}
{{ shared_state.proposals.count }}
{{ shared_state.proposals.tail }}
```

### SharedCounterMap

Map from keys to numeric counts.

Useful for:

- votes
- availability slot counts
- feature prioritization
- frequency tallies
- ratings buckets

Operations:

```text
increment
increment_many
decrement
set_count
clear
```

Read view:

```jinja2
{{ shared_state.slot_counts.counts }}
{{ shared_state.slot_counts.top_k }}
{{ shared_state.slot_counts.total }}
```

### SharedSet

Unique unordered membership.

Useful for:

- proposed agenda topics
- completed item ids
- participant ids
- claimed respondent ids
- seen items
- tags

Operations:

```text
add
add_many
remove
contains
clear
```

Read view:

```jinja2
{{ shared_state.topics.members }}
{{ shared_state.topics.count }}
```

### SharedMap

Dictionary keyed by id.

Useful for:

- respondent profiles
- item metadata
- labels by item id
- assignment status
- structured shared scratch state

Operations:

```text
put
merge
delete
get
clear
```

Read view:

```jinja2
{{ shared_state.labels.values }}
{{ shared_state.labels["item_123"] }}
```

### Later Primitives

These are powerful but can come after the core primitives:

#### SharedQueue / WorkPool

Claimable tasks.

Useful for:

- annotation task assignment
- peer review routing
- dynamic work distribution

Operations:

```text
enqueue
claim
complete
release
requeue
```

#### SharedCapacityPool

Limited-capacity resources.

Useful for:

- appointment slots
- seats
- inventory
- quota cells
- resource booking

Operations:

```text
reserve
release
available
```

#### Leaderboard / PriorityMap

Items with scores.

Useful for:

- top proposals
- ranked agenda items
- bid ranking
- live competition

Operations:

```text
submit_score
increment_score
top_k
rank
```

## Why Not Domain-Specific Primitives First?

Domain-specific objects like `SharedAuction`, `SharedMatchingPool`, or `SharedSchedulingPoll` are attractive, but they are too closely tied to individual examples.

The more general computational objects are:

- register
- log
- counter map
- set
- map
- queue
- capacity pool
- priority map

These can compose into many applications.

Examples:

- auction = `SharedRegister` + `SharedLog`
- availability poll = `SharedCounterMap` + `SharedLog`
- agenda builder = `SharedSet` + `SharedCounterMap` + `SharedLog`
- annotation workflow = `SharedQueue` + `SharedMap` + `SharedSet`
- booking system = `SharedCapacityPool` + `SharedLog`

Domain-specific wrappers can be added later as convenience layers.

## User Semantics

### Reads

Reads happen before rendering a question.

The current shared state snapshot is added to the render context as:

```python
shared_state
```

Question text can use:

```jinja2
{{ shared_state.slot_counts.counts }}
```

Question options can also use shared state:

```python
QuestionCheckBox(
    question_name="topic_votes",
    question_text="Select up to three topics.",
    question_options="{{ shared_state.topics.members }}",
)
```

### Writes

Writes happen after an answer validates.

If answer validation fails, no shared state write occurs.

Writes execute in declaration order.

Default failure behavior should be:

```python
on_write_error="error"
```

### Conditions

Writes may have conditions:

```python
survey.add_shared_state_write(
    after_question="confirm_bid",
    condition="{{ confirm_bid.answer }} == 'Yes'",
    target="bids",
    operation="append",
    value={...},
)
```

### Templating Context For Writes

Write keys and values can be templated against:

- scenario
- agent
- current interview answers
- shared_state snapshot
- possibly write results from earlier writes in the same trigger

Example:

```python
value={
    "name": "{{ name.answer }}",
    "slots": "{{ availability.answer }}",
    "respondent_id": "{{ agent.id }}",
}
```

### Metadata

Each result should record shared-state reads and writes separately from normal answers.

Normal answers:

```json
{
  "answer": {
    "availability": ["Mon 9am", "Tue 2pm"]
  }
}
```

Shared-state metadata:

```json
{
  "shared_state": {
    "scope": "team-retro-2026-07",
    "reads": [
      {
        "question": "availability",
        "target": "slot_counts",
        "version": "v3"
      }
    ],
    "writes": [
      {
        "question": "availability",
        "target": "slot_counts",
        "operation": "increment_many",
        "values": ["Mon 9am", "Tue 2pm"],
        "version": "v4"
      }
    ]
  }
}
```

## Store Protocol

Shared state stores should implement a common protocol.

Sketch:

```python
class SharedStateStore:
    def read(
        self,
        scope: str,
        primitives: dict[str, SharedPrimitive],
    ) -> SharedStateSnapshot:
        ...

    def apply(
        self,
        scope: str,
        operation: SharedStateOperation,
    ) -> SharedStateWriteResult:
        ...
```

Snapshot:

```python
{
  "state": {...},
  "versions": {
    "slot_counts": "v3"
  },
  "timestamp": "..."
}
```

Write result:

```python
{
  "ok": true,
  "target": "slot_counts",
  "operation": "increment_many",
  "version": "v4",
  "operation_id": "..."
}
```

## Store Backends

### InMemorySharedStateStore

For local tests and agent simulations.

Properties:

- deterministic
- no network
- easy to inspect
- can be seeded with initial state

### SQLiteSharedStateStore

Optional local persistent store.

Useful for:

- local human testing
- replay
- longer-running local workflows

### CoopSharedStateStore

For live human workflows.

Responsibilities:

- authentication
- access control
- concurrency
- persistence
- audit logs
- live shared state across respondents

## LLM / Agent Survey Behavior

Shared state can be used in simulated surveys with agents.

Important execution modes:

### Sequential

Agents run in a fixed order.

Each agent reads the latest shared state and writes updates before the next agent.

This is deterministic and easiest to test.

```python
results = survey.by(agent_list).run(shared_state_mode="sequential")
```

### Snapshot

All agents read the same initial shared state.

Writes are recorded but do not affect other agents in the same run.

Useful when reproducibility matters.

```python
results = survey.by(agent_list).run(shared_state_mode="snapshot")
```

### Live / Eventual

Agents or humans read whatever state exists at render time.

This is realistic for live workflows but less reproducible.

```python
results = survey.run(shared_state_mode="live")
```

Recommended defaults:

- local LLM simulations: `sequential`
- human Coop workflows: `live`
- reproducibility-sensitive runs: `snapshot`

## Human Survey Behavior

For human surveys, shared state enables live coordinated workflows.

The human survey renderer/backend should:

1. Resolve shared state scope for the respondent.
2. Read shared state before each page/question render.
3. Render question text/options with `shared_state`.
4. Validate the human answer.
5. Execute declared shared-state writes.
6. Store read/write metadata.

Human-specific concerns:

- state can change while the respondent is viewing a page
- submitted writes may fail due to stale state
- UI may need to show a retry or refresh message
- Coop store should enforce permissions

For v1, if a write fails because of stale state, the survey can surface a clear error and re-render the question with fresh shared state.

## Example 1: Availability Poll

Goal: collect availability while showing current aggregate availability.

```python
from edsl import Survey, Scenario, ScenarioList
from edsl import QuestionFreeText, QuestionCheckBox
from edsl.shared_state import SharedCounterMap, SharedLog

slots = [
    "Mon 9am",
    "Mon 2pm",
    "Tue 9am",
    "Tue 2pm",
    "Wed 9am",
    "Wed 2pm",
]

q_name = QuestionFreeText(
    question_name="name",
    question_text="What is your name?",
)

q_availability = QuestionCheckBox(
    question_name="availability",
    question_text="""
Current group availability:

{{ shared_state.slot_counts.counts }}

Which times work for you?
""",
    question_options=slots,
)

survey = (
    Survey([q_name, q_availability])
    .with_shared_state(
        scope="{{ scenario.meeting_id }}",
        store="coop",
        primitives={
            "slot_counts": SharedCounterMap(keys=slots),
            "submissions": SharedLog(),
        },
    )
    .add_shared_state_write(
        after_question="availability",
        target="slot_counts",
        operation="increment_many",
        values="{{ availability.answer }}",
    )
    .add_shared_state_write(
        after_question="availability",
        target="submissions",
        operation="append",
        value={
            "name": "{{ name.answer }}",
            "slots": "{{ availability.answer }}",
            "respondent_id": "{{ agent.id }}",
        },
    )
)
```

Scenario:

```python
scenarios = ScenarioList([
    Scenario({"meeting_id": "team-retro-2026-07"})
])
```

## Example 2: Collaborative Agenda Builder

Goal: participants propose topics and vote on topics proposed so far.

```python
from edsl import Survey, QuestionFreeText, QuestionCheckBox
from edsl.shared_state import SharedSet, SharedCounterMap, SharedLog

q_name = QuestionFreeText(
    question_name="name",
    question_text="What is your name?",
)

q_propose = QuestionFreeText(
    question_name="proposed_topic",
    question_text="""
Current proposed agenda topics:

{{ shared_state.topics.members }}

Add one agenda topic you think we should discuss.
""",
)

q_vote = QuestionCheckBox(
    question_name="topic_votes",
    question_text="Select up to three topics you most want to discuss.",
    question_options="{{ shared_state.topics.members }}",
    max_selections=3,
)

q_comment = QuestionFreeText(
    question_name="comment",
    question_text="""
Current vote counts:

{{ shared_state.topic_vote_counts.counts }}

Any context we should consider when setting the agenda?
""",
)

survey = (
    Survey([q_name, q_propose, q_vote, q_comment])
    .with_shared_state(
        scope="{{ scenario.meeting_id }}",
        store="coop",
        primitives={
            "topics": SharedSet(),
            "topic_vote_counts": SharedCounterMap(),
            "topic_proposals": SharedLog(),
        },
    )
    .add_shared_state_write(
        after_question="proposed_topic",
        target="topics",
        operation="add",
        value="{{ proposed_topic.answer }}",
    )
    .add_shared_state_write(
        after_question="proposed_topic",
        target="topic_proposals",
        operation="append",
        value={
            "name": "{{ name.answer }}",
            "topic": "{{ proposed_topic.answer }}",
            "respondent_id": "{{ agent.id }}",
        },
    )
    .add_shared_state_write(
        after_question="topic_votes",
        target="topic_vote_counts",
        operation="increment_many",
        values="{{ topic_votes.answer }}",
    )
)
```

This example exercises:

- dynamic question options from shared state
- unique topic membership via `SharedSet`
- vote counts via `SharedCounterMap`
- proposal audit history via `SharedLog`

## Example 3: Auction

Goal: participants see the current high bid and place bids.

This can be composed from:

- `SharedRegister` for current high bid
- `SharedLog` for bid history

```python
from edsl import Survey, QuestionFreeText, QuestionNumerical, QuestionYesNo
from edsl.shared_state import SharedRegister, SharedLog

q_name = QuestionFreeText(
    question_name="bidder_name",
    question_text="What is your bidder name?",
)

q_bid = QuestionNumerical(
    question_name="bid_amount",
    question_text="""
Item: {{ scenario.item_name }}

Current high bid: {{ shared_state.high_bid.value.amount }}
Current high bidder: {{ shared_state.high_bid.value.bidder_name }}

Enter your bid.
""",
)

q_confirm = QuestionYesNo(
    question_name="confirm_bid",
    question_text="""
You entered {{ bid_amount.answer }}.

Current high bid is {{ shared_state.high_bid.value.amount }}.

Do you want to submit this bid?
""",
)

survey = (
    Survey([q_name, q_bid, q_confirm])
    .with_shared_state(
        scope="{{ scenario.auction_id }}",
        store="coop",
        primitives={
            "high_bid": SharedRegister(
                initial_value={"amount": 0, "bidder_name": None}
            ),
            "bid_history": SharedLog(),
        },
    )
    .add_shared_state_write(
        after_question="confirm_bid",
        condition="{{ confirm_bid.answer }} == 'Yes'",
        target="high_bid",
        operation="compare_and_set",
        expected_version="{{ shared_state.high_bid.version }}",
        value={
            "amount": "{{ bid_amount.answer }}",
            "bidder_name": "{{ bidder_name.answer }}",
            "respondent_id": "{{ agent.id }}",
        },
        only_if="{{ bid_amount.answer }} > {{ shared_state.high_bid.value.amount }}",
    )
    .add_shared_state_write(
        after_question="confirm_bid",
        condition="{{ confirm_bid.answer }} == 'Yes'",
        target="bid_history",
        operation="append",
        value={
            "amount": "{{ bid_amount.answer }}",
            "bidder_name": "{{ bidder_name.answer }}",
            "respondent_id": "{{ agent.id }}",
        },
    )
)
```

This example exercises:

- stale read protection through `expected_version`
- conditional writes
- current value via `SharedRegister`
- audit trail via `SharedLog`

Open issue:

- The generic `compare_and_set` and `only_if` form may be enough for v1.
- Later, higher-level store-defined operations such as `place_bid` may be more ergonomic.

## Validation

Shared state config should be validated when the survey/job is validated.

Validation should check:

- targets refer to declared primitives
- operations are valid for the primitive type
- required operation arguments are present
- triggers refer to known questions
- conditions are syntactically valid
- store configuration is valid
- scope template is valid

Example invalid write:

```python
survey.add_shared_state_write(
    after_question="vote",
    target="vote_counts",
    operation="append",
    value="A",
)
```

If `vote_counts` is a `SharedCounterMap`, `append` is invalid.

## Serialization

Shared state config should serialize with the survey/job.

Example shape:

```json
{
  "shared_state": {
    "scope": "{{ scenario.meeting_id }}",
    "store": {"type": "coop"},
    "primitives": {
      "slot_counts": {
        "type": "counter_map",
        "keys": ["Mon 9am", "Tue 2pm"]
      },
      "submissions": {
        "type": "log"
      }
    },
    "writes": [
      {
        "trigger": "after_question",
        "question": "availability",
        "target": "slot_counts",
        "operation": "increment_many",
        "values": "{{ availability.answer }}"
      }
    ]
  }
}
```

## Local Testing

Local tests should use `InMemorySharedStateStore`.

Example:

```python
store = InMemorySharedStateStore(
    initial_state={
        "team-retro-2026-07": {
            "slot_counts": {
                "Mon 9am": 0,
                "Tue 2pm": 0,
            },
            "submissions": [],
        }
    }
)

survey = survey.with_shared_state(
    scope="{{ scenario.meeting_id }}",
    store=store,
    primitives={
        "slot_counts": SharedCounterMap(),
        "submissions": SharedLog(),
    },
)
```

Tests should be able to assert:

- rendered questions saw expected shared state
- writes happened after validated answers
- invalid answers did not write
- metadata recorded reads/writes
- sequential execution updates later respondents' state

## Implementation Phases

### Phase 1: Core Model

- Add shared primitive classes.
- Add shared state config serialization.
- Add validation.
- Add `InMemorySharedStateStore`.

### Phase 2: Survey Integration

- Add `Survey.with_shared_state`.
- Add `Survey.add_shared_state_write`.
- Add shared state reads before render.
- Add shared state writes after validation.
- Add result metadata.

### Phase 3: LLM/Agent Runtime

- Support sequential mode.
- Support snapshot mode.
- Add tests with multiple agents.

### Phase 4: Human Runtime

- Add Coop store integration.
- Add live mode.
- Add stale write handling.
- Add human survey metadata.

### Phase 5: Additional Primitives

- Add queue/workpool.
- Add capacity pool.
- Add priority map/leaderboard.

## Open Questions

- Which primitives should be v1: register/log/counter/set/map only, or include queue/capacity pool?
- Should `only_if` be part of generic writes, or only `compare_and_set`?
- Should write result data be available to later writes in the same trigger?
- How should human UI handle stale write failures?
- Should `read_keys` be explicit, or should all declared primitives be read before each question?
- Should shared state be allowed in local `Survey.run` by default, or require an explicit run flag?
- What should the Coop shared-state API look like?

