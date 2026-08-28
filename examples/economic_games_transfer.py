"""Live dictator and trust games across independent pairs."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import (
    FileStateStore,
    SharedDictatorGame,
    SharedState,
    SharedTrustGame,
)


def run_dictator(path, model):
    dictators = AgentList(
        [
            Agent(
                name="D1",
                traits={
                    "pair_id": "pair-1",
                    "recipient": "R1",
                    "norm": "strongly egalitarian",
                },
            ),
            Agent(
                name="D2",
                traits={
                    "pair_id": "pair-2",
                    "recipient": "R2",
                    "norm": "self-interested but dislikes appearing unfair",
                },
            ),
            Agent(
                name="D3",
                traits={
                    "pair_id": "pair-3",
                    "recipient": "R3",
                    "norm": "strictly payoff maximizing",
                },
            ),
        ]
    )
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), game=SharedDictatorGame(100)
    )
    transfer = QuestionNumerical(
        question_name="transfer",
        question_text=(
            "You are {{ agent.name }} and are {{ agent.norm }}. You unilaterally divide "
            "$100 between yourself and {{ agent.recipient }}, who has no action. Choose "
            "the dollars transferred to the recipient."
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
    Survey([transfer, state.game.allocate(transfer)]).by(dictators).by(model).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


def trust_players():
    specs = [
        ("S1", "pair-1", 0, "sender", "highly trusting and reciprocal"),
        ("R1", "pair-1", 1, "receiver", "highly trusting and reciprocal"),
        ("S2", "pair-2", 0, "sender", "cautiously prosocial"),
        ("R2", "pair-2", 1, "receiver", "cautiously prosocial"),
        ("S3", "pair-3", 0, "sender", "strictly self-interested"),
        ("R3", "pair-3", 1, "receiver", "strictly self-interested"),
    ]
    return AgentList(
        [
            Agent(name=n, traits={"pair_id": p, "turn": t, "role": r, "norm": norm})
            for n, p, t, r, norm in specs
        ]
    )


def run_trust(path, model):
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), game=SharedTrustGame(100, 3)
    )
    sent = QuestionNumerical(
        question_name="sent",
        question_text=(
            "You are {{ agent.name }}, the sender, and are {{ agent.norm }}. Choose "
            "$0–$100 to send. The amount is tripled for the receiver, who may return any amount."
        ),
        min_value=0,
        max_value=100,
    )
    returned = QuestionNumerical(
        question_name="returned",
        question_text=(
            "You are {{ agent.name }}, the receiver, and are {{ agent.norm }}. Current "
            "game: {{ shared_state.game }}. Return between $0 and the displayed "
            "receiver_available amount to the sender."
        ),
        min_value=0,
        max_value=300,
    )
    survey = Survey(
        [sent, state.game.send(sent), returned, state.game.return_funds(returned)]
    )
    survey.add_skip_rule("sent", "'{{ agent.role }}' != 'sender'")
    survey.add_skip_rule("returned", "'{{ agent.role }}' != 'receiver'")
    schedule = InterviewSchedule.grouped_round_robin(
        "pair_id", "turn", finalize_when=GroupStopCondition("game", "complete")
    )
    survey.by(trust_players()).by(model).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


def run_simulations(root: str | Path = ".", model_name="gemini-2.5-flash"):
    root, model = Path(root), Model(model_name)
    return {
        "dictator": run_dictator(root / "economic-game-dictator.jsonl", model),
        "trust": run_trust(root / "economic-game-trust.jsonl", model),
    }


if __name__ == "__main__":
    for game_name, state in run_simulations().items():
        print(f"# {game_name.title()}")
        for pair in ("pair-1", "pair-2", "pair-3"):
            print(state.render_markdown(scope=pair), "\n")
