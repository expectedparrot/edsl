"""One-pass booking survey: python -m examples.appointment_booking."""

import json
from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionCompute,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.machine_primitives.appointment_booking import DEFAULT_SLOTS, build_machine


def build_survey(*, state_id=None, slots=DEFAULT_SLOTS):
    states = SharedStateMap(
        SharedState(booking=build_machine(slots)), state_id=state_id
    )
    booking = states.by(current.agent.study_id).booking
    available = QuestionCompute(
        question_name="availability",
        question_text="{{ 'open' if shared_state.booking.options and shared_state.booking.status in ['missing', 'held'] else 'closed' }}",
    )
    slot = QuestionMultipleChoice(
        question_name="slot",
        question_text="Which appointment would you like?",
        question_options="{{ shared_state.booking.options }}",
    )
    held = QuestionCompute(
        question_name="hold_status", question_text="{{ shared_state.booking.status }}"
    )
    decision = QuestionMultipleChoice(
        question_name="confirmation",
        question_text="Confirm your held appointment or release it?",
        question_options=["Confirm", "Release"],
    )
    outcome = QuestionCompute(
        question_name="booking_outcome",
        question_text="{{ shared_state.booking.status }}",
    )
    survey = Survey(
        [
            booking.read(),
            available,
            slot,
            booking.hold(
                respondent_id=current.agent.respondent_id,
                reservation_id=current.agent.reservation_id,
                slot=slot.answer,
            ),
            booking.read(),
            held,
            decision,
            booking.decide(
                respondent_id=current.agent.respondent_id,
                reservation_id=current.agent.reservation_id,
                decision=decision.answer,
            ),
            booking.read(),
            outcome,
        ]
    )
    survey.add_stop_rule(available, "{{ availability.answer }} != 'open'")
    survey.add_stop_rule(held, "{{ hold_status.answer }} != 'held'")
    # Do not stop on temporary fullness: later cancellation may release a seat.
    schedule = InterviewSchedule.grouped_round_robin("study_id", "turn")
    return survey, states, schedule


def demo_answer(self, question, scenario):
    if question.question_name == "slot":
        return question.question_options[0]
    return self.traits["decision"]


def demo_agents():
    agents = AgentList()
    for i, decision in enumerate(
        ["Release", "Confirm", "Confirm", "Confirm", "Confirm"]
    ):
        agent = Agent(
            traits={
                "respondent_id": f"R{i}",
                "reservation_id": f"booking-{i}",
                "study_id": "study",
                "turn": i,
                "decision": decision,
            }
        )
        agent.add_direct_question_answering_method(demo_answer)
        agents.append(agent)
    return agents


def run_demo():
    from edsl.runner import Runner

    survey, _, schedule = build_survey()
    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(demo_agents()).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    rows = {r.agent.traits["respondent_id"]: r for r in results}
    assert rows["R0"].answer["booking_outcome"] == "released"
    assert rows["R1"].answer["slot"] == rows["R0"].answer["slot"] == "09:00"
    assert rows["R4"].answer.get("slot") is None
    assert all(
        rows[f"R{i}"].answer["booking_outcome"] == "confirmed" for i in (1, 2, 3)
    )
    return {
        "confirmed": 3,
        "released": 1,
        "unavailable": 1,
        "slots_shown": {
            rid: row.get_question_options("slot")
            for rid, row in rows.items()
            if row.answer.get("slot") is not None
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
