# Survey execution and state provenance

Use a scoped machine handle to add an explicit read and write around the
question that observes or changes the state:

```python
from edsl.sharedstate import current

group = state_map.by(current.agent.group_id)
survey = Survey(
    [
        group.poll.read(),
        question,
        group.poll.vote(voter=current.agent.name, activity=question.answer),
    ]
)
```

The read supplies a participant-visible view for rendering. The write consumes
validated answers through typed references. Put these operations in the intended
survey order; do not assume a question's text alone changes state. Scope keys
must be stable and available from agent traits or other supported execution
context.

Use the job's interview schedule when state transitions depend on who acts
first, grouped turns, or ordered rounds. Shared state provides atomic state
transitions; the schedule controls interview ordering. For respondent workflows
with branching, repeated steps, human delivery, and recovery, use the separate
`edsl-orchestration` skill.

## Inspecting a run

The saved Results object carries shared-state bindings with entry snapshots,
ordered events, and exit snapshots. Use these to inspect what state a run
started from, which reads and writes occurred, and the resulting state. A
question-presentation record can preserve the exact read versions used to build
that question's prompt; use it when checking which options were shown.

Prefer CLI inspection for agent workflows:

```bash
ep results state --file results.ep
ep results state --file results.ep --binding 0
```

The CLI currently returns all shared-state data or one binding by index. For
more detailed analysis, load the Results object in Python and inspect
`results.shared_state["bindings"]` and the associated presentation metadata.

Use a local Machine dry run to inspect the transition semantics before adding
the machine to a survey. `ep state simulate` does not write a backend or prove
that a complete multi-interview schedule behaves correctly; exercise the saved
Jobs or workflow as well when ordering and persistence matter.
