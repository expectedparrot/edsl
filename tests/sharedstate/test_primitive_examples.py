"""Differential and invariant checks for coding-agent reference examples."""

import random
from copy import deepcopy

import pytest

from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime, default_runtime
from examples.machine_primitives import (
    serial_dictatorship,
    deferred_acceptance,
    double_auction,
    binary_market,
    batch_auction,
)
from examples.machine_primitives.__main__ import EXAMPLES, run_example


def execute(machine, commands):
    machine = Machine.from_json(machine.to_json())
    machine.validate()
    runtime = Runtime()
    state = runtime.initial_state(machine)
    for name, inputs in commands:
        state = (
            runtime.close(machine, state)
            if name == "$close"
            else runtime.execute(machine, state, name, inputs).state
        )
    return state, runtime.render_view(machine, state, closed=True)


@pytest.mark.parametrize("name", EXAMPLES)
def test_corpus_runs_after_json_transport_with_empty_registry(name):
    result = run_example(name)
    assert result["definition"]["algorithms"] == []


@pytest.mark.parametrize("seed", range(20))
def test_serial_dictatorship_matches_registered_reference(seed):
    rng = random.Random(seed)
    items = ["X", "Y", "Z"]
    requests = [
        {
            "claimant": rng.choice(["A", "B", "C", "D"]),
            "priority": rng.choice([None, 0, 1, 2]),
            "ranking": rng.sample(items, rng.randrange(4)),
        }
        for _ in range(rng.randrange(12))
    ]
    capacity = rng.randrange(3)
    _, view = execute(
        serial_dictatorship.build_machine(items, capacity),
        [("collect", r) for r in requests] + [("$close", {})],
    )
    oracle = {}
    default_runtime().algorithms[("serial_dictatorship", 1)](
        oracle, {"requests": requests, "items": items, "capacity": capacity}, {}
    )
    assert view["assignments"] == oracle["assignments"]
    assert all(n >= 0 for n in view["remaining"].values())
    assert sum(view["remaining"].values()) + len(view["assignments"]) == capacity * len(
        items
    )


@pytest.mark.parametrize("seed", range(20))
def test_deferred_acceptance_matches_reference_and_has_no_blocking_pair(seed):
    rng = random.Random(seed)
    schools, students = ["X", "Y", "Z"], ["A", "B", "C", "D"]
    capacities = {s: rng.randrange(3) for s in schools}
    priorities = {s: rng.sample(students, len(students)) for s in schools}
    requests = [
        {
            "student": rng.choice(students),
            "ranking": rng.sample(schools, rng.randrange(4)),
        }
        for _ in range(rng.randrange(12))
    ]
    _, view = execute(
        deferred_acceptance.build_machine(capacities, priorities),
        [("collect", r) for r in requests] + [("$close", {})],
    )
    oracle = {}
    default_runtime().algorithms[("deferred_acceptance", 1)](
        oracle,
        {"requests": requests, "capacities": capacities, "priorities": priorities},
        {},
    )
    assert view == oracle
    assert all(len(view["institution_matches"][s]) <= capacities[s] for s in schools)
    latest = {r["student"]: r["ranking"] for r in requests}
    for student, ranking in latest.items():
        current = view["matches"].get(student)
        preferred = ranking[: ranking.index(current)] if current in ranking else ranking
        for school in preferred:
            held = view["institution_matches"][school]
            assert len(held) == capacities[school]
            assert all(
                priorities[school].index(other) < priorities[school].index(student)
                for other in held
            )


def test_deferred_acceptance_missing_priorities_use_lexical_ties():
    machine = deferred_acceptance.build_machine({"X": 1}, {"X": []})
    _, view = execute(
        machine,
        [("collect", {"student": s, "ranking": ["X"]}) for s in ["B", "A"]]
        + [("$close", {})],
    )
    assert view["matches"] == {"A": "X"}


@pytest.mark.parametrize("seed", range(10))
def test_double_auction_valid_streams_match_reference_and_conserve(seed):
    rng = random.Random(seed)
    accounts = {name: {"cash": 300, "inventory": 3} for name in ["A", "B", "C"]}
    machine = Machine.from_json(double_auction.build_machine(accounts).to_json())
    runtime, legacy = Runtime(), default_runtime()
    state = runtime.initial_state(machine)
    oracle = {"accounts": deepcopy(accounts), "orders": [], "trades": []}
    for turn in range(20):
        trader = rng.choice(list(accounts))
        opened = any(
            o["status"] == "open" and o["trader"] == trader for o in oracle["orders"]
        )
        action = "cancel" if opened else rng.choice(["buy", "sell", "hold"])
        price = rng.randrange(1, 100)
        if (
            action == "buy"
            and oracle["accounts"][trader]["cash"] < price
            or action == "sell"
            and oracle["accounts"][trader]["inventory"] < 1
        ):
            action = "hold"
        inputs = {"trader": trader, "action": action, "price": price, "round": turn + 1}
        state = runtime.execute(machine, state, "submit", inputs).state
        legacy.algorithms[("double_auction_submit", 1)](oracle, inputs, {})
        assert state["market"] == oracle
        assert sum(a["cash"] for a in oracle["accounts"].values()) == 900
        assert sum(a["inventory"] for a in oracle["accounts"].values()) == 9
    assert runtime.close(machine, state)["market"]["trades"] == oracle["trades"]


@pytest.mark.parametrize("seed", range(10))
def test_binary_market_matches_legacy_on_supported_paths(seed):
    rng = random.Random(seed)
    machine = Machine.from_json(binary_market.build_machine().to_json())
    runtime, legacy = Runtime(), default_runtime()
    state = runtime.initial_state(machine)
    oracle = {"q_yes": 0, "q_no": 0, "portfolios": {}, "trades": [], "outcome": None}
    for _ in range(12):
        inputs = {
            "trader": rng.choice(["A", "B"]),
            "action": rng.choice(["buy_yes", "buy_no", "hold"]),
            "quantity": rng.randrange(20),
        }
        state = runtime.execute(machine, state, "trade", inputs).state
        legacy.algorithms[("lmsr_trade", 1)](
            oracle, inputs, {"liquidity": 50, "initial_cash": 100}
        )
        for name, portfolio in oracle["portfolios"].items():
            assert state["market"]["portfolios"][name] == pytest.approx(portfolio)
    outcome = bool(seed % 2)
    state = runtime.execute(machine, state, "settle", {"outcome": outcome}).state
    legacy.algorithms[("lmsr_settle", 1)](oracle, {"outcome": outcome}, {})
    for name, portfolio in oracle["portfolios"].items():
        assert state["market"]["portfolios"][name] == pytest.approx(portfolio)
    assert runtime.render_view(machine, state)["prices"]["yes"] + runtime.render_view(
        machine, state
    )["prices"]["no"] == pytest.approx(1)
    assert (
        runtime.execute(
            machine, state, "trade", {"trader": "A", "action": "buy_yes", "quantity": 1}
        ).state
        == state
    )


@pytest.mark.parametrize(
    "orders, volume, price",
    [
        ([], 0, None),
        ([("B", "buy", 10)], 0, None),
        ([("B", "buy", 10), ("S", "sell", 20)], 0, None),
        ([("B", "buy", 20), ("S", "sell", 20)], 1, 20),
        (
            [
                ("B1", "buy", 50),
                ("B2", "buy", 40),
                ("S1", "sell", 10),
                ("S2", "sell", 30),
            ],
            2,
            35,
        ),
    ],
)
def test_batch_auction_boundaries(orders, volume, price):
    _, view = execute(
        batch_auction.build_machine(),
        [
            ("submit", {"trader": name, "side": side, "price": p})
            for name, side, p in orders
        ]
        + [("$close", {})],
    )
    clearing = view["clearing"]
    assert clearing["volume"] == volume
    assert clearing["price"] == price
    assert len(clearing["buyers"]) == len(clearing["sellers"]) == volume
