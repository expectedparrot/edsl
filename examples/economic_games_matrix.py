"""Sealed prisoner's-dilemma and stag-hunt games across parallel pairs."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    Survey,
)
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedMatrixGame, SharedState


def players():
    specs = [
        ("A1", "pair-1", 0, "trusting and norm-following"),
        ("B1", "pair-1", 1, "trusting and norm-following"),
        ("A2", "pair-2", 0, "strictly self-interested and strategically cautious"),
        ("B2", "pair-2", 1, "strictly self-interested and strategically cautious"),
        ("A3", "pair-3", 0, "optimistic about cooperation"),
        ("B3", "pair-3", 1, "pessimistic about the other player's cooperation"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={"pair_id": pair, "seat": seat, "strategy": strategy},
            )
            for name, pair, seat, strategy in specs
        ]
    )


def run_game(name, actions, payoffs, payoff_description, log_path, model_name):
    state = SharedState(
        "{{ agent.pair_id }}",
        FileStateStore(log_path),
        game=SharedMatrixGame(actions, payoffs),
    )
    choice = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            f"You are playing a one-shot sealed {name}. "
            "You are {{ agent.name }} and are {{ agent.strategy }}. "
            f"Payoffs by action profile are: {payoff_description}. "
            "Neither player observes the other's choice before both commit. Choose "
            "the action that best fits your incentives and expectations."
        ),
        question_options=actions,
    )
    survey = Survey([choice, state.game.submit(choice)])
    schedule = InterviewSchedule.rounds(
        count=1,
        group_by="pair_id",
        within_round="concurrent",
        reveal="after_round",
        finalize_when=GroupStopCondition("game", "complete"),
    )
    (
        survey.by(players())
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    return state


def run_simulations(root: str | Path = ".", model_name="gemini-2.5-flash"):
    root = Path(root)
    prisoner = run_game(
        "prisoner's dilemma",
        ["cooperate", "defect"],
        {
            "cooperate|cooperate": [3, 3],
            "cooperate|defect": [0, 5],
            "defect|cooperate": [5, 0],
            "defect|defect": [1, 1],
        },
        "C/C=(3,3), C/D=(0,5), D/C=(5,0), D/D=(1,1)",
        root / "economic-game-prisoners-dilemma.jsonl",
        model_name,
    )
    coordination = run_game(
        "stag-hunt coordination game",
        ["stag", "hare"],
        {
            "stag|stag": [4, 4],
            "stag|hare": [0, 3],
            "hare|stag": [3, 0],
            "hare|hare": [3, 3],
        },
        "stag/stag=(4,4), stag/hare=(0,3), hare/stag=(3,0), hare/hare=(3,3)",
        root / "economic-game-stag-hunt.jsonl",
        model_name,
    )
    return {"prisoners_dilemma": prisoner, "stag_hunt": coordination}


if __name__ == "__main__":
    games = run_simulations()
    for game_name, state in games.items():
        print(f"# {game_name.replace('_', ' ').title()}")
        for pair_id in ("pair-1", "pair-2", "pair-3"):
            print(state.render_markdown(scope=pair_id), "\n")
