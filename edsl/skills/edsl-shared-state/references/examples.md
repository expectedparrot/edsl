# Shared-state worked examples

## A typed running ledger

This Machine folds a sequence of amounts into a balance and history. The
definition is plain serializable data; transitions run through the shared-state
runtime.

```python
from edsl.sharedstate import (
    Command, Machine, StateType, arg, assign, field, fold, local, record,
    state_field,
)

previous, amount = local("previous"), local("amount")
balance = previous.get("balance") + amount
ledger_type = StateType.record({
    "balance": StateType.number(),
    "history": StateType.sequence(StateType.number()),
})

machine = Machine(
    name="RunningLedger",
    constants={},
    fields={"ledger": state_field(ledger_type, {"balance": 0, "history": []})},
    commands={
        "post": Command(
            inputs={"amounts": StateType.sequence(StateType.number())},
            effects=(assign("ledger", fold(
                arg("amounts"), field("ledger"), item="amount",
                accumulator="previous", accumulator_type=ledger_type,
                body=record(
                    balance=balance,
                    history=previous.get("history").appended(balance),
                ),
            )),),
        )
    },
    view={"ledger": field("ledger")},
)
```

Run the transition locally and inspect the resulting state:

```python
from edsl.sharedstate.dsl_runtime import Runtime

runtime = Runtime()
state = runtime.initial_state(machine)
result = runtime.execute(machine, state, "post", {"amounts": [10, -3, 5]})
print(result.state["ledger"])
# {"balance": 12, "history": [10, 7, 12]}
```

## Attach state to a survey

Read current group state before asking a question, then write the validated
answer through a typed reference. The scope key must be stable for everyone
who shares the same state.

```python
from edsl import QuestionMultipleChoice, Survey
from edsl.sharedstate import SharedState, SharedStateMap, current

state_map = SharedStateMap(SharedState(poll=poll_machine), state_id="poll-v1")
group = state_map.by(current.agent.group_id)
vote = QuestionMultipleChoice(
    question_name="vote",
    question_text="Choose an activity",
    question_options=["Sailing", "Hiking", "Beach"],
)
survey = Survey([
    group.poll.read(),
    vote,
    group.poll.vote(voter=current.agent.name, activity=vote.answer),
])
```

For run ordering, persistence, and provenance inspection, see
[survey execution and state provenance](survey-execution.md). The much larger
Machine corpus is maintained under `tests/fixtures/shared_state/dsl/` and
exercised by the test suite; this reference is the supported skill entry point
for the core patterns.
