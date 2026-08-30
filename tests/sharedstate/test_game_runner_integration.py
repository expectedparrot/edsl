"""End-to-end Runner tests for representative shared-state games."""

from __future__ import annotations

from uuid import uuid4

import pytest

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current


def _run(survey, agents, schedule):
    return (
        survey.by(AgentList(agents))
        .by(Model("test"))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )


def test_ultimatum_game_runs_in_role_order_and_finalizes_each_pair():
    from examples.economic_game_ultimatum import build_survey

    survey, complete = build_survey(f"runner-ultimatum-{uuid4()}")
    people = []
    for pair in range(2):
        for turn, role in enumerate(("proposer", "responder")):
            agent = Agent(
                name=f"pair-{pair}-{role}",
                traits={"pair_id": f"pair-{pair}", "turn": turn, "role": role},
            )

            def answer(self, question, scenario):
                if question.question_name == "offer":
                    return 35
                assert scenario["shared_state"]["game"]["offer"] == 35
                return "accept"

            agent.add_direct_question_answering_method(answer)
            people.append(agent)

    results = _run(
        survey,
        people,
        InterviewSchedule.grouped_round_robin(
            "pair_id", "turn", finalize_when=complete
        ),
    )
    binding = results.shared_state["bindings"][0]
    writes = [event for event in binding["events"] if event["kind"] == "write"]

    assert len(writes) == 6  # offer, response, and automatic close for each pair
    for scope in ("pair-0", "pair-1"):
        scoped = [event for event in writes if event["scope"] == scope]
        assert [event["command"] for event in scoped] == [
            "offer",
            "respond",
            "$close",
        ]
        assert [event["version"] for event in scoped] == [1, 2, 3]
    assert {row.answer["decision"] for row in results if row.agent.traits["role"] == "responder"} == {"accept"}


def test_sealed_auction_uses_snapshot_visibility_then_finalizes():
    from examples.shared_state_dsl.shared_sealed_auction import SPEC

    states = SharedStateMap(
        SharedState(auction=SPEC), state_id=f"runner-auction-{uuid4()}"
    )
    auction = states.by("sale").auction
    bid = QuestionNumerical(
        question_name="bid",
        question_text="Submit your sealed bid.",
        min_value=0,
    )
    survey = Survey(
        [
            auction.read(),
            bid,
            auction.bid(
                bidder=current.agent.name,
                seat=current.agent.seat,
                private_value=current.agent.private_value,
                amount=bid.answer,
            ),
        ]
    )
    people = []
    for seat, (name, value, amount) in enumerate(
        (("A", 80, 60), ("B", 70, 50), ("C", 40, 30))
    ):
        agent = Agent(name=name, traits={"seat": seat, "private_value": value})

        def answer(self, question, scenario, chosen=amount):
            assert scenario["shared_state"]["auction"]["bids"] == {}
            return chosen

        agent.add_direct_question_answering_method(answer)
        people.append(agent)

    results = _run(
        survey,
        people,
        InterviewSchedule.rounds(
            count=1,
            within_round="concurrent",
            state_visibility="snapshot",
            finalize_when=auction.is_complete(),
        ),
    )
    binding = results.shared_state["bindings"][0]
    reads = [event for event in binding["events"] if event["kind"] == "read"]
    writes = [event for event in binding["events"] if event["kind"] == "write"]

    assert {event["version"] for event in reads} == {0}
    assert [event["command"] for event in writes].count("bid") == 3
    assert writes[-1]["command"] == "$close"
    final = binding["exit_snapshots"][0]["state"]["auction"]
    assert final["winner"] == "A"
    assert final["price"] == 50
    assert final["utilities"] == {"A": 30, "B": 0, "C": 0}


def test_before_question_write_is_visible_to_live_private_read():
    from examples.shared_state_gemini_game_smoke import private_signal

    survey, people, schedule = private_signal()
    expected = {
        ("Amina", 1): "sunny",
        ("Amina", 2): "windy",
        ("Boris", 1): "cloudy",
        ("Boris", 2): "calm",
    }
    for agent in people:
        def answer(self, question, scenario):
            round_number = len(
                scenario["shared_state"]["game"]["your_signal_history"]
            )
            signal = scenario["shared_state"]["game"]["your_signal"]
            assert signal == expected[(self.name, round_number)]
            return signal

        agent.add_direct_question_answering_method(answer)

    results = _run(survey, list(people), schedule)
    events = results.shared_state["bindings"][0]["events"]
    assert [event["version"] for event in events if event["kind"] == "read"] == [
        1,
        2,
        3,
        4,
    ]


def test_sequential_is_a_checked_alias_for_serial_rounds():
    schedule = InterviewSchedule.rounds(count=1, within_round="sequential")
    assert schedule.within_round == "serial"


def test_concurrent_snapshot_rejects_before_question_writes():
    from edsl.jobs.exceptions import JobsValueError
    from examples.shared_state_gemini_game_smoke import private_signal

    survey, people, _ = private_signal()
    unsafe = InterviewSchedule.rounds(
        count=2,
        group_by="signal_group",
        within_round="concurrent",
        state_visibility="snapshot",
    )
    with pytest.raises(JobsValueError, match="pre-round write barriers"):
        (
            survey.by(people)
            .by(Model("test"))
            .run(
                interview_schedule=unsafe,
                disable_remote_inference=True,
                disable_remote_cache=True,
                cache=False,
            )
        )
