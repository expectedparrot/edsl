from types import SimpleNamespace

from edsl.jobs.cost_estimate_contract import apply_cost_estimate_contract


def _job(model, service="openai", **parameters):
    return SimpleNamespace(
        models=[
            SimpleNamespace(
                model=model,
                _inference_service_=service,
                parameters=parameters,
            )
        ]
    )


def test_default_reasoning_model_cost_is_labeled_lower_bound():
    result = apply_cost_estimate_contract(
        _job("gpt-5-nano"),
        {"cost_in_usd": 0.0019, "cost_in_credits": 0.19},
    )

    assert result["usd"] == 0.0019
    assert result["estimate_kind"] == "lower_bound"
    assert result["is_exact"] is False
    assert result["lower_bound_usd"] == 0.0019
    assert result["expected_usd"] is None
    reasoning = result["assumptions"]["reasoning_tokens"]
    assert reasoning["included_in_point_estimate"] is False
    assert reasoning["models"][0]["reasoning_setting_source"] == "model_default"
    assert result["warnings"]


def test_explicit_reasoning_setting_is_machine_readable():
    result = apply_cost_estimate_contract(
        _job("custom-model", service="custom", reasoning_effort="high"),
        {"cost_in_usd": 1.0, "cost_in_credits": 100},
    )

    model = result["assumptions"]["reasoning_tokens"]["models"][0]
    assert result["estimate_kind"] == "lower_bound"
    assert model["reasoning_setting"] == "high"
    assert model["reasoning_setting_source"] == "explicit"


def test_non_reasoning_model_remains_point_estimate():
    result = apply_cost_estimate_contract(
        _job("gpt-4o"),
        {"cost_in_usd": 0.5, "cost_in_credits": 50},
    )

    assert result["estimate_kind"] == "point_estimate"
    assert result["warnings"] == []


def test_richer_server_range_is_preserved():
    response = {
        "cost_in_usd": 1.0,
        "cost_in_credits": 100,
        "estimate_kind": "range",
        "lower_bound_usd": 1.0,
        "expected_usd": 1.5,
        "upper_bound_usd": 2.0,
        "assumptions": {"reasoning_tokens": {"expected_tokens": 500}},
        "pricing_revision": "2026-08-01",
        "warnings": [],
    }

    assert apply_cost_estimate_contract(_job("gpt-5-nano"), response) == {
        "credits_hold": 100,
        "usd": 1.0,
        **{key: value for key, value in response.items() if not key.startswith("cost_in_")},
    }
