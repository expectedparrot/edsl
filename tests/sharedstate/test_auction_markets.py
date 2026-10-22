"""Settled auction/market probes: references, rejection, durable races, and surveys."""

import importlib
import json
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from edsl import AgentList, Model, Results, Survey
from edsl.runner import Runner
from edsl.sharedstate import (
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    resolve_write,
)
from edsl.sharedstate.dsl_runtime import Runtime
from edsl.sharedstate.steps import StepContext

NAMES = ("second_price_auction", "uniform_price_auction", "posted_price_market")


def restored_machine(name, **kwargs):
    module = importlib.import_module("examples.machine_primitives." + name)
    m = Machine.from_json(module.build_machine(**kwargs).to_json())
    r = Runtime()
    return m, r, r.initial_state(m)


@pytest.mark.parametrize("name", NAMES[:2])
@pytest.mark.parametrize("seed", range(12))
def test_auction_independent_price_reference_and_conservation(name, seed):
    rng = random.Random(seed)
    units, demand = (1, 1) if name == NAMES[0] else (3, 2)
    m, r, s = restored_machine(name)
    # Unique prices make the independent allocation oracle independent of tie hashing.
    prices = iter(rng.sample(range(110), 3 * demand))
    bids = {
        k: sorted(
            [next(prices) for _ in range(rng.randrange(demand + 1))], reverse=True
        )
        for k in "ABC"
    }
    # Dedicated budgets constrain total liability, including all marginal units.
    for k in bids:
        if sum(bids[k]) > 200:
            bids[k] = [bids[k][0]]
    for k in rng.sample(list(bids), 3):
        s = r.execute(m, s, "submit", {"bidder_id": k, "bids": bids[k]}).state
    s = r.execute(m, s, "settle_if_ready", {}).state
    book = s["auction"]
    ranked = sorted(
        [(p, k) for k, ps in bids.items() for p in ps if p >= 40], reverse=True
    )
    winners = ranked[:units]
    price = (ranked[units][0] if len(ranked) > units else 40) if winners else None
    assert book["price"] == price
    assert book["allocations"] == {
        k: sum(owner == k for _, owner in winners) for k in bids
    }
    assert book["payments"] == {k: book["allocations"][k] * (price or 0) for k in bids}
    assert sum(book["cash"].values()) + book["seller_cash"] == 600
    assert sum(book["allocations"].values()) + book["remaining"] == units
    assert min(book["cash"].values()) >= 0
    assert r.execute(m, s, "settle_if_ready", {}).state == s
    assert r.close(m, s) == s
    for k in bids:
        assert r.execute(m, s, "submit", {"bidder_id": k, "bids": bids[k]}).state == s


@pytest.mark.parametrize("name", NAMES[:2])
def test_sealed_views_rejections_partial_close_and_abstention(name):
    m, r, s = restored_machine(name)
    inputs = {"bidder_id": "A", "bids": [90]}
    s = r.execute(m, s, "submit", inputs).state
    assert r.execute(m, s, "settle_if_ready", {}).event["status"] == "noop"
    a = r.render_view(m, s, current={"bidder_id": "A"})
    b = r.render_view(m, s, current={"bidder_id": "B"})
    assert a["your_bids"] == [90] and b["your_bids"] == []
    assert a["allocations"] == b["allocations"] == {} and a["price"] is None
    for payload, reason in [
        ({"bidder_id": "X", "bids": [1]}, "unknown_bidder"),
        ({"bidder_id": "A", "bids": [80]}, "bid_changed"),
        ({"bidder_id": "B", "bids": [1, 1, 1]}, "too_many_units"),
    ]:
        result = r.execute(m, s, "submit", payload)
        assert result.state == s and result.event["reason_code"] == reason
    closed = r.close(m, s)
    assert closed["auction"]["price"] == 40 and closed["auction"]["payments"]["A"] == 40
    assert (
        r.execute(m, closed, "submit", {"bidder_id": "B", "bids": []}).event[
            "reason_code"
        ]
        == "auction_settled"
    )
    empty = r.close(m, r.initial_state(m))["auction"]
    assert empty["price"] is None and empty["seller_cash"] == 0
    assert empty["remaining"] == m.constants["units"]


def test_uniform_budget_decreasing_bids_and_own_losing_bid():
    m, r, s = restored_machine(
        NAMES[1], units=2, max_demand=2, balances={"A": 200, "B": 200}
    )
    for bids, reason in [
        ([60, 90], "bids_not_decreasing"),
        ([150, 100], "insufficient_budget"),
    ]:
        result = r.execute(m, s, "submit", {"bidder_id": "A", "bids": bids})
        assert result.state == s and result.event["reason_code"] == reason
    for k, bids in [("A", [100, 80]), ("B", [90, 50])]:
        s = r.execute(m, s, "submit", {"bidder_id": k, "bids": bids}).state
    s = r.close(m, s)
    assert s["auction"]["allocations"] == {"A": 1, "B": 1}
    assert s["auction"]["price"] == 80  # A's own rejected bid sets the uniform price.


@pytest.mark.parametrize("name", NAMES[:2])
def test_ties_are_stable_across_arrival_order(name):
    outcomes = []
    for order in ["ABC", "CBA", "BAC"]:
        m, r, s = restored_machine(name)
        for k in order:
            s = r.execute(
                m,
                s,
                "submit",
                {"bidder_id": k, "bids": [70] * m.constants["max_demand"]},
                current={"market_id": "same"},
            ).state
        outcomes.append(
            r.execute(m, s, "settle_if_ready", {}, current={"market_id": "same"}).state
        )
    assert outcomes[0] == outcomes[1] == outcomes[2]


def test_posted_stale_quote_refresh_pass_and_idempotent_payment():
    m, r, s = restored_machine(NAMES[2])
    for k in "AB":
        s = r.execute(m, s, "quote", {"buyer_id": k, "order_id": k + "1"}).state
    s = r.execute(m, s, "buy", {"buyer_id": "A", "order_id": "A1", "quantity": 2}).state
    stale = r.execute(m, s, "buy", {"buyer_id": "B", "order_id": "B1", "quantity": 1})
    assert stale.state == s and stale.event["reason_code"] == "stale_quote"
    assert r.execute(m, s, "quote", {"buyer_id": "B", "order_id": "B1"}).state == s
    assert (
        r.execute(m, s, "buy", {"buyer_id": "A", "order_id": "A1", "quantity": 2}).state
        == s
    )
    assert (
        r.execute(
            m, s, "buy", {"buyer_id": "A", "order_id": "A1", "quantity": 1}
        ).event["reason_code"]
        == "order_changed"
    )
    hidden = r.render_view(m, s, current={"buyer_id": "B", "order_id": "A1"})
    assert hidden["quoted_price"] is None and hidden["options"] == []
    s = r.execute(m, s, "quote", {"buyer_id": "B", "order_id": "B2"}).state
    assert s["orders"]["B2"]["price"] == 30
    s = r.execute(m, s, "buy", {"buyer_id": "B", "order_id": "B2", "quantity": 1}).state
    s = r.close(m, s)
    s = r.execute(m, s, "buy", {"buyer_id": "B", "order_id": "B1", "quantity": 0}).state
    assert s["orders"]["B1"]["status"] == "passed"
    assert sum(s["cash"].values()) + s["seller_cash"] == 800
    assert sum(s["inventory"].values()) + s["stock"] == 5
    assert (
        r.execute(m, s, "quote", {"buyer_id": "C", "order_id": "C1"}).event[
            "reason_code"
        ]
        == "market_closed"
    )


@pytest.mark.parametrize(
    "quantity,reason", [(3, "insufficient_stock"), (2, "insufficient_funds")]
)
def test_posted_rejections_are_atomic(quantity, reason):
    m, r, s = restored_machine(NAMES[2], stock=2, balances={"A": 20, "B": 20})
    s = r.execute(m, s, "quote", {"buyer_id": "A", "order_id": "a"}).state
    result = r.execute(
        m, s, "buy", {"buyer_id": "A", "order_id": "a", "quantity": quantity}
    )
    assert result.state == s and result.event["reason_code"] == reason
    assert (
        r.execute(m, s, "buy", {"buyer_id": "B", "order_id": "a", "quantity": 1}).event[
            "reason_code"
        ]
        == "order_not_owned"
    )
    assert (
        r.execute(m, s, "quote", {"buyer_id": "B", "order_id": "a"}).event[
            "reason_code"
        ]
        == "order_not_owned"
    )


@pytest.mark.parametrize("name", NAMES)
def test_restart_replay_scope_and_fresh_interpreter(name, tmp_path):
    module = importlib.import_module("examples.machine_primitives." + name)
    m, r, expected = restored_machine(name)
    spaces = SharedStateMap(SharedState(app=m))
    target = spaces.by("market").app
    operations = []
    for i, (cmd, inputs) in enumerate(module.DEMO):
        backend = SQLiteStateBackend(
            SharedStateMap.from_dict(spaces.to_dict()),
            tmp_path / "market.sqlite",
            runtime=Runtime(),
        )
        op = resolve_write(getattr(target, cmd)(**inputs), StepContext({}, f"op-{i}"))
        result = backend.apply(op)
        expected = r.execute(m, expected, cmd, inputs).state
        assert backend.snapshot("market").state["app"] == expected
        operations.append((op, result.status))
    before = backend.snapshot("market")
    for op, status in operations:
        assert backend.apply(op).status == status
    assert backend.snapshot("market") == before
    assert backend.snapshot("other").state["app"] == r.initial_state(m)
    code = """import json, sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
p=json.load(sys.stdin); m=Machine.from_dict(p['machine']); r=Runtime(); s=r.initial_state(m)
for c,i in p['commands']: s=r.execute(m,s,c,i).state
assert not any(n.startswith('examples.') for n in sys.modules)
print(json.dumps(s))"""
    out = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"machine": m.to_dict(), "commands": module.DEMO}),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(out.stdout) == expected


@pytest.mark.parametrize("name", NAMES)
def test_concurrent_settlement_or_purchase(name, tmp_path):
    m, _, _ = restored_machine(name)
    spaces = SharedStateMap(SharedState(app=m))
    target = spaces.by("market").app
    backend = SQLiteStateBackend(spaces, tmp_path / "races.sqlite", runtime=Runtime())
    if name == NAMES[2]:
        for k in "ABCD":
            backend.apply(
                resolve_write(
                    target.quote(buyer_id=k, order_id=k), StepContext({}, "quote-" + k)
                )
            )
        steps = [target.buy(buyer_id=k, order_id=k, quantity=2) for k in "ABCD"]
    else:
        for k, p in zip("ABC", [90, 70, 50]):
            backend.apply(
                resolve_write(
                    target.submit(bidder_id=k, bids=[p]), StepContext({}, "bid-" + k)
                )
            )
        steps = [target.settle_if_ready() for _ in range(4)]
    ops = [
        resolve_write(step, StepContext({}, f"settle-{i}"))
        for i, step in enumerate(steps)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(pool.map(backend.apply, ops))
    assert sum(d.status == "applied" for d in decisions) == 1
    s = backend.snapshot("market").state["app"]
    if name == NAMES[2]:
        assert sum(d.status == "rejected" for d in decisions) == 3
        assert s["stock"] == 3 and s["seller_cash"] == 40
        assert sum(s["cash"].values()) + s["seller_cash"] == 800
    else:
        assert sum(d.status == "noop" for d in decisions) == 3
        book = s["auction"]
        assert sum(book["cash"].values()) + book["seller_cash"] == 600


@pytest.mark.parametrize("name", NAMES)
def test_survey_transport_schedule_choices_receipts_and_results(name):
    module = importlib.import_module("examples." + name)
    survey, _, schedule = module.build_survey()
    survey = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    results = (
        Runner(interview_schedule=schedule)
        .submit(
            survey.by(AgentList(reversed(module.demo_agents()))).by(Model("test")),
            cache=False,
        )
        .results()
    )
    assert not results.has_unfixed_exceptions
    restored = Results.from_dict(json.loads(json.dumps(results.to_dict())))
    if name == NAMES[2]:
        rows = {r.agent.traits["buyer_id"]: r for r in restored}
        for k, price, options in [
            ("A", 20, list(range(6))),
            ("B", 30, list(range(4))),
            ("C", 35, list(range(3))),
        ]:
            assert rows[k].get_question_options("quantity") == options
            assert rows[k].answer["order_receipt"] == "filled"
            attrs = rows[k].data["question_to_attributes"]["quantity"]
            assert attrs["presentation"]["source"] == "agent_direct"
        assert rows["D"].answer.get("quantity") is None
    else:
        rows = {r.agent.traits["bidder_id"]: r for r in restored}
        assert [rows[k].answer["auction_receipt"] for k in "ABC"] == [
            "pending",
            "pending",
            "settled",
        ]
    assert module.run_demo()


@pytest.mark.parametrize(
    "name,kwargs",
    [
        (NAMES[0], {"reserve": 0}),
        (NAMES[0], {"balances": {}}),
        (NAMES[1], {"max_demand": 4}),
        (NAMES[1], {"units": True}),
        (NAMES[2], {"increment": -1}),
        (NAMES[2], {"stock": 0}),
        (NAMES[2], {"balances": {"A": True}}),
    ],
)
def test_invalid_configuration(name, kwargs):
    with pytest.raises(ValueError):
        restored_machine(name, **kwargs)


def test_posted_model_prompts_contain_the_actual_quote():
    from examples.posted_price_market import build_survey, demo_agents

    survey, _, schedule = build_survey()
    agents = demo_agents()
    for agent in agents:
        agent.remove_direct_question_answering_method()
    prompts = []
    quantities = iter([2, 1, 2])

    def answer(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        return str(next(quantities))

    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(agents).by(Model("test", func=answer)), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    assert len(prompts) == 3
    for prompt, price in zip(prompts, [20, 30, 35]):
        assert f"at {price} each" in prompt
    for row in results:
        if row.answer.get("quantity") is not None:
            assert (
                row.data["question_to_attributes"]["quantity"]["presentation"]["source"]
                == "prompt"
            )
