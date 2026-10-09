"""Adaptive question coverage in one pass: python -m examples.question_coverage."""

from collections import Counter
import json

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionCompute,
    QuestionLinearScale,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.machine_primitives.question_coverage import (
    DEFAULT_QUESTIONS,
    build_machine,
)


def build_survey(
    *, state_id=None, question_ids=DEFAULT_QUESTIONS, target=10, per_agent=3
):
    spec = build_machine(question_ids, target, per_agent)
    states = SharedStateMap(SharedState(coverage=spec), state_id=state_id)
    coverage = states.by(current.agent.study_id).coverage
    slots = [
        QuestionCompute(
            question_name=f"coverage_slot_{i + 1}",
            question_text="{{ shared_state.coverage.pending["
            + str(i)
            + "] if shared_state.coverage.pending | length > "
            + str(i)
            + " else 'coverage_none' }}",
        )
        for i in range(per_agent)
    ]
    questions = [
        QuestionLinearScale(
            question_name=q,
            question_text=f"How useful would feature {q} be to you?",
            question_options=[1, 2, 3, 4, 5],
            option_labels={1: "Not useful", 5: "Very useful"},
        )
        for q in spec.constants["questions"]
    ]
    steps = [
        coverage.assign(respondent_id=current.agent.respondent_id),
        coverage.read(),
        *slots,
    ]
    for question in questions:
        steps.extend(
            [
                question,
                coverage.record_answer(
                    respondent_id=current.agent.respondent_id,
                    question=question.question_name,
                    answer=question.answer,
                ),
            ]
        )
    survey = Survey(steps)
    survey.add_stop_rule(slots[0], "{{ coverage_slot_1.answer }} == 'coverage_none'")
    assigned_slots = (
        "["
        + ", ".join("{{ " + slot.question_name + ".answer }}" for slot in slots)
        + "]"
    )
    for question in questions:
        survey.add_skip_rule(
            question, f"{question.question_name!r} not in {assigned_slots}"
        )
    schedule = InterviewSchedule.grouped_round_robin(
        "study_id", "turn", stop_when=coverage.is_complete()
    )
    return survey, states, schedule


def demo_answer(self, question, scenario):
    return 3


def demo_agents(count=100):
    if type(count) is not int or count < 1:
        raise ValueError("population count must be a positive integer")
    agents = AgentList()
    for i in range(count):
        agent = Agent(
            name=f"respondent-{i}",
            traits={"respondent_id": f"R{i}", "study_id": "study", "turn": i},
        )
        agent.add_direct_question_answering_method(demo_answer)
        agents.append(agent)
    return agents


def run_demo(count=100):
    from edsl.runner import Runner

    survey, _, schedule = build_survey()
    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(demo_agents(count)).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    writes = [
        e for e in results.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    state = writes[-1]["state"]["coverage"]
    distribution = Counter()
    for row in results:
        respondent = row.agent.traits["respondent_id"]
        answered = {
            q: row.answer[q] for q in DEFAULT_QUESTIONS if row.answer.get(q) is not None
        }
        assert answered == state["answers"].get(respondent, {})
        if answered:
            distribution[len(answered)] += 1
    total = sum(state["counts"].values())
    return {
        "population_size": count,
        "agents_answering": sum(distribution.values()),
        "answers_per_agent": dict(sorted(distribution.items())),
        "total_answers": total,
        "counts": state["counts"],
        "stop_reason": "coverage_complete" if total == 200 else "population_exhausted",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
