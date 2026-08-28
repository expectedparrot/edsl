"""Education signaling with private worker productivity."""

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
from edsl.sharedstate import FileStateStore, SharedSignalingGame, SharedState


def participants():
    specs = [
        (
            "High-1",
            "pair-1",
            0,
            "worker",
            100,
            5,
            "high productivity and low education cost",
        ),
        (
            "Firm-1",
            "pair-1",
            1,
            "employer",
            0,
            0,
            "believes education of 2 or more strongly predicts high productivity",
        ),
        (
            "Low-1",
            "pair-2",
            0,
            "worker",
            40,
            20,
            "low productivity and high education cost",
        ),
        (
            "Firm-2",
            "pair-2",
            1,
            "employer",
            0,
            0,
            "believes education of 2 or more strongly predicts high productivity",
        ),
        (
            "High-2",
            "pair-3",
            0,
            "worker",
            100,
            5,
            "high productivity and low education cost",
        ),
        (
            "Firm-3",
            "pair-3",
            1,
            "employer",
            0,
            0,
            "is skeptical and requires a strong education signal",
        ),
        (
            "Low-2",
            "pair-4",
            0,
            "worker",
            40,
            20,
            "low productivity but is willing to mimic if profitable",
        ),
        (
            "Firm-4",
            "pair-4",
            1,
            "employer",
            0,
            0,
            "uses education as its only observable evidence",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=n,
                traits={
                    "pair_id": p,
                    "turn": t,
                    "role": r,
                    "productivity": prod,
                    "signal_cost": cost,
                    "strategy": s,
                },
            )
            for n, p, t, r, prod, cost, s in specs
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-signaling.jsonl", model_name="gemini-2.5-flash"
):
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), game=SharedSignalingGame(60)
    )
    education = QuestionNumerical(
        question_name="education",
        question_text=(
            "You are {{ agent.name }}, a worker with private productivity "
            "{{ agent.productivity }} and cost {{ agent.signal_cost }} per education "
            "unit. You are {{ agent.strategy }}. Choose education 0–3. An employer "
            "observes education but not productivity, then may hire at wage 60."
        ),
        min_value=0,
        max_value=3,
    )
    hiring = QuestionMultipleChoice(
        question_name="hiring",
        question_text=(
            "You are {{ agent.name }} and {{ agent.strategy }}. Worker productivity is "
            "either 100 or 40 with equal prior probability. You observe education "
            "{{ shared_state.game.education }} but not type. Hiring pays productivity "
            "minus wage 60; not hiring pays zero. Choose."
        ),
        question_options=["hire", "do_not_hire"],
    )
    survey = Survey(
        [education, state.game.signal(education), hiring, state.game.decide(hiring)]
    )
    survey.add_skip_rule("education", "'{{ agent.role }}' != 'worker'")
    survey.add_skip_rule("hiring", "'{{ agent.role }}' != 'employer'")
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
    for pair in ("pair-1", "pair-2", "pair-3", "pair-4"):
        print(result.render_markdown(scope=pair), "\n")
