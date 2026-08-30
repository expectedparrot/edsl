"""Parallel ultimatum games using only the machine-based shared-state API."""

from __future__ import annotations

import random
from uuid import uuid4

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    choose,
    constant,
    current,
    field,
    input_,
    record,
    set_once,
    state_field,
)


TRAITS_TEMPLATE = """Your behavioral traits use scales from -1 to 1:
- generosity = {{ generosity }}: -1 means maximizing your own payoff; 1 means
  willingly sacrificing payoff to benefit the other player.
- inequity_aversion = {{ inequity_aversion }}: -1 means readily accepting
  unequal outcomes; 1 means strongly opposing unequal outcomes.
Act consistently with these values. Rejection gives both players $0.
"""


def ultimatum_game(stake: float = 100) -> Machine:
    return Machine(
        name="UltimatumGame",
        constants={"stake": stake},
        fields={
            "offer": state_field(T.optional(T.number()), None),
            "proposer": state_field(T.optional(T.text()), None),
            "responder": state_field(T.optional(T.text()), None),
            "decision": state_field(
                T.optional(T.choice(("accept", "reject"))), None
            ),
        },
        commands={
            "offer": Command(
                inputs={
                    "player": T.text(),
                    "amount": T.number(minimum=0, maximum=constant("stake")),
                },
                effects=(
                    set_once("proposer", input_("player")),
                    set_once("offer", input_("amount")),
                ),
            ),
            "respond": Command(
                inputs={
                    "player": T.text(),
                    "decision": T.choice(("accept", "reject")),
                },
                require=field("offer") != None,  # noqa: E711
                effects=(
                    set_once("responder", input_("player")),
                    set_once("decision", input_("decision")),
                ),
            ),
        },
        view={
            "offer": field("offer"),
            "proposer": field("proposer"),
            "responder": field("responder"),
            "decision": field("decision"),
            "payoffs": choose(
                field("decision") == "accept",
                record(
                    proposer=constant("stake") - field("offer"),
                    responder=field("offer"),
                ),
                record(proposer=0, responder=0),
            ),
        },
        complete_when=field("decision") != None,  # noqa: E711
    )


def players(count: int = 50, seed: int = 20260828) -> AgentList:
    if count < 2 or count % 2:
        raise ValueError("count must be an even integer of at least 2")
    rng = random.Random(seed)
    return AgentList(
        [
            Agent(
                name=f"Person {index + 1:02d}",
                traits={
                    "generosity": round(rng.uniform(-1, 1), 2),
                    "inequity_aversion": round(rng.uniform(-1, 1), 2),
                    "pair_id": f"pair-{index // 2 + 1}",
                    "turn": index % 2,
                    "role": "proposer" if index % 2 == 0 else "responder",
                },
            )
            for index in range(count)
        ],
        traits_presentation_template=TRAITS_TEMPLATE,
    )


def build_survey(state_id: str) -> tuple[Survey, object]:
    games = SharedStateMap(
        SharedState(game=ultimatum_game()), state_id=state_id
    )
    game = games.by(current.agent.pair_id).game
    offer = QuestionNumerical(
        question_name="offer",
        question_text=(
            "You are the proposer. Current game: {{ shared_state.game }}. "
            "How many dollars from the $100 stake do you offer the responder?"
        ),
        min_value=0,
        max_value=100,
    )
    decision = QuestionMultipleChoice(
        question_name="decision",
        question_text=(
            "You are the responder. Current game: {{ shared_state.game }}. "
            "Do you accept or reject the recorded offer?"
        ),
        question_options=["accept", "reject"],
    )
    survey = Survey(
        [
            game.read(),
            offer,
            game.offer(player=current.agent.name, amount=offer.answer),
            game.read(),
            decision,
            game.respond(player=current.agent.name, decision=decision.answer),
        ]
    )
    survey.add_skip_rule("offer", "'{{ agent.role }}' != 'proposer'")
    survey.add_skip_rule("decision", "'{{ agent.role }}' != 'responder'")
    return survey, game.is_complete()


def run(
    count: int = 50,
    seed: int = 20260828,
    model_name: str = "gemini-2.5-flash",
    max_concurrency: int = 10,
    state_id: str | None = None,
):
    survey, complete = build_survey(state_id or f"ultimatum-{uuid4()}")
    schedule = InterviewSchedule.grouped_round_robin(
        "pair_id", "turn", finalize_when=complete
    )
    return (
        survey.by(players(count, seed))
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
            max_concurrency=max_concurrency,
        )
    )


if __name__ == "__main__":
    results = run()
    print(results.shared_state)
