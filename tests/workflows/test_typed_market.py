"""Experiment settings drive prompts, question schemas, and the actual market."""

import pytest

from edsl.sharedstate import (
    CashInterest,
    Endowment,
    Redemption,
    ShareDividend,
    DiscreteDistribution,
    SQLiteStateBackend,
)
from examples.asset_market import full_market_experiment as historical
from examples.asset_market import typed_market_experiment as typed


def test_default_prompts_and_agents_are_unchanged():
    for period in range(1, 31):
        assert typed.question_text(period) == historical.question_text(period, 30)
    assert [a.to_dict() for a in typed.build_agents()] == [
        a.to_dict() for a in historical.build_agents()
    ]
    names = [f"trader-{i:02d}" for i in range(12)]
    assert (
        typed.build_market(names).to_dict() == historical.build_market(names).to_dict()
    )


def test_changed_economics_reach_prompts_personas_and_settlement(tmp_path):
    rules = typed.RULES.with_changes(
        periods=2,
        endowment=Endowment(cash_cents=20000, shares=3),
        income=(
            CashInterest(rate=0.1),
            ShareDividend(
                distribution=DiscreteDistribution(
                    values_cents=(50,), probabilities=(1,)
                )
            ),
        ),
        redemption=Redemption(value_cents=900),
        maximum_buy_quantity=2,
    )
    treatment = typed.TREATMENT.with_changes(composition=("RA", "MC"))
    experiment = typed.build(rules=rules, treatment=treatment)
    text = typed.question_text(1, rules, treatment)
    for expected in (
        "Period 1 of 2",
        "2 traders",
        "$200 cash and 3 shares",
        "10% interest",
        "$0.50 (probability 1)",
        "redeemed for $9",
        "capped at 2 shares",
    ):
        assert expected in text
    rational = next(
        a for a in experiment.agents if "rational arbitrageur" in a.instruction
    )
    assert "10% cash return" in rational.instruction
    assert "5% cash return" not in rational.instruction
    machine = next(iter(experiment.states[0].definition.machines.values()))
    assert machine.constants["periods"] == 2
    assert machine.constants["redemption_cents"] == 900
    assert len(experiment.workflow.steps) == 4
    assert rules.fundamental_value() != pytest.approx(14)
    responses = [
        {
            "step": f"orders-{period}",
            "participant": f"trader-{seat:02d}",
            "answers": {
                "decision": {
                    "forecast_0": 9,
                    "forecast_2": 9,
                    "forecast_5": 9,
                    "forecast_10": 9,
                    "side": "hold",
                    "price": 0,
                    "quantity": 0,
                    "rationale": "test",
                }
            },
        }
        for period in (1, 2)
        for seat in (0, 1)
    ]
    result = experiment.run(tmp_path / "variant", responses=responses)
    assert result["status"] == "completed"
    state = (
        SQLiteStateBackend(experiment.states[0], tmp_path / "variant/state-0.sqlite")
        .snapshot("session")
        .state["market"]
    )
    assert all(
        a["cash_cents"] == 27215 and a["shares"] == 0
        for a in state["accounts"].values()
    )
    assert [r["dividend"] for r in state["tape"]] == [0.5, 0.5]


def test_forecast_horizons_are_validated_and_shared_with_question_and_market():
    treatment = typed.TREATMENT.with_changes(forecast_horizons=(0, 1))
    with pytest.raises(ValueError, match="must match"):
        typed.build(treatment=treatment)
    rules = typed.RULES.with_changes(
        forecast_keys=treatment.decision_schema.forecast_keys
    )
    text = typed.question_text(1, rules, treatment)
    assert "Forecast transaction prices now and 1 period ahead" in text
    assert "Your forecasts (now, +1)" in text
    assert "forecast_10" not in text
    experiment = typed.build(rules=rules, treatment=treatment)
    assert experiment.workflow.steps[0].survey.questions[0].answer_keys[:2] == [
        "forecast_0",
        "forecast_1",
    ]
    with pytest.raises(ValueError):
        treatment.with_changes(forecast_horizons=(0, 2, 1))
