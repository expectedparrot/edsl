"""Adaptive price questions using ordinary fixed Survey slots and skip rules."""

import json
from edsl import (
    Agent,
    AgentList,
    Model,
    QuestionCompute,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.machine_primitives.price_elicitation import build_machine


def build_survey(*, state_id=None, lower=0, upper=100, max_questions=7, tolerance=0):
    states = SharedStateMap(
        SharedState(pricing=build_machine(lower, upper, max_questions, tolerance)),
        state_id=state_id,
    )
    pricing = states.by([current.agent.study_id, current.agent.respondent_id]).pricing
    steps, choices = [], []
    for i in range(max_questions):
        quote = QuestionCompute(
            question_name=f"price_{i}",
            question_text="{{ shared_state.pricing.price if not shared_state.pricing.done and shared_state.pricing.next_step == "
            + str(i)
            + " else 'skip' }}",
        )
        answer = QuestionMultipleChoice(
            question_name=f"buy_{i}",
            question_text="Would you buy this product for {{ price_"
            + str(i)
            + ".answer }} price units?",
            question_options=["Yes", "No"],
        )
        steps.extend(
            [
                pricing.read(),
                quote,
                answer,
                pricing.observe(step=i, answer=answer.answer),
            ]
        )
        choices.append(answer)
    summary = QuestionCompute(
        question_name="price_interval",
        question_text="{{ shared_state.pricing.lower }}..{{ shared_state.pricing.upper }}",
    )
    survey = Survey([*steps, pricing.read(), summary])
    for i, question in enumerate(choices):
        survey.add_skip_rule(question, "{{ price_" + str(i) + ".answer }} == 'skip'")
    # Independent respondent scopes can proceed concurrently; no shared ranking.
    return survey, states, "concurrent"


def demo_answer(self, question, scenario):
    return (
        "Yes"
        if self.traits["value"] >= scenario["shared_state"]["pricing"]["price"]
        else "No"
    )


def demo_agents(values=(0, 37, 65, 100)):
    agents = AgentList()
    for i, value in enumerate(values):
        agent = Agent(
            traits={"respondent_id": f"R{i}", "study_id": "study", "value": value}
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
    report = []
    for row in results:
        value = row.agent.traits["value"]
        assert row.answer["price_interval"] == f"{value}..{value}"
        answers = [row.answer.get(f"buy_{i}") for i in range(7)]
        report.append(
            {
                "value": value,
                "interval": row.answer["price_interval"],
                "questions": sum(a is not None for a in answers),
            }
        )
    return {"respondents": report}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
