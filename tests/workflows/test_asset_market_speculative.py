"""Check that the prompt intervention preserves economics and removes fake anchors."""

from jinja2 import StrictUndefined, Template

from edsl.workflows import HumanWorkflow
from examples.asset_market.audit import audit_session
from examples.asset_market.experiment import build_experiment as original
from examples.asset_market.run_speculative import run_session
from examples.asset_market.speculative_prompts import COMPOSITION, build_experiment


def test_prompt_variant_preserves_market_and_workflow_contract():
    old, old_states, old_agents = original(COMPOSITION, periods=2, seed=140926)
    new, new_states, agents = build_experiment(periods=2, seed=140926)
    assert old_states.to_dict() == new_states.to_dict()
    assert old.metadata["persona_assignment"] == new.metadata["persona_assignment"]
    assert [a.traits for a in agents] == [a.traits for a in old_agents]
    assert HumanWorkflow.from_dict(new.to_dict()).to_dict() == new.to_dict()
    for before, after in zip(old.steps, new.steps):
        a, b = before.to_dict(), after.to_dict()
        # Independently authored workflows allocate fresh state-operation UUIDs.
        for definition in (a, b):
            for operation in definition["reads"] + definition["writes"]:
                operation.pop("step_id")
        if before.name.startswith("orders-"):
            a.pop("survey")
            b.pop("survey")
        assert a == b


def test_render_does_not_leak_reference_quote_and_shows_dollars():
    workflow, _, _ = build_experiment(periods=2)
    market = {
        "your_account": {"cash_cents": 12345, "shares": 4, "history": []},
        "last_price": 99999.99,
        "tape": [
            {
                "period": 1,
                "price": None,
                "reference_price": 88888.88,
                "volume": 0,
                "dividend": 0.4,
                "total_cash": 1260,
                "total_shares": 48,
                "total_interest": 60,
            }
        ],
    }
    text = Template(
        workflow.steps[0].survey.questions[0].question_text, undefined=StrictUndefined
    ).render(shared_state={"market": market})
    assert "Cash: 123.45" in text
    assert "99999" not in text and "88888" not in text and "12345" not in text
    assert "fundamental value" not in text
    assert "transaction price None" in text
    assert "redeemed for $14" in text


def test_two_period_workflow_with_real_history(tmp_path):
    config = {
        "output": str(tmp_path / "smoke"),
        "treatment": COMPOSITION,
        "periods": 2,
        "seed": 140926,
        "backend": "scripted",
        "model": None,
        "service": None,
        "base_url": None,
        "temperature": 0.7,
        "resume": False,
    }
    result = run_session(config)
    assert result["complete"]
    assert audit_session(tmp_path / "smoke")["checks_passed"]
    import json

    state = json.loads((tmp_path / "smoke" / "summary.json").read_text())
    name, account = next(iter(state["accounts"].items()))
    workflow, _, _ = build_experiment(periods=2)
    text = Template(
        workflow.steps[2].survey.questions[0].question_text, undefined=StrictUndefined
    ).render(shared_state={"market": {"your_account": account, "tape": state["tape"]}})
    assert "Your rationale: Scripted" in text
    assert "{{" not in text
