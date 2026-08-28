"""Sealed simultaneous Nash demand bargaining."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedNashDemandGame, SharedState


def run_simulation(
    path: str | Path = "economic-game-nash-demand.jsonl", model_name="gemini-2.5-flash"
):
    specs = [
        ("A1", "pair-1", 0, "expects a fair 50/50 convention"),
        ("B1", "pair-1", 1, "expects a fair 50/50 convention"),
        ("A2", "pair-2", 0, "makes an assertive but coordination-aware demand"),
        ("B2", "pair-2", 1, "is accommodating to avoid bargaining failure"),
        ("A3", "pair-3", 0, "demands aggressively and expects the other to yield"),
        ("B3", "pair-3", 1, "demands aggressively and expects the other to yield"),
    ]
    agents = AgentList(
        [
            Agent(name=n, traits={"pair_id": p, "seat": s, "style": x})
            for n, p, s, x in specs
        ]
    )
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), game=SharedNashDemandGame(100)
    )
    demand = QuestionNumerical(
        question_name="demand",
        question_text=(
            "You and one other player simultaneously demand 0–100 from a pie of 100. "
            "You are {{ agent.name }} and {{ agent.style }}. If demands sum to at most "
            "100, each receives their demand and the remainder is wasted. If they exceed "
            "100, both receive zero. Demands are sealed. Choose yours."
        ),
        min_value=0,
        max_value=100,
    )
    schedule = InterviewSchedule.rounds(
        count=1,
        group_by="pair_id",
        reveal="after_round",
        finalize_when=GroupStopCondition("game", "complete"),
    )
    Survey([demand, state.game.demand(demand)]).by(agents).by(Model(model_name)).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


if __name__ == "__main__":
    result = run_simulation()
    for pair in ("pair-1", "pair-2", "pair-3"):
        print(result.render_markdown(scope=pair), "\n")
