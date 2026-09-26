"""Adaptive pairwise survey: python -m examples.pairwise_comparisons.

Scripted local respondents, ordinary survey navigation, and no model calls.
"""

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
from examples.machine_primitives.pairwise_comparisons import (
    DEFAULT_ITEMS,
    build_machine,
)


def build_survey(
    *,
    state_id=None,
    items=DEFAULT_ITEMS,
    budget=40,
    explore_every=5,
    learning_rate=0.5,
    seed="pairwise-2026",
):
    states = SharedStateMap(
        SharedState(
            comparisons=build_machine(items, budget, explore_every, learning_rate, seed)
        ),
        state_id=state_id,
    )
    comparisons = states.by(current.agent.study_id).comparisons
    gate = QuestionCompute(
        question_name="pairwise_gate",
        question_text="{{ 'open' if shared_state.comparisons.accepting else 'closed' }}",
    )
    preference = QuestionMultipleChoice(
        question_name="preference",
        question_text="Which of these products would you prefer?",
        question_options="{{ shared_state.comparisons.options }}",
    )
    survey = Survey(
        [
            comparisons.assign(respondent_id=current.agent.respondent_id),
            comparisons.read(),
            gate,
            preference,
            comparisons.compare(
                respondent_id=current.agent.respondent_id, winner=preference.answer
            ),
        ]
    )
    survey.add_stop_rule(gate, "{{ pairwise_gate.answer }} != 'open'")
    schedule = InterviewSchedule.grouped_round_robin(
        "study_id", "turn", stop_when=comparisons.is_complete()
    )
    return survey, states, schedule


def demo_answer(self, question, scenario):
    # This ranking belongs only to the scripted population, never the Machine.
    order = self.traits["preference_order"]
    return min(question.question_options, key=order.index)


def demo_agents(count=60, *, observed_options=None):
    if type(count) is not int or count < 1:
        raise ValueError("population count must be a positive integer")

    def answer(self, question, scenario):
        if observed_options is not None:
            observed_options[self.traits["respondent_id"]] = list(
                question.question_options
            )
        return demo_answer(self, question, scenario)

    agents = AgentList()
    for i in range(count):
        agent = Agent(
            name=f"respondent-{i}",
            traits={
                "respondent_id": f"R{i}",
                "study_id": "study",
                "turn": i,
                "preference_order": list(DEFAULT_ITEMS),
            },
        )
        agent.add_direct_question_answering_method(answer)
        agents.append(agent)
    return agents


def run_demo(count=60, budget=40):
    from edsl.runner import Runner

    survey, _, schedule = build_survey(budget=budget)
    observed = {}
    results = (
        Runner(interview_schedule=schedule)
        .submit(
            survey.by(demo_agents(count, observed_options=observed)).by(Model("test")),
            cache=False,
        )
        .results()
    )
    assert not results.has_unfixed_exceptions
    writes = [
        e for e in results.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    final = writes[-1]["state"]["comparisons"]
    for row in results:
        rid = row.agent.traits["respondent_id"]
        assert row.answer.get("preference") == final["responses"].get(rid)
        if rid in final["responses"]:
            assert (
                row.get_question_options("preference")
                == observed[rid]
                == final["assignments"][rid]["options"]
            )
    assert set(observed) == set(final["responses"])
    ranking = sorted(DEFAULT_ITEMS, key=lambda x: (-final["ratings"][x], x))
    return {
        "population_size": count,
        "comparisons": final["comparisons"],
        "stop_reason": (
            "budget_reached"
            if final["comparisons"] == budget
            else "population_exhausted"
        ),
        "ranking": ranking,
        "ratings": final["ratings"],
        "pair_counts": final["pair_counts"],
        "exploration_comparisons": sum(
            a["mode"] == "explore"
            for r, a in final["assignments"].items()
            if r in final["responses"]
        ),
        "matches_simulated_order": ranking == list(DEFAULT_ITEMS),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
