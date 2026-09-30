"""Posted-price inventory sales: python -m examples.posted_price_market."""

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
from examples.machine_primitives.posted_price_market import build_machine


def build_survey(*, state_id=None, **machine_options):
    states = SharedStateMap(
        SharedState(market=build_machine(**machine_options)), state_id=state_id
    )
    market = states.by(current.agent.market_id).market
    gate = QuestionCompute(
        question_name="market_entry",
        question_text="{{ 'open' if shared_state.market.status == 'quoted' and shared_state.market.quote_current and shared_state.market.accepting else 'closed' }}",
    )
    quantity = QuestionMultipleChoice(
        question_name="quantity",
        question_text="How many units would you buy at {{ shared_state.market.quoted_price }} each? Zero passes.",
        question_options="{{ shared_state.market.options }}",
    )
    receipt = QuestionCompute(
        question_name="order_receipt", question_text="{{ shared_state.market.status }}"
    )
    survey = Survey(
        [
            market.quote(
                buyer_id=current.agent.buyer_id, order_id=current.agent.order_id
            ),
            market.read(),
            gate,
            quantity,
            market.buy(
                buyer_id=current.agent.buyer_id,
                order_id=current.agent.order_id,
                quantity=quantity.answer,
            ),
            market.read(),
            receipt,
        ]
    )
    survey.add_stop_rule(gate, "{{ market_entry.answer }} != 'open'")
    return survey, states, InterviewSchedule.grouped_round_robin("market_id", "turn")


def demo_answer(self, question, scenario):
    return self.traits["desired_quantity"]


def demo_agents():
    agents = AgentList()
    for turn, (buyer, quantity) in enumerate(zip(["A", "B", "C", "D"], [2, 1, 2, 1])):
        agent = Agent(
            traits={
                "buyer_id": buyer,
                "order_id": buyer + "-1",
                "desired_quantity": quantity,
                "market_id": "market",
                "turn": turn,
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
    writes = [
        e for e in results.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    state = writes[-1]["state"]["market"]
    assert state["stock"] == 0 and state["seller_cash"] == 140
    assert sum(state["cash"].values()) + state["seller_cash"] == 800
    assert sum(r.answer.get("order_receipt") == "filled" for r in results) == 3
    return {k: state[k] for k in ["stock", "inventory", "cash", "seller_cash"]}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
