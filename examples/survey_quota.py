"""Run quota screening locally, without model calls: python -m examples.survey_quota."""

import json

from edsl import (
    Agent,
    AgentList,
    Model,
    QuestionCompute,
    QuestionFreeText,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.machine_primitives.survey_quota import build_machine


def build_survey(*, state_id=None, quota_a=10, quota_b=10):
    """Return the survey and its resumable state map. One scope covers the study."""
    states = SharedStateMap(
        SharedState(quota=build_machine(quota_a, quota_b)), state_id=state_id
    )
    quota = states.by("study").quota
    enrollment = QuestionCompute(
        question_name="enrollment_gate",
        question_text="{{ 'open' if shared_state.quota.accepting or shared_state.quota.admitted else 'closed' }}",
    )
    screen = QuestionMultipleChoice(
        question_name="respondent_type",
        question_text="Which group describes you?",
        question_options=["A", "B", "Other"],
    )
    gate = QuestionCompute(
        question_name="quota_gate",
        question_text="{{ 'admitted' if shared_state.quota.admitted and shared_state.quota.your_group == respondent_type.answer else 'screened_out' }}",
    )
    main = QuestionFreeText(
        question_name="experience",
        question_text="What would you most like to improve about your experience?",
    )
    survey = Survey(
        [
            quota.read(),
            enrollment,
            screen,
            quota.screen(
                respondent_id=current.agent.respondent_id, group=screen.answer
            ),
            quota.read(),
            gate,
            main,
        ]
    )
    survey.add_stop_rule(enrollment, "{{ enrollment_gate.answer }} != 'open'")
    survey.add_stop_rule(gate, "{{ quota_gate.answer }} != 'admitted'")
    return survey, states


def demo_agents():
    """12 of each eligible type and three other respondents, with stable IDs."""
    people = AgentList()
    for index, group in enumerate(["A"] * 12 + ["Other"] * 3 + ["B"] * 12):
        person = Agent(
            name=f"respondent-{index}",
            traits={"respondent_id": f"R{index}", "group": group},
        )
        person.add_direct_question_answering_method(demo_answer)
        people.append(person)
    return people


def demo_answer(self, question, scenario):
    if question.question_name == "respondent_type":
        return self.traits["group"]
    # This method is never used to decide admission: QuestionCompute does that.
    return "Shorter waiting times."


def run_demo():
    from edsl.runner import Runner

    survey, _ = build_survey()
    # The test model satisfies Jobs' model dimension; all demo answers are local.
    results = (
        Runner()
        .submit(survey.by(demo_agents()).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    admitted = {group: 0 for group in ("A", "B")}
    screened_out = 0
    for row in results:
        if row.answer.get("quota_gate") == "admitted":
            admitted[row.answer["respondent_type"]] += 1
            assert row.answer["experience"] == "Shorter waiting times."
        else:
            screened_out += 1
            assert row.answer.get("experience") is None
    return {
        "admitted": admitted,
        "screened_out": screened_out,
        "respondents": len(results),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
