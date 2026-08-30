"""Run small behavioral smoke tests of shared-state games with Gemini.

These are genuine EDSL interviews.  Gemini chooses every action; the script only
provides roles, private values, scheduling, and the shared-state machinery.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
from uuid import uuid4

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    QuestionNumerical,
    QuestionRank,
    QuestionFreeText,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current


MODEL = "gemini-2.5-flash"


def _agent(name, **traits):
    return Agent(name=name, traits=traits)


def _simultaneous(spec, target, question, write, agents):
    states = SharedStateMap(
        SharedState(**{target: spec}), state_id=f"gemini-{target}-{uuid4()}"
    )
    handle = getattr(states.by("game"), target)
    survey = Survey([handle.read(), question, write(handle, question)])
    schedule = InterviewSchedule.rounds(
        count=1,
        within_round="concurrent",
        state_visibility="snapshot",
        finalize_when=handle.is_complete(),
    )
    return survey, AgentList(agents), schedule


def dictator():
    from examples.shared_state_dsl.shared_dictator_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-dictator-{uuid4()}"
    )
    game = states.by("game").game
    q = QuestionNumerical(
        question_name="transfer",
        question_text=(
            "You have $100. Choose how many dollars to give Recipient; you keep "
            "the rest. Choose from 0 through 100."
        ),
        min_value=0,
        max_value=100,
    )
    return (
        Survey(
            [
                game.read(),
                q,
                game.allocate(
                    dictator=current.agent.name,
                    recipient="Recipient",
                    transfer=q.answer,
                ),
            ]
        ),
        AgentList([_agent("Dictator", generosity=0.25)]),
        InterviewSchedule.rounds(
            count=1, finalize_when=game.is_complete()
        ),
    )


def trust():
    from examples.shared_state_dsl.shared_trust_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-trust-{uuid4()}"
    )
    game = states.by("game").game
    send = QuestionNumerical(
        question_name="send",
        question_text=(
            "You are Sender with $100. Choose 0–100 to send. The amount sent "
            "will be tripled for Receiver, who can return some of it."
        ),
        min_value=0,
        max_value=100,
    )
    returned = QuestionNumerical(
        question_name="returned",
        question_text=(
            "You are Receiver. Current game: {{ shared_state.game }}. Choose how "
            "much of the tripled transfer to return to Sender."
        ),
        min_value=0,
        max_value=300,
    )
    survey = Survey(
        [
            game.read(),
            send,
            game.send(player=current.agent.name, amount=send.answer),
            game.read(),
            returned,
            game.return_funds(player=current.agent.name, amount=returned.answer),
        ]
    )
    survey.add_skip_rule("send", "'{{ agent.role }}' != 'sender'")
    survey.add_skip_rule("returned", "'{{ agent.role }}' != 'receiver'")
    people = AgentList(
        [
            _agent("Sender", role="sender", role_group="game", turn=0),
            _agent("Receiver", role="receiver", role_group="game", turn=1),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        group_by="role_group", order_by="turn", finalize_when=game.is_complete()
    )


def matrix():
    from examples.shared_state_dsl.shared_matrix_game import SPEC

    q = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "Choose an action in this one-shot game. Both cooperate gives 3 each; "
            "defect against cooperate gives 5 to the defector and 0 to the other; "
            "both defect gives 1 each."
        ),
        question_options=["cooperate", "defect"],
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.submit(
            player=current.agent.name,
            seat=current.agent.seat,
            action=question.answer,
        ),
        [_agent("Row", seat="0"), _agent("Column", seat="1")],
    )


def beauty():
    from examples.shared_state_dsl.shared_beauty_contest import SPEC

    q = QuestionNumerical(
        question_name="choice",
        question_text=(
            "Choose a number from 0 to 100. The winner is closest to two-thirds "
            "of the mean of all three choices."
        ),
        min_value=0,
        max_value=100,
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.submit(
            player=current.agent.name, choice=question.answer
        ),
        [_agent("A"), _agent("B"), _agent("C")],
    )


def market_entry():
    from examples.shared_state_dsl.shared_market_entry_game import SPEC

    q = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "Choose enter or stay_out. Staying out pays 2. Entry pays "
            "10 - 3 times the number of entrants. There are three players."
        ),
        question_options=["enter", "stay_out"],
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.submit(
            player=current.agent.name, action=question.answer
        ),
        [_agent("A"), _agent("B"), _agent("C")],
    )


def nash_demand():
    from examples.shared_state_dsl.shared_nash_demand_game import SPEC

    q = QuestionNumerical(
        question_name="amount",
        question_text=(
            "Demand 0–100 from a $100 pie. If the two demands sum to at most "
            "$100, each receives their demand; otherwise both receive $0."
        ),
        min_value=0,
        max_value=100,
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.demand(
            player=current.agent.name,
            seat=current.agent.seat,
            amount=question.answer,
        ),
        [_agent("A", seat="0"), _agent("B", seat="1")],
    )


def money_request():
    from examples.shared_state_dsl.shared_money_request_game import SPEC

    q = QuestionMultipleChoice(
        question_name="request",
        question_text=(
            "Request an integer from 11 through 20. You receive your request; "
            "if you request exactly one less than the other player, you also "
            "receive a $20 bonus."
        ),
        question_options=list(range(11, 21)),
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.submit(
            player=current.agent.name, request=question.answer
        ),
        [_agent("A"), _agent("B")],
    )


def common_pool():
    from examples.shared_state_dsl.shared_common_pool_game import SPEC

    q = QuestionNumerical(
        question_name="amount",
        question_text=(
            "Choose how much to extract from 0 through 20. Three players share "
            "a stock of 60; your payoff reflects your extraction and the stock "
            "remaining after everyone's extraction."
        ),
        min_value=0,
        max_value=20,
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.extract(
            player=current.agent.name, amount=question.answer
        ),
        [_agent("A"), _agent("B"), _agent("C")],
    )


def bilateral_trade():
    from examples.shared_state_dsl.shared_bilateral_trade import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-bilateral-{uuid4()}"
    )
    game = states.by("game").game
    offer = QuestionNumerical(
        question_name="price",
        question_text=(
            "You are Buyer. The object is worth $90 to you. Offer Seller a "
            "price from $0 through $90."
        ),
        min_value=0,
        max_value=90,
    )
    decision = QuestionMultipleChoice(
        question_name="decision",
        question_text=(
            "You are Seller and your private cost is $30. The current offer is "
            "{{ shared_state.game.price }}. Accept or reject it."
        ),
        question_options=["accept", "reject"],
    )
    survey = Survey(
        [
            game.read(),
            offer,
            game.offer(buyer=current.agent.name, buyer_value=90, price=offer.answer),
            game.read(),
            decision,
            game.respond(
                seller=current.agent.name,
                seller_cost=30,
                decision=decision.answer,
            ),
        ]
    )
    survey.add_skip_rule("price", "'{{ agent.role }}' != 'buyer'")
    survey.add_skip_rule("decision", "'{{ agent.role }}' != 'seller'")
    people = AgentList(
        [
            _agent("Buyer", role="buyer", game_id="game", turn=0),
            _agent("Seller", role="seller", game_id="game", turn=1),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "game_id", "turn", finalize_when=game.is_complete()
    )


def centipede():
    from examples.shared_state_dsl.shared_centipede_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-centipede-{uuid4()}"
    )
    game = states.by("game").game
    q = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "You move at node {{ agent.node }} of a three-node centipede game. "
            "Current history: {{ shared_state.game.history }}. Taking at nodes "
            "1, 2, 3 yields payoffs [2,0], [1,3], [4,2]. Passing at the final "
            "node yields [3,5]. Choose take or pass."
        ),
        question_options=["take", "pass"],
    )
    survey = Survey(
        [
            game.read(),
            q,
            game.move(
                player=current.agent.name,
                node=current.agent.node,
                action=q.answer,
            ),
        ]
    )
    people = AgentList(
        [
            _agent("Player A at node 1", game_id="game", node=1),
            _agent("Player B at node 2", game_id="game", node=2),
            _agent("Player A at node 3", game_id="game", node=3),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "game_id", "node", stop_when=game.is_complete(), finalize_when=game.is_complete()
    )


def cheap_talk():
    from examples.shared_state_dsl.shared_cheap_talk_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-cheap-talk-{uuid4()}"
    )
    game = states.by("game").game
    message = QuestionMultipleChoice(
        question_name="message",
        question_text=(
            "You are Sender. The private state is L and your preferences are "
            "aligned with Receiver. Send message L or R."
        ),
        question_options=["L", "R"],
    )
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "You are Receiver. Sender's message is "
            "{{ shared_state.game.message }}. Choose action L or R."
        ),
        question_options=["L", "R"],
    )
    survey = Survey(
        [
            game.read(),
            message,
            game.message(
                sender=current.agent.name,
                state="L",
                preference="aligned",
                message=message.answer,
            ),
            game.read(),
            action,
            game.act(receiver=current.agent.name, action=action.answer),
        ]
    )
    survey.add_skip_rule("message", "'{{ agent.role }}' != 'sender'")
    survey.add_skip_rule("action", "'{{ agent.role }}' != 'receiver'")
    people = AgentList(
        [
            _agent("Sender", role="sender", game_id="game", turn=0),
            _agent("Receiver", role="receiver", game_id="game", turn=1),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "game_id", "turn", finalize_when=game.is_complete()
    )


def signaling():
    from examples.shared_state_dsl.shared_signaling_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-signaling-{uuid4()}"
    )
    game = states.by("game").game
    education = QuestionMultipleChoice(
        question_name="education",
        question_text=(
            "You are a worker with productivity 90. A job pays 60 if hired. "
            "Each unit of education costs you 10; choose 0, 1, 2, or 3 units "
            "as a signal to the employer."
        ),
        question_options=[0, 1, 2, 3],
    )
    decision = QuestionMultipleChoice(
        question_name="decision",
        question_text=(
            "You are Employer. The worker chose education level "
            "{{ shared_state.game.education }}. Hiring pays productivity minus "
            "the wage of 60. Choose hire or do_not_hire."
        ),
        question_options=["hire", "do_not_hire"],
    )
    survey = Survey(
        [
            game.read(),
            education,
            game.signal(
                worker=current.agent.name,
                productivity=90,
                signal_cost=10,
                education=education.answer,
            ),
            game.read(),
            decision,
            game.decide(employer=current.agent.name, decision=decision.answer),
        ]
    )
    survey.add_skip_rule("education", "'{{ agent.role }}' != 'worker'")
    survey.add_skip_rule("decision", "'{{ agent.role }}' != 'employer'")
    people = AgentList(
        [
            _agent("Worker", role="worker", game_id="game", turn=0),
            _agent("Employer", role="employer", game_id="game", turn=1),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "game_id", "turn", finalize_when=game.is_complete()
    )


def principal_agent():
    from examples.shared_state_dsl.shared_principal_agent_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-principal-agent-{uuid4()}"
    )
    game = states.by("game").game
    bonus = QuestionNumerical(
        question_name="bonus",
        question_text=(
            "You are Firm. Output is worth 100. Offer a success bonus from 0 "
            "through 100. High effort succeeds with probability .8; low effort "
            "with .2. High effort privately costs Worker 20."
        ),
        min_value=0,
        max_value=100,
    )
    effort = QuestionMultipleChoice(
        question_name="effort",
        question_text=(
            "You are Worker. Firm offered success bonus "
            "{{ shared_state.game.bonus }}. High effort costs 20 and succeeds "
            "with probability .8; low effort is free and succeeds with .2."
        ),
        question_options=["high", "low"],
    )
    survey = Survey(
        [
            game.read(),
            bonus,
            game.contract(principal=current.agent.name, bonus=bonus.answer),
            game.read(),
            effort,
            game.effort(worker=current.agent.name, effort=effort.answer),
        ]
    )
    survey.add_skip_rule("bonus", "'{{ agent.role }}' != 'principal'")
    survey.add_skip_rule("effort", "'{{ agent.role }}' != 'worker'")
    people = AgentList(
        [
            _agent("Firm", role="principal", game_id="game", turn=0),
            _agent("Worker", role="worker", game_id="game", turn=1),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "game_id", "turn", finalize_when=game.is_complete()
    )


def sealed_auction():
    from examples.shared_state_dsl.shared_sealed_auction import SPEC

    q = QuestionNumerical(
        question_name="bid",
        question_text=(
            "This is a sealed second-price auction. Your private value is "
            "{{ agent.private_value }}. The highest bidder wins but pays the "
            "second-highest bid. Submit a nonnegative bid."
        ),
        min_value=0,
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.bid(
            bidder=current.agent.name,
            seat=current.agent.seat,
            private_value=current.agent.private_value,
            amount=question.answer,
        ),
        [
            _agent("A", seat=0, private_value=80),
            _agent("B", seat=1, private_value=70),
            _agent("C", seat=2, private_value=40),
        ],
    )


def ultimatum():
    from examples.shared_state_dsl.shared_ultimatum_game import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-ultimatum-{uuid4()}"
    )
    game = states.by(current.agent.pair_id).game
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
    people = AgentList(
        [
            _agent(
                "Proposer",
                role="proposer",
                pair_id="game",
                turn=0,
                generosity=0.2,
                inequity_aversion=0.4,
            ),
            _agent(
                "Responder",
                role="responder",
                pair_id="game",
                turn=1,
                generosity=0.0,
                inequity_aversion=0.8,
            ),
        ],
        traits_presentation_template=(
            "Your traits range from -1 to 1. generosity measures willingness "
            "to sacrifice payoff for another person; inequity_aversion measures "
            "opposition to unequal outcomes. Act consistently with these values."
        ),
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "pair_id", "turn", finalize_when=game.is_complete()
    )


def negotiation():
    from examples.shared_state_dsl.shared_negotiation import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-negotiation-{uuid4()}"
    )
    game = states.by("game").game
    offer = QuestionNumerical(
        question_name="offer",
        question_text=(
            "You are buying a used sailboat. Make a price offer from $0 through "
            "$100. Your value is $90; Seller's cost is $30."
        ),
        min_value=0,
        max_value=100,
    )
    response = QuestionMultipleChoice(
        question_name="response",
        question_text=(
            "You are Seller with cost $30. Negotiation so far: "
            "{{ shared_state.game.turns }}. Choose accept, reject, or walk away."
        ),
        question_options=["accept", "reject", "walk away"],
    )
    survey = Survey(
        [
            game.read(),
            offer,
            game.record(
                speaker=current.agent.name,
                role="buyer",
                action="offer",
                amount=offer.answer,
                message="My opening offer",
            ),
            game.read(),
            response,
            game.record(
                speaker=current.agent.name,
                role="seller",
                action=response.answer,
                amount=0,
                message="My response to the offer",
            ),
        ]
    )
    survey.add_skip_rule("offer", "'{{ agent.role }}' != 'buyer'")
    survey.add_skip_rule("response", "'{{ agent.role }}' != 'seller'")
    people = AgentList(
        [
            _agent("Buyer", role="buyer", game_id="game", turn=0),
            _agent("Seller", role="seller", game_id="game", turn=1),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "game_id", "turn", finalize_when=game.is_complete()
    )


def double_auction():
    from examples.shared_state_dsl.shared_double_auction import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-double-auction-{uuid4()}"
    )
    game = states.by("market").game
    price = QuestionNumerical(
        question_name="price",
        question_text=(
            "You are {{ agent.side }}ing one unit in a continuous double "
            "auction. {{ agent.private_instruction }} Submit a limit price."
        ),
        min_value=0,
        max_value=100,
    )
    survey = Survey(
        [
            game.read(),
            price,
            game.submit(
                trader=current.agent.name,
                round=1,
                action=current.agent.side,
                price=price.answer,
            ),
        ]
    )
    people = AgentList(
        [
            _agent(
                "Buyer",
                side="buy",
                private_instruction="Your value is $70; prefer paying less.",
            ),
            _agent(
                "Seller",
                side="sell",
                private_instruction="Your cost is $30; prefer receiving more.",
            ),
        ]
    )
    return survey, people, InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="snapshot"
    )


def voting():
    from examples.shared_state_dsl.shared_voting_game import SPEC

    q = QuestionRank(
        question_name="ranking",
        question_text=(
            "Rank candidates A, B, and C from most to least preferred. Your "
            "ideal candidate is {{ agent.ideal }}; your second choice is "
            "{{ agent.second }}."
        ),
        question_options=["A", "B", "C"],
        num_selections=3,
    )
    return _simultaneous(
        SPEC,
        "game",
        q,
        lambda game, question: game.vote(
            voter=current.agent.name, ranking=question.answer
        ),
        [
            _agent("Voter A", ideal="A", second="B"),
            _agent("Voter B", ideal="B", second="A"),
            _agent("Voter C", ideal="C", second="A"),
        ],
    )


def deferred_acceptance():
    from examples.shared_state_dsl.shared_deferred_acceptance import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-matching-{uuid4()}"
    )
    game = states.by("market").game
    ranking = QuestionRank(
        question_name="ranking",
        question_text=(
            "Rank North and South from most to least preferred. "
            "Your personal first choice is {{ agent.first_choice }}."
        ),
        question_options=["North", "South"],
        num_selections=2,
    )
    survey = Survey(
        [
            game.read(),
            ranking,
            game.collect(student=current.agent.name, ranking=ranking.answer),
        ]
    )
    people = AgentList(
        [
            _agent("A", role="student", market_id="market", turn=0, first_choice="North"),
            _agent("B", role="student", market_id="market", turn=1, first_choice="North"),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        group_by="market_id", order_by="turn", finalize_when=game.is_complete()
    )


def binary_market():
    from examples.shared_state_dsl.shared_binary_market import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-binary-market-{uuid4()}"
    )
    game = states.by("market").game
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "Trade an Event-occurs prediction contract. Current prices are "
            "{{ shared_state.game.prices }}. Your private probability is "
            "{{ agent.probability }}%. Choose buy_yes, buy_no, or hold."
        ),
        question_options=["buy_yes", "buy_no", "hold"],
    )
    quantity = QuestionNumerical(
        question_name="quantity",
        question_text="Choose a nonnegative trade quantity; use 0 if holding.",
        min_value=0,
        max_value=10,
    )
    outcome = QuestionMultipleChoice(
        question_name="outcome",
        question_text="Resolve the event as true or false.",
        question_options=[True, False],
    )
    survey = Survey(
        [
            game.read(),
            action,
            quantity,
            game.trade(
                trader=current.agent.name,
                action=action.answer,
                quantity=quantity.answer,
            ),
            outcome,
            game.settle(outcome=outcome.answer),
        ]
    )
    survey.add_skip_rule("action", "'{{ agent.role }}' != 'trader'")
    survey.add_skip_rule("quantity", "'{{ agent.role }}' != 'trader'")
    survey.add_skip_rule("outcome", "'{{ agent.role }}' != 'resolver'")
    people = AgentList(
        [
            _agent("Optimist", role="trader", market_id="market", turn=0, probability=75),
            _agent("Pessimist", role="trader", market_id="market", turn=1, probability=25),
            _agent("Resolver", role="resolver", market_id="market", turn=2, probability=50),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "market_id", "turn"
    )


def resource_allocation():
    from examples.shared_state_dsl.shared_resource_board import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-resource-{uuid4()}"
    )
    game = states.by("incident-board").game
    incident = QuestionMultipleChoice(
        question_name="incident",
        question_text=(
            "Choose an unassigned incident after reviewing the board: "
            "{{ shared_state.game }}. Fire needs an engine; injury needs an ambulance."
        ),
        question_options=["fire", "injury"],
    )
    survey = Survey(
        [
            game.read(),
            incident,
            game.allocate(
                responder=current.agent.name,
                round=1,
                incident=incident.answer,
                resource=current.agent.resource,
            ),
        ]
    )
    return survey, AgentList([
        _agent("Engine crew", resource="E1"),
        _agent("Ambulance crew", resource="A1"),
    ]), InterviewSchedule.rounds(
        count=1, within_round="serial", state_visibility="live"
    )


def delphi():
    from examples.shared_state_dsl.shared_delphi_panel import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-delphi-{uuid4()}"
    )
    game = states.by("panel").game
    estimate = QuestionNumerical(
        question_name="estimate",
        question_text=(
            "Estimate next year's demand. Your initial private estimate is "
            "{{ agent.initial_estimate }}. Current "
            "panel summaries are {{ shared_state.game.summaries }}. Revise if useful."
        ),
        min_value=0,
        max_value=100,
    )
    survey = Survey(
        [
            game.read(),
            estimate,
            game.submit(
                expert=current.agent.name,
                round=current.run.round,
                estimate=estimate.answer,
                confidence=80,
                rationale="Estimate informed by private view and panel summary",
            ),
        ]
    )
    people = AgentList(
        [
            _agent("Expert A", panel_id="panel", initial_estimate=45),
            _agent("Expert B", panel_id="panel", initial_estimate=55),
            _agent("Expert C", panel_id="panel", initial_estimate=65),
        ]
    )
    return survey, people, InterviewSchedule.rounds(
        count=2,
        group_by="panel_id",
        within_round="concurrent",
        state_visibility="snapshot",
        finalize_when=game.is_complete(),
    )


def agenda():
    from examples.shared_state_dsl.shared_agenda import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-agenda-{uuid4()}"
    )
    game = states.by("committee").game
    title = QuestionFreeText(
        question_name="title",
        question_text=(
            "Propose one concise weekend activity for the committee's agenda."
        ),
    )
    vote_a1 = QuestionMultipleChoice(
        question_name="vote_a1",
        question_text=(
            "Current agenda: {{ shared_state.game.proposals }}. Vote up, neutral, "
            "or down on proposal A1."
        ),
        question_options=["up", "neutral", "down"],
    )
    vote_a2 = QuestionMultipleChoice(
        question_name="vote_a2",
        question_text="Vote up, neutral, or down on proposal A2.",
        question_options=["up", "neutral", "down"],
    )
    survey = Survey(
        [
            game.read(),
            title,
            game.propose(proposer=current.agent.name, title=title.answer),
            game.read(),
            vote_a1,
            vote_a2,
            game.vote(
                voter=current.agent.name,
                votes={"A1": vote_a1.answer, "A2": vote_a2.answer},
            ),
        ]
    )
    survey.add_skip_rule("title", "'{{ agent.role }}' != 'proposer'")
    survey.add_skip_rule("vote_a1", "'{{ agent.role }}' != 'voter'")
    survey.add_skip_rule("vote_a2", "'{{ agent.role }}' != 'voter'")
    people = AgentList(
        [
            _agent("Proposer 1", role="proposer", committee_id="c", turn=0),
            _agent("Proposer 2", role="proposer", committee_id="c", turn=1),
            _agent("Voter 1", role="voter", committee_id="c", turn=2),
            _agent("Voter 2", role="voter", committee_id="c", turn=3),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "committee_id", "turn"
    )


def budget():
    from examples.shared_state_dsl.shared_budget_pool import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-budget-{uuid4()}"
    )
    game = states.by("budget").game
    amount = QuestionNumerical(
        question_name="amount",
        question_text=(
            "You represent the {{ agent.project }} project. Current shared budget: "
            "{{ shared_state.game }}. Request an amount from 0 through 100."
        ),
        min_value=0,
        max_value=100,
    )
    survey = Survey(
        [
            game.read(),
            amount,
            game.fund(
                sponsor=current.agent.name,
                project=current.agent.project,
                amount=amount.answer,
            ),
        ]
    )
    people = AgentList(
        [
            _agent("Park advocate", budget_id="budget", turn=0, project="park"),
            _agent("Library advocate", budget_id="budget", turn=1, project="library"),
            _agent("Chair", budget_id="budget", turn=2, project="library"),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "budget_id", "turn", stop_when=game.is_complete()
    )


def coalition():
    from examples.shared_state_dsl.shared_coalition_pool import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-coalition-{uuid4()}"
    )
    game = states.by("assembly").game
    choice = QuestionMultipleChoice(
        question_name="coalition",
        question_text=(
            "Choose red or blue. Each coalition has capacity two. Current "
            "membership is {{ shared_state.game.members }}."
        ),
        question_options=["red", "blue"],
    )
    survey = Survey(
        [
            game.read(),
            choice,
            game.request(
                member=current.agent.name,
                coalition=choice.answer,
                round=1,
            ),
        ]
    )
    people = AgentList(
        [_agent(f"Member {index}", assembly_id="assembly", turn=index) for index in range(5)]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "assembly_id", "turn"
    )


def serial_matching():
    from examples.shared_state_dsl.shared_match_pool import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-serial-matching-{uuid4()}"
    )
    game = states.by("market").game
    ranking = QuestionRank(
        question_name="ranking",
        question_text=(
            "Rank bike ride, sailing, hike, and beach day. Your stated favorite "
            "is {{ agent.favorite }}."
        ),
        question_options=["bike ride", "sailing", "hike", "beach day"],
        num_selections=4,
    )
    survey = Survey(
        [
            game.read(),
            ranking,
            game.collect(
                claimant=current.agent.name,
                priority=current.agent.priority,
                ranking=ranking.answer,
            ),
        ]
    )
    people = AgentList(
        [
            _agent("A", role="claimant", market_id="market", turn=0, priority=1, favorite="hike"),
            _agent("B", role="claimant", market_id="market", turn=1, priority=2, favorite="hike"),
            _agent("C", role="claimant", market_id="market", turn=2, priority=3, favorite="sailing"),
        ]
    )
    return survey, people, InterviewSchedule.grouped_round_robin(
        "market_id", "turn", finalize_when=game.is_complete()
    )


def forecast():
    from examples.shared_state_dsl.shared_forecast import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-forecast-{uuid4()}"
    )
    game = states.by("panel").game
    probability = QuestionNumerical(
        question_name="probability",
        question_text=(
            "Estimate the probability (0–100) that the event occurs. Your "
            "private initial belief is {{ agent.initial }}. Current consensus: "
            "{{ shared_state.game }}."
        ),
        min_value=0,
        max_value=100,
    )
    survey = Survey(
        [
            game.read(),
            probability,
            game.submit(
                forecaster=current.agent.name,
                round=current.run.round,
                probability=probability.answer,
                confidence=current.agent.confidence,
            ),
        ]
    )
    people = AgentList(
        [
            _agent("Forecaster A", panel_id="panel", initial=30, confidence=75),
            _agent("Forecaster B", panel_id="panel", initial=50, confidence=80),
            _agent("Forecaster C", panel_id="panel", initial=70, confidence=70),
        ]
    )
    return survey, people, InterviewSchedule.rounds(
        count=2,
        group_by="panel_id",
        within_round="concurrent",
        state_visibility="snapshot",
    )


def private_signal():
    from examples.shared_state_dsl.shared_signal_schedule import SPEC

    states = SharedStateMap(
        SharedState(game=SPEC), state_id=f"gemini-private-signal-{uuid4()}"
    )
    game = states.by("signals").game
    reaction = QuestionFreeText(
        question_name="reaction",
        question_text=(
            "Your newly revealed private signal is "
            "{{ shared_state.game.your_signal }}. Briefly interpret it."
        ),
    )
    survey = Survey(
        [
            game.reveal(
                participant=current.agent.name,
                round=current.run.round,
            ),
            game.read(),
            reaction,
        ]
    )
    people = AgentList(
        [_agent("Amina", signal_group="signals"), _agent("Boris", signal_group="signals")]
    )
    return survey, people, InterviewSchedule.rounds(
        count=2,
        group_by="signal_group",
        within_round="concurrent",
        state_visibility="live",
    )


def ascending_auction():
    from examples.shared_state_dsl.shared_auction import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-ascending-{uuid4()}")
    game = states.by("auction").game
    bid = QuestionNumerical(
        question_name="bid",
        question_text=("Bid for a sailboat lesson. Your private value is {{ agent.value }}. "
                       "Current auction: {{ shared_state.game }}."),
        min_value=0,
    )
    survey = Survey([game.read(), bid, game.bid(amount=bid.answer)])
    people = AgentList([_agent("Bidder A", auction_id="a", turn=0, value=45),
                        _agent("Bidder B", auction_id="a", turn=1, value=65),
                        _agent("Bidder C", auction_id="a", turn=2, value=55)])
    return survey, people, InterviewSchedule.grouped_round_robin(
        "auction_id", "turn", finalize_when=game.is_complete()
    )


def counter():
    from examples.shared_state_dsl.shared_counter_map import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-counter-{uuid4()}")
    game = states.by("group").game
    q = QuestionMultipleChoice(
        question_name="activity",
        question_text="Choose the best group activity for this weekend.",
        question_options=["bike ride", "sailing", "hike", "beach day"],
    )
    survey = Survey([game.read(), q, game.tally(values=[q.answer])])
    return survey, AgentList([_agent(f"Chooser {i}") for i in range(4)]), InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="snapshot"
    )


def document():
    from examples.shared_state_dsl.shared_document import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-document-{uuid4()}")
    game = states.by("plan").game
    text = QuestionFreeText(
        question_name="text",
        question_text=("Revise the activity plan into one useful sentence. Current document: "
                       "{{ shared_state.game.text }}."),
    )
    survey = Survey([game.read(), text,
                     game.revise(author=current.agent.name, round=current.agent.turn,
                                 text=text.answer,
                                 rationale="Improve clarity and make the plan actionable")])
    people = AgentList([_agent("Editor 1", plan_id="p", turn=1),
                        _agent("Editor 2", plan_id="p", turn=2),
                        _agent("Editor 3", plan_id="p", turn=3)])
    return survey, people, InterviewSchedule.grouped_round_robin("plan_id", "turn")


def log():
    from examples.shared_state_dsl.shared_log import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-log-{uuid4()}")
    game = states.by("field-study").game
    note = QuestionFreeText(
        question_name="note",
        question_text="Record one concise observation about cooperation in the group.",
    )
    survey = Survey([game.read(), note,
                     game.append(entry={"author": current.agent.name, "note": note.answer})])
    return survey, AgentList([_agent(f"Observer {i}") for i in range(3)]), InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="snapshot"
    )


def message_board():
    from examples.shared_state_dsl.shared_message_board import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-board-{uuid4()}")
    game = states.by("board").game
    message = QuestionFreeText(
        question_name="message",
        question_text=("Post a constructive message about choosing a weekend activity. "
                       "Existing messages: {{ shared_state.game.messages }}."),
    )
    survey = Survey([game.read(), message,
                     game.add(author=current.agent.name, message=message.answer, reply_to=None)])
    people = AgentList([_agent(f"Member {i}", board_id="b", turn=i) for i in range(3)])
    return survey, people, InterviewSchedule.grouped_round_robin("board_id", "turn")


def register():
    from examples.shared_state_dsl.shared_register import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-register-{uuid4()}")
    game = states.by("preferences").game
    q = QuestionMultipleChoice(
        question_name="preference", question_text="Register your preferred activity.",
        question_options=["bike ride", "sailing", "hike", "beach day"],
    )
    survey = Survey([game.read(), q, game.set(key=current.agent.name, value=q.answer)])
    return survey, AgentList([_agent(f"Person {i}") for i in range(3)]), InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="snapshot"
    )


def repeated_matrix():
    from examples.shared_state_dsl.shared_repeated_matrix_game import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-repeated-matrix-{uuid4()}")
    game = states.by("match").game
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=("Choose cooperate or defect in round {{ agent.round_hint }}. "
                       "Previous play: {{ shared_state.game.rounds }}. Standard payoffs are "
                       "CC=3 each, DC=5/0, DD=1 each."),
        question_options=["cooperate", "defect"],
    )
    survey = Survey([game.read(), action,
                     game.submit(player=current.agent.name, seat=current.agent.seat,
                                 round=current.run.round, action=action.answer)])
    people = AgentList([_agent("Row", match_id="m", seat="0", round_hint="the current"),
                        _agent("Column", match_id="m", seat="1", round_hint="the current")])
    return survey, people, InterviewSchedule.rounds(
        count=3, group_by="match_id", within_round="concurrent",
        state_visibility="snapshot", finalize_when=game.is_complete()
    )


def work_pool():
    from examples.shared_state_dsl.shared_work_pool import SPEC
    states = SharedStateMap(SharedState(game=SPEC), state_id=f"gemini-work-{uuid4()}")
    game = states.by("queue").game
    result = QuestionFreeText(
        question_name="result",
        question_text=("You atomically claimed work item {{ shared_state.game.claims }}. "
                       "Return a short completion note for your item."),
    )
    survey = Survey([game.claim_before(claimant=current.agent.name), game.read(), result,
                     game.complete(claimant=current.agent.name,
                                   result={"note": result.answer})])
    return survey, AgentList([_agent("Worker A"), _agent("Worker B")]), InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="live"
    )


GAMES = {
    "dictator": dictator,
    "trust": trust,
    "matrix": matrix,
    "beauty": beauty,
    "market_entry": market_entry,
    "nash_demand": nash_demand,
    "money_request": money_request,
    "common_pool": common_pool,
    "bilateral_trade": bilateral_trade,
    "centipede": centipede,
    "cheap_talk": cheap_talk,
    "signaling": signaling,
    "principal_agent": principal_agent,
    "sealed_auction": sealed_auction,
    "ultimatum": ultimatum,
    "negotiation": negotiation,
    "double_auction": double_auction,
    "voting": voting,
    "deferred_acceptance": deferred_acceptance,
    "binary_market": binary_market,
    "resource_allocation": resource_allocation,
    "delphi": delphi,
    "agenda": agenda,
    "budget": budget,
    "coalition": coalition,
    "serial_matching": serial_matching,
    "forecast": forecast,
    "private_signal": private_signal,
    "ascending_auction": ascending_auction,
    "counter": counter,
    "document": document,
    "log": log,
    "message_board": message_board,
    "register": register,
    "repeated_matrix": repeated_matrix,
    "work_pool": work_pool,
}


def run_game(name: str, model_name: str = MODEL) -> dict:
    survey, agents, schedule = GAMES[name]()
    results = (
        survey.by(agents)
        .by(Model(model_name, service_name="google"))
        .run(
            cache=False,
            disable_remote_cache=True,
            disable_remote_inference=True,
            interview_schedule=schedule,
            max_concurrency=5,
            stop_on_exceptions=True,
        )
    )
    binding = results.shared_state["bindings"][0]
    writes = [event for event in binding["events"] if event["kind"] == "write"]
    return {
        "game": name,
        "answers": [row.answer for row in results],
        "commands": [event["command"] for event in writes],
        "final_state": binding["exit_snapshots"][0]["state"],
        "read_versions": [
            event["version"]
            for event in binding["events"]
            if event["kind"] == "read"
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", action="append", choices=sorted(GAMES))
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Maximum seconds allowed for each game; zero disables the limit.",
    )
    args = parser.parse_args()
    selected = args.game or list(GAMES)
    report = {"model": args.model, "runs": []}
    for name in selected:
        print(f"Running {name}...", flush=True)
        previous = signal.getsignal(signal.SIGALRM)

        def timed_out(signum, frame):
            raise TimeoutError(
                f"{name} exceeded the {args.timeout}-second smoke-test limit"
            )

        try:
            if args.timeout:
                signal.signal(signal.SIGALRM, timed_out)
                signal.alarm(args.timeout)
            report["runs"].append(run_game(name, args.model))
        except TimeoutError as exc:
            report["runs"].append(
                {"game": name, "status": "timeout", "error": str(exc)}
            )
            print(str(exc), flush=True)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
    rendered = json.dumps(report, indent=2, default=str)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
