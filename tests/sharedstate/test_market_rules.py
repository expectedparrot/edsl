"""Authoring errors fail before execution; typed rules preserve v1 behavior."""

from copy import deepcopy
import json

import pytest
from pydantic import ValidationError

from edsl.sharedstate import (
    Account,
    CallMarketRules,
    CashInterest,
    DecisionSchema,
    DiscreteDistribution,
    DividendSampling,
    Endowment,
    PricingRule,
    Redemption,
    ShareDividend,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    call_market,
)
from edsl.sharedstate.dsl_runtime import default_runtime
from edsl.sharedstate.market_records import RoundOutcome, TradeFill
from edsl.sharedstate.market_rules import MarketConstants


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"periods": 0}, "periods"),
        ({"periods": True}, "periods"),
        ({"endowment": {"cash_cents": -1}}, "endowment.cash_cents"),
        ({"endowment": {"shares": 2.5}}, "endowment.shares"),
        ({"pricing": "midpont"}, "pricing"),
        ({"initial_reference_price": float("nan")}, "initial_reference_price"),
        ({"redemption": {"value_cents": "1400"}}, "redemption.value_cents"),
        (
            {
                "income": [
                    {"kind": "cash_interest", "rate": False},
                    {"kind": "share_dividend"},
                ]
            },
            "income.0.cash_interest.rate",
        ),
        ({"income": [{"kind": "cash_interest"}]}, "income"),
        ({"forecast_keys": ["side"]}, "forecast_keys"),
        ({"forecast_keys": ["_hidden"]}, "forecast_keys"),
        ({"forecast_keys": ["model_dump"]}, "forecast_keys"),
        ({"forecast_keys": ["x", "x"]}, "forecast_keys"),
        ({"borrowing": True}, "borrowing"),
        ({"prcing": "marginal_bid"}, "prcing"),
    ],
)
def test_configuration_errors_have_paths(changes, field):
    with pytest.raises(ValidationError) as error:
        CallMarketRules(**changes)
    assert field in {".".join(map(str, e["loc"])) for e in error.value.errors()}


def test_nested_probability_error_and_immutable_validated_changes():
    with pytest.raises(ValidationError) as error:
        CallMarketRules(
            income=[
                {"kind": "cash_interest"},
                {"kind": "share_dividend", "distribution": {"probabilities": [1]}},
            ]
        )
    assert error.value.errors()[0]["loc"] == (
        "income",
        1,
        "share_dividend",
        "distribution",
        "probabilities",
    )
    rules = CallMarketRules()
    with pytest.raises(ValidationError):
        rules.endowment.shares = 8
    with pytest.raises(ValidationError):
        rules.with_changes(periods=-1)
    assert rules.with_changes(periods=5).periods == 5
    assert rules.periods == 30
    assert CallMarketRules.from_dict(json.loads(rules.model_dump_json())) == rules


@pytest.mark.parametrize(
    "rule",
    [
        {"kind": "share_dividend", "values_cents": [1]},
        {"kind": "cash_interest", "raet": 0.1},
        {"kind": "bogus"},
        42,
    ],
)
def test_malformed_legacy_income_is_validation_error_not_key_error(rule):
    with pytest.raises(ValidationError):
        call_market(
            ["a"], income_schedule=[rule, {"kind": "cash_interest", "rate": 0.05}]
        )


def test_wire_unknown_fields_and_missing_rate_fail_before_database(tmp_path):
    for mutate in (
        lambda c: c.update(pricing_rul="marginal_midpoint"),
        lambda c: c["income_schedule"][0].pop("rate"),
        lambda c: c.update(borrowing=0),
    ):
        machine = call_market(["a"])
        mutate(machine.constants)
        with pytest.raises(ValidationError):
            SQLiteStateBackend(
                SharedStateMap(SharedState(market=machine)), tmp_path / "absent.sqlite"
            )
        assert not (tmp_path / "absent.sqlite").exists()
    with pytest.raises(ValueError, match="cannot be combined"):
        call_market(["a"], rules=CallMarketRules(), periods=5)
    with pytest.raises(ValueError, match="unknown"):
        call_market(["a"], initial_cash_cent=100)
    with pytest.raises(ValidationError):
        call_market(["a"], seed=True)


def test_weighted_distribution_and_income_order_change_benchmark():
    dividend = ShareDividend(
        distribution=DiscreteDistribution(
            values_cents=(0, 100), probabilities=(0.25, 0.75)
        )
    )
    assert dividend.sampling == DividendSampling.WEIGHTED
    with pytest.raises(ValidationError, match="equal probabilities"):
        dividend.with_changes(sampling=DividendSampling.CHOICE)
    rules = CallMarketRules(
        periods=1,
        redemption=Redemption(value_cents=1000),
        income=(CashInterest(rate=0.1), dividend),
    )
    assert rules.fundamental_value() == pytest.approx(10.75 / 1.1)
    assert rules.with_changes(
        income=tuple(reversed(rules.income))
    ).fundamental_value() == pytest.approx((10 + 0.75 * 1.1) / 1.1)
    assert (
        rules.with_changes(income=(CashInterest(rate=0), dividend)).fundamental_value()
        == 10.75
    )
    assert rules.fundamental_value(2) == 10
    assert CallMarketRules().fundamental_value() == pytest.approx(14)
    wire = rules.to_constants(2, "seed")
    MarketConstants.from_dict(wire)
    assert "probability 0.25" in rules.instructions(2)


def test_typed_rules_match_legacy_machine():
    rules = CallMarketRules(
        periods=2,
        endowment=Endowment(cash_cents=500, shares=2),
        pricing=PricingRule.MARGINAL_ASK,
    )
    typed = call_market(["a", "b"], rules=rules, seed=4)
    legacy = call_market(
        ["a", "b"],
        periods=2,
        initial_cash_cents=500,
        initial_shares=2,
        pricing_rule="marginal_ask",
        seed=4,
    )
    assert typed.to_dict() == legacy.to_dict()


def test_decision_contract_and_rejected_order_audit_are_distinct():
    schema = DecisionSchema(forecast_keys=("estimate",))
    answer = dict(estimate=14, side="buy", price=10, quantity=2, rationale="test")
    assert schema.question(
        question_name="q", question_text="Trade"
    ).answer_keys == list(answer)
    assert schema.validate_decision(answer).quantity == 2
    for changes in (
        {"side": "byu"},
        {"price": float("inf")},
        {"quantity": True},
        {"estimate": -1},
        {"quantity": 0},
    ):
        with pytest.raises(ValidationError):
            schema.validate_decision({**answer, **changes})
    market = call_market(["a"], forecast_keys=["estimate"])
    runtime = default_runtime()
    initial = runtime.initial_state(market)
    rejected = {**answer, "side": "byu"}
    state = runtime.execute(
        market, initial, "submit", {"trader": "a", "period": 1, "decision": rejected}
    ).state
    assert state["orders"]["a"]["decision"] == rejected
    assert state["orders"]["a"]["rejection"] == "invalid side"
    assert state["orders"]["a"]["accepted_quantity"] == 0
    assert state["accounts"] == initial["accounts"]
    invalid_forecast = {**answer, "estimate": -1}
    before = deepcopy(initial)
    with pytest.raises(ValidationError):
        runtime.execute(
            market,
            initial,
            "submit",
            {"trader": "a", "period": 1, "decision": invalid_forecast},
        )
    assert initial == before
    settled = runtime.execute(market, state, "settle", {"period": 1}).state
    account = Account.from_dict(settled["accounts"]["a"])
    assert account.to_dict() == settled["accounts"]["a"]
    with pytest.raises(ValidationError, match="fill exceeds"):
        TradeFill.from_dict({**account.history[0].to_dict(), "fill": 1})
    with pytest.raises(ValidationError, match="price is present"):
        RoundOutcome.from_dict({**settled["tape"][0], "price": 14})
