"""Ask characteristics, then assign an arm: python -m examples.balanced_assignment."""

import json
from collections import Counter
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
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.machine_primitives.balanced_assignment import (
    AGES,
    EXPERIENCE,
    build_machine,
)


def build_survey(*, state_id=None, seed="balanced-2026"):
    states = SharedStateMap(SharedState(balance=build_machine(seed)), state_id=state_id)
    balance = states.by(current.agent.study_id).balance
    age = QuestionMultipleChoice(
        question_name="age_group",
        question_text="Which age band describes you?",
        question_options=list(AGES),
    )
    experience = QuestionMultipleChoice(
        question_name="experience",
        question_text="How much prior experience do you have?",
        question_options=list(EXPERIENCE),
    )
    arm = QuestionCompute(
        question_name="assigned_arm",
        question_text="{{ shared_state.balance.arm if shared_state.balance.age == age_group.answer and shared_state.balance.experience == experience.answer else 'unassigned' }}",
    )
    response = QuestionFreeText(
        question_name="response",
        question_text="Your assigned condition is {{ assigned_arm.answer }}. What do you think of the proposal?",
    )
    survey = Survey(
        [
            age,
            experience,
            balance.assign(
                respondent_id=current.agent.respondent_id,
                age=age.answer,
                experience=experience.answer,
            ),
            balance.read(),
            arm,
            response,
        ]
    )
    survey.add_stop_rule(arm, "{{ assigned_arm.answer }} == 'unassigned'")
    return survey, states, InterviewSchedule.grouped_round_robin("study_id", "turn")


def demo_answer(self, question, scenario):
    if question.question_name in ("age_group", "experience"):
        return self.traits[question.question_name]
    return "A clear proposal."


def demo_agents(count=12):
    agents = AgentList()
    for i in range(count):
        agent = Agent(
            traits={
                "respondent_id": f"R{i}",
                "study_id": "study",
                "turn": i,
                "age_group": AGES[i % 2],
                "experience": EXPERIENCE[(i // 2) % 2],
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
    counts = Counter(r.answer["assigned_arm"] for r in results)
    assert dict(counts) == {"Control": 6, "Treatment": 6}
    assert all(r.answer["response"] == "A clear proposal." for r in results)
    return {
        "counts": dict(counts),
        "assignments": {
            r.agent.traits["respondent_id"]: r.answer["assigned_arm"] for r in results
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
