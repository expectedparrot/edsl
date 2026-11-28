# Respondent workflow example

This two-step flow lets one participant propose an activity and another approve
it. The dependency ensures the approval step opens after the proposal, and the
shared-state read makes the proposal available when the second survey renders.

```python
from edsl import Agent, QuestionMultipleChoice, QuestionYesNo, Survey
from edsl.sharedstate import (
    Command, Machine, SharedState, SharedStateMap, StateType,
    arg, field, set_once, state_field,
)
from edsl.workflows import HumanStep, HumanWorkflow, ParticipantSelector

activity_machine = Machine(
    name="WeekendActivity",
    constants={},
    fields={"suggestion": state_field(StateType.optional(StateType.text()), None)},
    commands={
        "suggest": Command(
            inputs={"activity": StateType.text()},
            effects=(set_once("suggestion", arg("activity")),),
        )
    },
    view={"suggestion": field("suggestion")},
)
state_map = SharedStateMap(
    SharedState(activity=activity_machine), state_id="weekend-activity"
)
activity = state_map.by("this-weekend").activity

proposal = QuestionMultipleChoice(
    question_name="suggestion",
    question_text="What activity should we do this weekend?",
    question_options=["Sailing", "Biking", "Hiking", "Beach"],
)
approval = QuestionYesNo(
    question_name="approved",
    question_text="Do you approve {{ shared_state.activity.suggestion }}?",
)
workflow = HumanWorkflow("weekend-activity-approval", [
    HumanStep(
        "suggest-activity", Survey([proposal]),
        ParticipantSelector.role("proposer"),
        writes=(activity.suggest(activity=proposal.answer),),
    ),
    HumanStep(
        "approve-activity", Survey([approval]),
        ParticipantSelector.role("approver"),
        after=("suggest-activity",), reads=(activity.read(),),
    ),
])
people = [
    Agent(name="proposer", traits={"role": "proposer"}),
    Agent(name="approver", traits={"role": "approver"}),
]
```

Compile and validate before creating a durable run. Keep the workflow, state
map, participants, and execution plan together in a `WorkflowExperiment` when
you need a portable bundle. See
[authoring and execution](authoring-and-execution.md) for persistence and
resumption requirements.
