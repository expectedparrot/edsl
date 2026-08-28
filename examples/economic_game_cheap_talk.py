"""Cheap-talk communication with aligned and biased senders."""

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
from edsl.sharedstate import FileStateStore, SharedCheapTalkGame, SharedState


def participants():
    specs = [
        (
            "Sender-1",
            "pair-1",
            0,
            "sender",
            "L",
            "aligned",
            "Sender wants the receiver to match the true state.",
        ),
        (
            "Receiver-1",
            "pair-1",
            1,
            "receiver",
            "L",
            "aligned",
            "You know the sender is aligned.",
        ),
        (
            "Sender-2",
            "pair-2",
            0,
            "sender",
            "R",
            "aligned",
            "Sender wants the receiver to match the true state.",
        ),
        (
            "Receiver-2",
            "pair-2",
            1,
            "receiver",
            "L",
            "aligned",
            "You know the sender is aligned.",
        ),
        (
            "Sender-3",
            "pair-3",
            0,
            "sender",
            "L",
            "biased",
            "Sender earns 1 whenever receiver chooses R, regardless of state.",
        ),
        (
            "Receiver-3",
            "pair-3",
            1,
            "receiver",
            "L",
            "biased",
            "You know the sender always prefers action R.",
        ),
        (
            "Sender-4",
            "pair-4",
            0,
            "sender",
            "R",
            "biased",
            "Sender earns 1 whenever receiver chooses R, regardless of state.",
        ),
        (
            "Receiver-4",
            "pair-4",
            1,
            "receiver",
            "L",
            "biased",
            "You know the sender always prefers action R.",
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
                    "private_state": state,
                    "sender_preference": pref,
                    "information": info,
                },
            )
            for n, p, t, r, state, pref, info in specs
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-cheap-talk.jsonl", model_name="gemini-2.5-flash"
):
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), game=SharedCheapTalkGame()
    )
    message = QuestionMultipleChoice(
        question_name="message",
        question_text=(
            "You are {{ agent.name }}, the sender. The equally likely true state, "
            "observed only by you, is {{ agent.private_state }}. {{ agent.information }} "
            "Send costless message L or R. The receiver knows your incentive but not the state."
        ),
        question_options=["L", "R"],
    )
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "You are {{ agent.name }}, the receiver. The state is equally likely L or "
            "R and matching it pays you 1. {{ agent.information }} The sender's "
            "costless message is {{ shared_state.game.message }}. Choose action L or R."
        ),
        question_options=["L", "R"],
    )
    survey = Survey(
        [message, state.game.message(message), action, state.game.act(action)]
    )
    survey.add_skip_rule("message", "'{{ agent.role }}' != 'sender'")
    survey.add_skip_rule("action", "'{{ agent.role }}' != 'receiver'")
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
