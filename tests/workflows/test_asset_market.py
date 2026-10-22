"""Economic invariants and workflow visibility for the asset-market example."""

from copy import deepcopy
import json

import pytest

from edsl.sharedstate import SQLiteStateBackend
from edsl.workflows import HumanWorkflow, SQLiteWorkflowStore, WorkflowCoordinator
from examples.asset_market.experiment import (
    build_experiment,
    compositions,
    market_runtime,
    metrics,
    settle_market,
    submit_order,
)
from examples.asset_market.run import run_session


def initial():
    _, states, _ = build_experiment(periods=2)
    spec = states.definition.machines["market"]
    return market_runtime().initial_state(spec)


def order(side="hold", price=0.0, quantity=0):
    return dict(
        forecast_0=14.0,
        forecast_2=14.0,
        forecast_5=14.0,
        forecast_10=14.0,
        side=side,
        price=price,
        quantity=quantity,
        rationale="test",
    )


def submit_all(state, overrides=None):
    for name in state["accounts"]:
        submit_order(
            state,
            {
                "trader": name,
                "period": state["period"],
                "decision": (overrides or {}).get(name, order()),
            },
            {},
        )


def test_call_market_uniform_price_income_and_redemption():
    state = initial()
    submit_all(
        state,
        {
            "trader-00": order("buy", 20.0, 2),
            "trader-01": order("buy", 18.0, 1),
            "trader-02": order("sell", 12.0, 2),
            "trader-03": order("sell", 16.0, 1),
        },
    )
    settle_market(state, {"period": 1}, {"seed": 1, "periods": 2})
    assert state["tape"][0]["price"] == 17.0
    assert state["tape"][0]["volume"] == 3
    assert state["accounts"]["trader-00"]["shares"] == 6
    assert state["accounts"]["trader-02"]["shares"] == 2
    assert sum(a["shares"] for a in state["accounts"].values()) == 48
    dividend = int(state["tape"][0]["dividend"] * 100)
    # $100 - 2*$17, plus 5% interest, plus dividends on six shares.
    assert state["accounts"]["trader-00"]["cash_cents"] == 6600 + 330 + 6 * dividend
    pre = deepcopy(state["accounts"])
    submit_all(state)
    settle_market(state, {"period": 2}, {"seed": 1, "periods": 2})
    assert state["finished"]
    assert state["tape"][1]["price"] is None
    dividend = int(state["tape"][1]["dividend"] * 100)
    for name, a in state["accounts"].items():
        old = pre[name]
        assert a["cash_cents"] == old["cash_cents"] + (
            old["cash_cents"] * 5 + 50
        ) // 100 + old["shares"] * (dividend + 1400)
        assert a["shares"] == 0
    with pytest.raises(ValueError):
        settle_market(state, {"period": 2}, {"seed": 1, "periods": 2})


def test_budget_limits_rejections_no_trade_and_barrier():
    state = initial()
    submit_order(
        state,
        {"trader": "trader-00", "period": 1, "decision": order("buy", 30, 999)},
        {},
    )
    assert state["orders"]["trader-00"]["accepted_quantity"] == 3
    with pytest.raises(ValueError, match="every trader"):
        settle_market(state, {"period": 1}, {"seed": 2, "periods": 2})
    with pytest.raises(ValueError, match="already submitted"):
        submit_order(
            state, {"trader": "trader-00", "period": 1, "decision": order()}, {}
        )
    for name in list(state["accounts"])[1:]:
        submit_order(
            state, {"trader": name, "period": 1, "decision": order("sell", -1, 1)}, {}
        )
        assert state["orders"][name]["accepted_quantity"] == 0
        assert state["orders"][name]["rejection"]
    settle_market(state, {"period": 1}, {"seed": 2, "periods": 2})
    assert state["tape"][0]["price"] is None
    assert state["last_price"] == 14
    assert metrics(state["tape"])["peak_fraction"] is None


def test_sealed_visibility_and_workflow_fan_in(tmp_path):
    workflow, states, agents = build_experiment(periods=2)
    assert HumanWorkflow.from_dict(workflow.to_dict()).to_dict() == workflow.to_dict()
    backend = SQLiteStateBackend(
        states, tmp_path / "state.sqlite", runtime=market_runtime()
    )
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        workflow, store, state_backends={states.state_id: backend}
    )
    instance = coordinator.launch(agents)
    traders = [i for i in store.items(instance) if i["step_name"] == "orders-1"]
    seen = []
    for item in traders:
        opened = coordinator.open(item["id"])
        observed = opened.shared_state["market"]
        assert set(observed) == {
            "period",
            "tape",
            "last_price",
            "your_account",
            "finished",
        }
        assert observed["tape"] == []
        assert observed["your_account"] == {
            "cash_cents": 10000,
            "shares": 4,
            "history": [],
        }
        seen.append(opened)
        coordinator.submit(
            item["id"], {"decision": order()}, idempotency_key=item["id"]
        )
        if len(seen) < 12:
            assert all(
                i["status"] != "ready"
                for i in store.items(instance)
                if i["step_name"] == "settle-1"
            )
    settlement = next(i for i in store.items(instance) if i["step_name"] == "settle-1")
    assert settlement["status"] == "ready"
    assert all(
        i["status"] != "ready"
        for i in store.items(instance)
        if i["step_name"] == "orders-2"
    )
    coordinator.open(settlement["id"])
    coordinator.submit(
        settlement["id"], {"settlement": "clear"}, idempotency_key="clear-1"
    )
    # A retried accepted submission must not pay the dividend twice.
    before = backend.snapshot("session")
    coordinator.submit(
        settlement["id"], {"settlement": "clear"}, idempotency_key="clear-1"
    )
    assert backend.snapshot("session").state == before.state
    assert all(
        i["status"] == "ready"
        for i in store.items(instance)
        if i["step_name"] == "orders-2"
    )


def test_recovery_and_design(tmp_path):
    config = {
        "output": str(tmp_path / "run"),
        "treatment": "evolved",
        "periods": 2,
        "seed": 1,
        "backend": "scripted",
        "model": None,
        "service": None,
        "base_url": None,
        "temperature": 0.7,
        "resume": False,
    }
    first = run_session(dict(config))
    before = json.loads((tmp_path / "run" / "summary.json").read_text())
    second = run_session({**config, "resume": True})
    assert first["metrics"] == second["metrics"]
    after = json.loads((tmp_path / "run" / "summary.json").read_text())
    assert before["accounts"] == after["accounts"]
    assert after["work_items"] == {"completed": 26}
    assert len(compositions()) == len(set(compositions())) == 63
    assert len(after["persona_assignment"]) == 12
    assert list(after["persona_assignment"].values()).count("trend_reader") == 7


def test_order_arrival_does_not_change_clearing():
    a, b = initial(), initial()
    submit_all(
        a,
        {
            name: order("buy" if i < 6 else "sell", 15 if i < 6 else 13, 2)
            for i, name in enumerate(a["accounts"])
        },
    )
    b["orders"] = dict(reversed(list(deepcopy(a["orders"]).items())))
    for state in [a, b]:
        settle_market(state, {"period": 1}, {"seed": 45, "periods": 2})
    assert a == b


def test_recover_accepted_settlement_after_lost_acknowledgement(tmp_path, monkeypatch):
    workflow, states, agents = build_experiment(periods=1)
    backend = SQLiteStateBackend(
        states, tmp_path / "state.sqlite", runtime=market_runtime()
    )
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        workflow, store, state_backends={states.state_id: backend}
    )
    instance = coordinator.launch(agents)
    for item in store.items(instance):
        if item["step_name"] == "orders-1":
            coordinator.open(item["id"])
            coordinator.submit(
                item["id"], {"decision": order()}, idempotency_key=item["id"]
            )
    settlement = next(i for i in store.items(instance) if i["step_name"] == "settle-1")
    coordinator.open(settlement["id"])
    original_apply = backend.apply

    def lost_acknowledgement(operation):
        original_apply(operation)
        raise RuntimeError("Simulated interruption after the state commit")

    monkeypatch.setattr(backend, "apply", lost_acknowledgement)
    with pytest.raises(RuntimeError, match="Simulated interruption"):
        coordinator.submit(
            settlement["id"], {"settlement": "clear"}, idempotency_key="settle"
        )
    assert store.item(settlement["id"])["status"] == "committing"
    paid = backend.snapshot("session").state
    assert paid["market"]["finished"]
    monkeypatch.setattr(backend, "apply", original_apply)
    restored = WorkflowCoordinator.restore(
        instance, store, state_backends={states.state_id: backend}
    )
    restored.recover(instance)
    assert store.item(settlement["id"])["status"] == "completed"
    assert backend.snapshot("session").state == paid
