"""End-to-end Runner tests for representative shared-state games."""

from __future__ import annotations

from uuid import uuid4

import pytest

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMatrix,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    append,
    current,
    field,
    input_,
    record,
    state_field,
)


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


def test_shared_state_matrix_rows_use_rendered_schema_for_validation():
    activities = ["Bike ride", "Sailing"]
    definition = Machine(
        name="Poll",
        constants={},
        fields={
            "activities": state_field(T.sequence(T.text()), activities),
            "ballots": state_field(T.sequence(), []),
        },
        commands={
            "vote": Command(
                inputs={"voter": T.text(), "votes": T.map()},
                effects=(
                    append(
                        "ballots",
                        record(voter=input_("voter"), votes=input_("votes")),
                    ),
                ),
            )
        },
        view={"activities": field("activities"), "ballots": field("ballots")},
    )
    states = SharedStateMap(
        SharedState(poll=definition), state_id=f"matrix-validation-{uuid4()}"
    )
    poll = states.by("committee").poll
    ballot = QuestionMatrix(
        question_name="ballot",
        question_text="Vote on each proposed activity.",
        question_items="{{ shared_state.poll.activities }}",
        question_options=["up", "neutral", "down"],
    )
    survey = Survey(
        [
            poll.read(),
            ballot,
            poll.vote(voter=current.agent.name, votes=ballot.answer),
        ]
    )

    results = (
        survey.by(Agent(name="Avery"))
        .by(Model("test", canned_response='{"0": 0, "1": 2}'))
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )

    assert results[0].answer["ballot"] == {
        "Bike ride": "up",
        "Sailing": "down",
    }
    assert results[0].data["validated_dict"]["ballot_validated"] is True
    events = results.shared_state["bindings"][0]["events"]
    vote = next(event for event in events if event.get("command") == "vote")
    assert vote["inputs"]["votes"] == {
        "Bike ride": "up",
        "Sailing": "down",
    }


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


def test_state_read_persists_and_supports_dynamic_jinja_lookup():
    from edsl import QuestionFreeText
    from edsl.sharedstate import Command, Machine, T, field, set_, state_field

    spec = Machine(
        name="PersistentRead",
        constants={},
        fields={
            "claims": state_field(
                T.map(T.text(), T.map()), {"Alice": {"id": "P1"}}
            )
        },
        commands={
            "replace": Command(
                inputs={},
                effects=(set_("claims", {"Alice": {"id": "P2"}}),),
            )
        },
        view={"claims": field("claims")},
    )
    states = SharedStateMap(
        SharedState(game=spec), state_id=f"persistent-read-{uuid4()}"
    )
    game = states.by("review").game
    first = QuestionFreeText(
        question_name="first",
        question_text=(
            "First assignment: "
            "{{ shared_state.game.claims[agent.name].id }}"
        ),
    )
    second = QuestionFreeText(
        question_name="second",
        question_text=(
            "Same snapshot: "
            "{{ shared_state.game.claims.get(agent.name).id }}"
        ),
    )
    refreshed = QuestionFreeText(
        question_name="refreshed",
        question_text=(
            "Refreshed assignment: "
            "{{ shared_state.game.claims[agent.name].id }}"
        ),
    )
    results = _run(
        Survey(
            [
                game.read(),
                first,
                game.replace(),
                second,
                game.read(),
                refreshed,
            ]
        ),
        [Agent(name="Alice")],
        InterviewSchedule.rounds(
            count=1, within_round="serial", state_visibility="live"
        ),
    )

    prompts = results[0].data["prompt"]
    assert "First assignment: P1" in prompts["first_user_prompt"].text
    assert "Same snapshot: P1" in prompts["second_user_prompt"].text
    assert "Refreshed assignment: P2" in prompts["refreshed_user_prompt"].text
    events = results.shared_state["bindings"][0]["events"]
    assert [event["kind"] for event in events].count("read") == 2


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
