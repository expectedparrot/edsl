"""Principal-agent contracting with private costly effort."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedPrincipalAgentGame, SharedState


def participants():
    specs = [
        (
            "Principal-1",
            "pair-1",
            0,
            "principal",
            "calculates the minimum incentive-compatible bonus",
        ),
        ("Worker-1", "pair-1", 1, "worker", "maximizes expected monetary payoff"),
        (
            "Principal-2",
            "pair-2",
            0,
            "principal",
            "is stingy and dislikes sharing output",
        ),
        ("Worker-2", "pair-2", 1, "worker", "maximizes expected monetary payoff"),
        (
            "Principal-3",
            "pair-3",
            0,
            "principal",
            "uses a generous bonus to strongly motivate effort",
        ),
        ("Worker-3", "pair-3", 1, "worker", "maximizes expected monetary payoff"),
    ]
    return AgentList(
        [
            Agent(name=n, traits={"pair_id": p, "turn": t, "role": r, "strategy": s})
            for n, p, t, r, s in specs
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-moral-hazard.jsonl", model_name="gemini-2.5-flash"
):
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), game=SharedPrincipalAgentGame()
    )
    bonus = QuestionNumerical(
        question_name="bonus",
        question_text=(
            "You are {{ agent.name }}, the principal, and {{ agent.strategy }}. Output "
            "is worth 100 on success. A worker privately chooses high effort (success "
            "probability .8, cost 20) or low effort (probability .2, cost 0). Offer a "
            "success-contingent bonus from 0–100 to maximize expected output minus bonus."
        ),
        min_value=0,
        max_value=100,
    )
    effort = QuestionMultipleChoice(
        question_name="effort",
        question_text=(
            "You are {{ agent.name }}, the worker, and {{ agent.strategy }}. The success "
            "bonus is {{ shared_state.game.bonus }}. High effort has success probability "
            ".8 and cost 20; low effort has probability .2 and cost 0. Effort is private. Choose."
        ),
        question_options=["high", "low"],
    )
    survey = Survey(
        [bonus, state.game.contract(bonus), effort, state.game.effort(effort)]
    )
    survey.add_skip_rule("bonus", "'{{ agent.role }}' != 'principal'")
    survey.add_skip_rule("effort", "'{{ agent.role }}' != 'worker'")
    terminal = GroupStopCondition("game", "terminal")
    schedule = InterviewSchedule.grouped_round_robin(
        "pair_id", "turn", finalize_when=terminal
    )
    survey.by(participants()).by(Model(model_name)).run(
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
