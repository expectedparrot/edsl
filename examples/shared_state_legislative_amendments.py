"""Live serial revision of a small bill by competing legislators."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionFreeText, Survey
from edsl.sharedstate import FileStateStore, SharedDocument, SharedState


INITIAL_BILL = """1. Automated decisions must be disclosed to affected residents.
2. Agencies must publish an annual summary of automated systems.
3. This act takes effect 30 days after passage."""


def legislators():
    specs = [
        ("Rosa", 0, "civil-liberties advocate", "appeals and individual due process"),
        ("Sam", 1, "city operations chair", "feasible implementation and cost"),
        ("Talia", 2, "labor representative", "worker consultation and job protections"),
        (
            "Uma",
            3,
            "technology reformer",
            "audits, transparency, and measurable enforcement",
        ),
    ]
    return AgentList(
        [
            Agent(name=name, traits={"seat": seat, "role": role, "priority": priority})
            for name, seat, role, priority in specs
        ]
    )


def build_survey(state):
    draft = QuestionFreeText(
        question_name="revised_bill",
        question_text=(
            "Round {{ run.round }} of 2. You are {{ agent.name }}, a {{ agent.role }} "
            "focused on {{ agent.priority }}.\n\nCurrent bill:\n"
            "{{ shared_state.bill.text }}\n\nRecent revisions: "
            "{{ shared_state.bill.recent_revisions }}\n\nReturn the complete bill with one "
            "careful amendment. Preserve provisions you do not intend to change."
        ),
    )
    rationale = QuestionFreeText(
        question_name="rationale",
        question_text="Briefly explain the single amendment you made and its tradeoff.",
    )
    return Survey([draft, rationale, state.bill.revise(draft, rationale)])


def run_simulation(
    log_path: str | Path = "legislative-amendments.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "automated-decisions-bill",
        FileStateStore(log_path),
        bill=SharedDocument("Automated Decisions Accountability Act", INITIAL_BILL),
    )
    schedule = InterviewSchedule.rounds(
        count=2,
        within_round="serial",
        state_visibility="live",
        order_by="seat",
        round_order="rotate",
    )
    (
        build_survey(state)
        .by(legislators())
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
