"""Behavioral contracts for the standard, serialized call-market capability."""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from edsl.sharedstate import (
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    call_market,
)
from edsl.sharedstate.dsl_runtime import default_runtime


def decision(side="hold", price=0, quantity=0):
    return {
        "forecast_0": 14,
        "forecast_2": 14,
        "forecast_5": 14,
        "forecast_10": 14,
        "side": side,
        "price": price,
        "quantity": quantity,
        "rationale": "test",
    }


def run_round(machine, decisions, state=None):
    runtime = default_runtime()
    machine = Machine.from_dict(json.loads(machine.to_json()))
    state = state or runtime.initial_state(machine)
    period = state["period"]
    for name, answer in decisions:
        state = runtime.execute(
            machine,
            state,
            "submit",
            {"trader": name, "period": period, "decision": answer},
        ).state
    return runtime.execute(machine, state, "settle", {"period": period}).state


@pytest.mark.parametrize(
    "pricing,expected",
    [
        ("marginal_midpoint", 17.53),
        ("marginal_bid", 21),
        ("marginal_ask", 14.05),
    ],
)
def test_serialized_pricing_rules_change_actual_clearing(pricing, expected):
    machine = call_market(["buyer", "seller"], pricing_rule=pricing, seed=140926)
    state = run_round(
        machine,
        [("buyer", decision("buy", 21, 2)), ("seller", decision("sell", 14.05, 2))],
    )
    assert state["tape"][0]["price"] == expected
    assert state["tape"][0]["volume"] == 2
    assert sum(a["shares"] for a in state["accounts"].values()) == 8
    assert state["accounts"]["buyer"]["shares"] == 6
    assert state["accounts"]["seller"]["shares"] == 2


def test_sealed_orders_conserve_balances_and_capacity_is_enforced():
    machine = call_market(
        ["buyer", "seller"], initial_cash_cents=1000, initial_shares=1
    )
    runtime = default_runtime()
    initial = runtime.initial_state(machine)
    state = runtime.execute(
        machine,
        initial,
        "submit",
        {"trader": "buyer", "period": 1, "decision": decision("buy", 6, 50)},
    ).state
    assert state["accounts"] == initial["accounts"]
    assert state["tape"] == []
    assert state["orders"]["buyer"]["accepted_quantity"] == 1
    with pytest.raises(ValueError, match="every trader"):
        runtime.execute(machine, state, "settle", {"period": 1})
    state = runtime.execute(
        machine,
        state,
        "submit",
        {"trader": "seller", "period": 1, "decision": decision("sell", 4, 50)},
    ).state
    assert state["orders"]["seller"]["accepted_quantity"] == 1
    with pytest.raises(ValueError, match="already submitted"):
        runtime.execute(
            machine,
            state,
            "submit",
            {"trader": "seller", "period": 1, "decision": decision()},
        )
    state = runtime.execute(machine, state, "settle", {"period": 1}).state
    assert state["tape"][0]["price"] == 5
    assert state["tape"][0]["total_cash"] == 21 + 2 * state["tape"][0]["dividend"]
    with pytest.raises(ValueError, match="exactly once"):
        runtime.execute(machine, state, "settle", {"period": 1})


def test_income_order_and_final_redemption_are_explicit():
    interest = {"kind": "cash_interest", "rate": 0.1}
    dividend = {
        "kind": "share_dividend",
        "values_cents": [100],
        "probabilities": [1],
        "sampling": "python_random_choice_v1",
    }
    for schedule, expected in [
        ([interest, dividend], 1700),
        ([dividend, interest], 1710),
    ]:
        machine = call_market(
            ["A"],
            periods=1,
            initial_cash_cents=1000,
            initial_shares=1,
            redemption_cents=500,
            income_schedule=schedule,
        )
        state = run_round(machine, [("A", decision())])
        assert state["tape"][0]["price"] is None
        assert state["accounts"]["A"]["cash_cents"] == expected
        assert state["accounts"]["A"]["shares"] == 0
        assert state["accounts"]["A"]["redeemed_shares"] == 1
        assert state["finished"]


def test_ties_are_independent_of_answer_arrival_order():
    machine = call_market(["a", "b", "seller"], seed=123)
    answers = [
        ("a", decision("buy", 20, 1)),
        ("b", decision("buy", 20, 1)),
        ("seller", decision("sell", 16, 1)),
    ]
    assert run_round(machine, answers) == run_round(machine, list(reversed(answers)))


@pytest.mark.parametrize(
    "field,value",
    [("pricing_rule", "mystery"), ("borrowing", True), ("rounding", "bankers")],
)
def test_loaded_rule_errors_fail_before_creating_database(tmp_path, field, value):
    machine = call_market(["A"])
    machine.constants[field] = value
    maps = SharedStateMap(SharedState(market=machine))
    with pytest.raises(ValueError):
        SQLiteStateBackend(maps, tmp_path / "must-not-exist.sqlite")
    assert not (tmp_path / "must-not-exist.sqlite").exists()


def test_bad_forecast_and_unavailable_version_do_not_mutate_state(tmp_path):
    machine = call_market(["A"])
    runtime = default_runtime()
    state = runtime.initial_state(machine)
    before = deepcopy(state)
    answer = decision()
    answer["forecast_0"] = -1
    with pytest.raises(ValueError):
        runtime.execute(
            machine, state, "submit", {"trader": "A", "period": 1, "decision": answer}
        )
    assert state == before
    machine = replace(
        machine, algorithms=("call_market_submit@999", "call_market_settle@1")
    )
    with pytest.raises(ValueError, match="unregistered"):
        runtime.validate_capabilities(machine)
