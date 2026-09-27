"""A sealed-bid auction collected in one pass; run with python -m examples.second_price_auction."""

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
from examples.machine_primitives.second_price_auction import build_machine


def build_survey(*, state_id=None, **machine_options):
    spec = build_machine(**machine_options)
    states = SharedStateMap(SharedState(auction=spec), state_id=state_id)
    auction = states.by(current.agent.market_id).auction
    gate = QuestionCompute(
        question_name="auction_entry",
        question_text="{{ 'closed' if shared_state.auction.settled or shared_state.auction.submitted else 'open' }}",
    )
    questions = [
        QuestionMultipleChoice(
            question_name=f"bid_{i}",
            question_text=f"What is your bid for marginal unit {i+1}? Use whole money units, weakly decreasing bids, and a total within your dedicated budget. Zero means no bid for this unit.",
            question_options=list(range(spec.constants["max_cash"] + 1)),
        )
        for i in range(spec.constants["max_demand"])
    ]
    receipt = QuestionCompute(
        question_name="auction_receipt",
        question_text="{{ 'settled' if shared_state.auction.settled else ('pending' if shared_state.auction.submitted else 'not accepted') }}",
    )
    survey = Survey(
        [
            auction.read(),
            gate,
            *questions,
            auction.submit(
                bidder_id=current.agent.bidder_id, bids=[q.answer for q in questions]
            ),
            auction.settle_if_ready(),
            auction.read(),
            receipt,
        ]
    )
    survey.add_stop_rule(gate, "{{ auction_entry.answer }} != 'open'")
    return survey, states, InterviewSchedule.grouped_round_robin("market_id", "turn")


def demo_answer(self, question, scenario):
    return self.traits["bids"][int(question.question_name.split("_")[-1])]


def demo_agents():
    agents = AgentList()
    for turn, (bidder, bids) in enumerate(zip(["A", "B", "C"], [[90], [70], [50]])):
        agent = Agent(
            traits={
                "bidder_id": bidder,
                "bids": bids,
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
    book = writes[-1]["state"]["auction"]["auction"]
    assert book["settled"] and book["price"] == 70
    assert sum(book["cash"].values()) + book["seller_cash"] == 600
    return {
        k: book[k]
        for k in [
            "price",
            "allocations",
            "payments",
            "cash",
            "seller_cash",
            "remaining",
        ]
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2))
