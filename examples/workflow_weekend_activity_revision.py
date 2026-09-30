"""Bounded proposal/rejection loop executed through simulated email inboxes."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from edsl import Agent, Model, QuestionMultipleChoice, QuestionYesNo, Survey
from edsl.sharedstate import (
    Command,
    Machine,
    SQLiteStateBackend,
    SharedState,
    SharedStateMap,
    T,
    append,
    field,
    input_,
    state_field,
)
from edsl.workflows import (
    AnswerCondition,
    EDSLAgentAnswerer,
    HumanStep,
    HumanWorkflow,
    ParticipantSelector,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowSimulation,
)

ACTIVITIES = ["Sailing", "Biking", "Hiking", "Beach"]


def build_revision_workflow():
    activity_state = Machine(
        name="ActivitySuggestions",
        constants={},
        fields={"suggestions": state_field(T.sequence(T.text()), [])},
        commands={
            "suggest": Command(
                inputs={"activity": T.text()},
                effects=(append("suggestions", input_("activity")),),
            )
        },
        view={"suggestions": field("suggestions")},
    )
    state_map = SharedStateMap(
        SharedState(activity=activity_state), state_id="weekend-activity-revisions"
    )
    activity = state_map.by("this-weekend").activity

    steps = []
    previous_approval = None
    for attempt in range(1, len(ACTIVITIES) + 1):
        proposal_name = f"propose-{attempt}"
        approval_name = f"approve-{attempt}"
        suggestion = QuestionMultipleChoice(
            question_name=f"suggestion_{attempt}",
            question_text=(
                "Choose an activity for this weekend. Previous rejected suggestions: "
                "{{ shared_state.activity.suggestions }}. Do not repeat one."
            ),
            question_options=ACTIVITIES,
        )
        proposal_condition = (
            AnswerCondition(
                previous_approval,
                f"approved_{attempt - 1}",
                "No",
            )
            if previous_approval is not None
            else None
        )
        steps.append(
            HumanStep(
                proposal_name,
                Survey([suggestion]),
                ParticipantSelector.role("proposer"),
                after=((previous_approval,) if previous_approval else ()),
                enabled_when=proposal_condition,
                reads=(activity.read(),),
                writes=(activity.suggest(activity=suggestion.answer),),
            )
        )
        approval = QuestionYesNo(
            question_name=f"approved_{attempt}",
            question_text=(
                "The proposed activity is "
                "{{ shared_state.activity.suggestions[-1] }}. Do you approve?"
            ),
        )
        steps.append(
            HumanStep(
                approval_name,
                Survey([approval]),
                ParticipantSelector.role("approver"),
                after=(proposal_name,),
                reads=(activity.read(),),
            )
        )
        previous_approval = approval_name
    return HumanWorkflow("weekend-activity-revision", steps), state_map


def llm_respondents():
    return [
        Agent(
            name="proposer@simulated.email",
            traits={"role": "proposer"},
            instruction=(
                "You propose weekend activities. Prefer Sailing first, then Hiking, "
                "then Biking, then Beach. Never repeat a rejected suggestion."
            ),
        ),
        Agent(
            name="approver@simulated.email",
            traits={"role": "approver"},
            instruction=(
                "You approve weekend plans. Reject Sailing because the wind forecast "
                "is unsafe. Approve Hiking, Biking, or Beach."
            ),
        ),
    ]


class ScriptedDemoAnswerer:
    """Reproduce the illustrative rejection path without model calls."""

    def answer(self, agent, opened):
        answers = {
            "propose-1": {"suggestion_1": "Sailing"},
            "approve-1": {"approved_1": "No"},
            "propose-2": {"suggestion_2": "Hiking"},
            "approve-2": {"approved_2": "Yes"},
        }
        return answers[opened.step_name]


def run(root: Path, answerer):
    workflow, state_map = build_revision_workflow()
    store = SQLiteWorkflowStore(root / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        workflow,
        store,
        state_backends={
            state_map.state_id: SQLiteStateBackend(state_map, root / "state.sqlite")
        },
    )
    agents = llm_respondents()
    instance_id = coordinator.launch(agents)
    simulation = WorkflowSimulation(
        coordinator,
        {agent.name: agent for agent in agents},
        answerer,
    )
    simulation.run(instance_id)
    return store, instance_id, simulation


def run_with_llms(root: Path):
    answerer = EDSLAgentAnswerer(
        Model("gpt-4o-mini", service_name="openai"),
        run_options={"disable_remote_inference": False},
    )
    return run(root, answerer)


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        store, instance_id, simulation = run_with_llms(Path(directory))
        print("Simulated delivery order:")
        for message in simulation.inbox.messages:
            print(f"  {message.participant_id}")
        print("Responses:")
        for item in store.items(instance_id):
            answers = store.step_answers(instance_id, item["step_name"])
            if answers:
                print(f"  {item['step_name']}: {answers[0]}")
        print("Skipped future work:")
        for item in store.items(instance_id):
            if item["status"] == "skipped":
                print(f"  {item['step_name']}")
