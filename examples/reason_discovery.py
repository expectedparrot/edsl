"""Adaptive reason discovery without model calls: python -m examples.reason_discovery."""

import json

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionCompute,
    QuestionFreeText,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current, seeded_integer
from edsl.sharedstate.dsl_runtime import Runtime
from examples.machine_primitives.reason_discovery import DEFAULT_SEEDS, build_machine

# Ground truth belongs to the simulated population, never to the discovery Machine.
ALL_REASONS = (*DEFAULT_SEEDS, "Convenience", "Recommendation", "Habit")


def build_survey(*, state_id=None, seed_reasons=DEFAULT_SEEDS, patience=10):
    states = SharedStateMap(
        SharedState(discovery=build_machine(seed_reasons, patience)), state_id=state_id
    )
    discovery = states.by(current.agent.study_id).discovery
    gate = QuestionCompute(
        question_name="discovery_gate",
        question_text="{{ 'open' if shared_state.discovery.accepting else 'closed' }}",
    )
    reason = QuestionMultipleChoice(
        question_name="reason",
        question_text="Why did you choose this product? Choose Other if your reason is not listed.",
        question_options="{{ shared_state.discovery.options }}",
    )
    other = QuestionFreeText(
        question_name="other_reason",
        question_text="What was your other reason for choosing this product?",
    )
    survey = Survey(
        [
            discovery.read(),
            gate,
            reason,
            discovery.select(
                respondent_id=current.agent.respondent_id, reason=reason.answer
            ),
            other,
            discovery.suggest(
                respondent_id=current.agent.respondent_id, reason=other.answer
            ),
        ]
    )
    survey.add_stop_rule(gate, "{{ discovery_gate.answer }} != 'open'")
    survey.add_skip_rule(other, "{{ reason.answer }} != 'Other'")
    schedule = InterviewSchedule.grouped_round_robin(
        "study_id", "turn", stop_when=discovery.is_complete()
    )
    return survey, states, schedule


def demo_answer(self, question, scenario):
    truth = self.traits["true_reason"]
    if question.question_name == "reason":
        return truth if truth in question.question_options else "Other"
    if question.question_name == "other_reason":
        return truth
    raise ValueError(f"Unexpected respondent question {question.question_name}")


def make_agent(index, reason, study_id="study"):
    agent = Agent(
        name=f"respondent-{index}",
        traits={
            "respondent_id": f"R{index}",
            "study_id": study_id,
            "turn": index,
            "true_reason": reason,
        },
    )
    agent.add_direct_question_answering_method(demo_answer)
    return agent


def demo_agents(seed="reason-discovery-2026", count=100):
    if type(count) is not int or count < 1:
        raise ValueError("population count must be a positive integer")
    runtime = Runtime()
    return AgentList(
        [
            make_agent(
                i,
                ALL_REASONS[
                    runtime.evaluate(
                        seeded_integer(
                            seed,
                            0,
                            len(ALL_REASONS),
                            scope="population",
                            key=f"agent-{i}",
                        ),
                        {},
                    )
                ],
            )
            for i in range(count)
        ]
    )


def run_demo(seed="reason-discovery-2026", count=100):
    from edsl.runner import Runner

    survey, _, schedule = build_survey()
    people = demo_agents(seed, count)
    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(people).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    binding = results.shared_state["bindings"][0]
    writes = [e for e in binding["events"] if e["kind"] == "write"]
    final = (
        writes[-1]["state"]["discovery"]
        if writes
        else Runtime().initial_state(build_machine())
    )
    history = [
        {
            "respondent_id": e["inputs"]["respondent_id"],
            "reason": e["inputs"]["reason"],
            "reasons_known": len(e["state"]["discovery"]["reasons"]),
            "quiet_streak": e["state"]["discovery"]["quiet_streak"],
        }
        for e in writes
        if e["status"] == "applied"
    ]
    return {
        "seed": seed,
        "seed_reasons": list(DEFAULT_SEEDS),
        "population_size": count,
        "interviewed": len(final["responses"]),
        "reasons_discovered": final["reasons"],
        "quiet_streak": final["quiet_streak"],
        "stop_reason": (
            "saturation" if final["quiet_streak"] >= 10 else "population_exhausted"
        ),
        "undiscovered_ground_truth": [
            r for r in ALL_REASONS if r not in final["reasons"]
        ],
        "history": history,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
