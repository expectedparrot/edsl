"""Live allocation from a finite shared civic budget."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionMultipleChoice
from edsl import QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedBudgetPool, SharedState


PROJECTS = {
    "Cooling centers": "heat-wave shelters in underserved neighborhoods",
    "Library hours": "evening and weekend access at branch libraries",
    "Bike safety": "protected intersections on high-injury corridors",
    "Youth arts": "free after-school music and theater programs",
}


def delegates() -> AgentList:
    specs = [
        ("Inez", 0, "public health", "Cooling centers"),
        ("Jamal", 1, "education access", "Library hours"),
        ("Keiko", 2, "street safety", "Bike safety"),
        ("Luis", 3, "youth development", "Youth arts"),
        ("Mara", 4, "climate resilience", "Cooling centers"),
        ("Noah", 5, "neighborhood equity", "Library hours"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={"seat": seat, "priority": priority, "favorite": favorite},
            )
            for name, seat, priority, favorite in specs
        ]
    )


def build_survey(state: SharedState) -> Survey:
    project = QuestionMultipleChoice(
        question_name="project",
        question_text=(
            "Round {{ run.round }}. You are {{ agent.name }}, representing "
            "{{ agent.priority }}; your preferred project is {{ agent.favorite }}.\n\n"
            "Shared budget: {{ shared_state.budget }}\n\n"
            "Choose one project for your next funding request. React to allocations "
            "already made and diversify if another need is now more urgent."
        ),
        question_options=list(PROJECTS),
    )
    amount = QuestionNumerical(
        question_name="amount",
        question_text=(
            "Request between $0 and $20 for {{ project.answer }}. Only "
            "{{ shared_state.budget.remaining }} remains. The grant will be partially "
            "filled if your request exceeds the remaining shared budget."
        ),
        min_value=0,
        max_value=20,
    )
    return Survey([project, amount, state.budget.fund(project, amount)])


def run_simulation(
    log_path: str | Path = "budget-allocation.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "city-mini-budget",
        FileStateStore(log_path),
        budget=SharedBudgetPool(75, PROJECTS),
    )
    schedule = InterviewSchedule.rounds(
        count=2,
        within_round="serial",
        state_visibility="live",
        order_by="seat",
        round_order="rotate",
        stop_when=GroupStopCondition("budget", "exhausted"),
    )
    (
        build_survey(state)
        .by(delegates())
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    state.close()
    return state


if __name__ == "__main__":
    print(run_simulation().render_markdown())
