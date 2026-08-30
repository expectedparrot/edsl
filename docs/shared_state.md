# Shared state in EDSL

Shared state lets several interviews read and update the same serializable state
machine. The authoring objects describe behavior and routing; execution storage is
chosen by EDSL.

## The four authoring objects

`Machine` defines one state machine. It contains constants, typed fields, commands,
and a public view.

```python
from edsl.sharedstate import (
    Command, Machine, T, field, input_, put, reduce_, state_field,
)

activities = ("bike ride", "sailing", "hike", "beach day")

activity_poll = Machine(
    name="ActivityPoll",
    constants={"activities": activities},
    fields={
        "votes": state_field(T.map(T.text(), T.choice(activities)), {}),
    },
    commands={
        "vote": Command(
            inputs={"voter": T.text(), "activity": T.choice(activities)},
            effects=(put("votes", input_("voter"), input_("activity")),),
        ),
    },
    view={
        "votes": field("votes"),
        "counts": reduce_("count_by", field("votes").values()),
    },
)
```

`SharedState` names the machines that compose one state definition:

```python
from edsl.sharedstate import SharedState

definition = SharedState(poll=activity_poll)
```

`SharedStateMap` identifies a durable collection of independently scoped instances
of that definition:

```python
from edsl.sharedstate import SharedStateMap

polls = SharedStateMap(definition, state_id="weekend-activity-study")
```

The map does not contain a filename or server connection. An explicit `state_id`
means that later local runs using the same definition and identifier continue from
the same state. Omitting it creates a fresh identifier.

`ScopedState` is obtained with `.by(...)`. A scope may be any serializable value,
including a value resolved from the current interview:

```python
from edsl.sharedstate import current

family_poll = polls.by(current.agent.family_id)
```

The map is the container of scopes. `family_poll` is a declarative reference to one
entry; it does not read storage while the survey is being built.

## Reads and writes are Survey steps

An explicit read immediately before a question refreshes the state visible to that
question. A command immediately after a question becomes a write using its answer.

```python
from edsl import QuestionMultipleChoice, Survey

activity = QuestionMultipleChoice(
    question_name="activity",
    question_text=(
        "Current votes: {{ shared_state.poll.votes }}. "
        "Which activity should the group choose?"
    ),
    question_options=list(activities),
)

survey = Survey([
    family_poll.poll.read(),
    activity,
    family_poll.poll.vote(
        voter=current.agent.name,
        activity=activity.answer,
    ),
])
```

`current.agent.name` and `activity.answer` are serializable references. They are
resolved only when that interview reaches the step. The Jinja expression is only
presentation: the explicit read determines which state is supplied to the prompt.

Survey creation rejects unknown commands, missing or extra inputs, writes before a
question, unavailable answer references, conflicting definitions for one
`state_id`, and duplicate step identifiers.

## Scheduling determines visibility

A live serial schedule lets each participant observe preceding commits:

```python
from edsl import InterviewSchedule

schedule = InterviewSchedule.grouped_round_robin(
    group_by="family_id",
    order_by="turn",
)
```

A snapshot round gives every participant in the same group the state committed at
the beginning of that round, even if another participant finishes early:

```python
schedule = InterviewSchedule.rounds(
    count=3,
    group_by="family_id",
    within_round="concurrent",
    state_visibility="snapshot",
)
```

Concurrency limits control resource use; they do not create visibility barriers.
The interview schedule expresses those barriers.

## Completion is typed

A machine may define `complete_when`. Its scoped handle then provides a typed
condition to the schedule:

```python
game = games.by(current.agent.pair_id).game

schedule = InterviewSchedule.grouped_round_robin(
    "pair_id",
    "turn",
    stop_when=game.is_complete(),
)
```

This replaces string pairs naming a primitive and predicate. Supplying
`.is_complete()` for a machine without `complete_when` fails while authoring.
`finalize_when=game.is_complete()` applies the machine's close effects once.

A machine that has close effects but no automatic completion predicate can also
be closed explicitly as a Survey step:

```python
survey = Survey([
    auction.read(),
    bid,
    auction.bid(amount=bid.answer),
    auction.close(),
])
```

`.close()` is a serializable, idempotent state transition. It is most useful when
the survey structure itself identifies the final writer. For multi-participant
mechanisms, prefer a `complete_when` predicate with `finalize_when`, so settlement
occurs exactly when the shared state becomes complete.

## Local execution

EDSL binds state definitions to `SQLiteStateBackend`. SQLite transactions serialize
read-modify-write operations across threads and separate Python worker processes.
The backend is execution infrastructure and is not included in the Survey.

The backend contract is:

```python
class StateBackend(Protocol):
    def read(self, operation, *, at_sequence=None) -> ObservedState: ...
    def apply(self, operation) -> AdvisoryWriteOutcome: ...
    def finalize(self, condition, scope, *, execution_id): ...
    def snapshot(self, scope, *, at_sequence=None) -> StateSnapshot: ...
    def history(self, *, after_sequence=0) -> list[dict]: ...
    def checkpoint(self) -> int: ...
```

Writes are atomic and idempotent under retry. Every valid command write is processed;
a false `require` condition produces an unchanged successful write rather than a
rejection. A returned write outcome is always advisory: callers must not interpret it
as a durable receipt or use it to coordinate later work. Coordination comes from
subsequent reads and the schedule. Invalid definitions, unresolved references, and
type violations are programming errors and roll back before an event is committed.

## Results provenance

`Results.shared_state` contains one binding record per `state_id` touched by the
run. Each binding contains:

- the complete machine definition;
- an entry snapshot for every scope touched by this run;
- every read and write event produced by this run; and
- an exit snapshot for every touched scope.

Each read has a unique `read_id`, the observed version, and the exact public value
returned to the interview. Each write records its resolved inputs, committed
version, execution and step identifiers, and materialized state.

When another local run uses the same explicit `state_id`, its entry snapshot begins
at the previous run's exit state. Its `Results` still contains only its own events.

## Definition validation

Creating `SharedState(...)` validates every machine recursively. Validation covers:

- field and nested container initial values;
- known expression operations and reference namespaces;
- declared fields, constants, and command inputs;
- command targets and declared algorithms;
- public views against the initial state; and
- complete JSON serialization.

The DSL does not execute Python source, import modules, access files, or perform
network operations. More complicated algorithms must be registered under explicit,
versioned capability names.

## Complete examples

- `examples/shared_state_activity_poll.py` demonstrates scoped live voting.
- `examples/shared_state_activity_poll_repeated.py` demonstrates repeated paths.
- `examples/economic_game_ultimatum.py` demonstrates typed completion and
  finalization.
- `examples/shared_state_dsl/` contains one machine definition per state pattern.
- `docs/shared_state_execution_matrix.md` records executable coverage of every
  retained machine.
