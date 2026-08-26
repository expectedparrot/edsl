"""Structured uncertainty metadata for remote job cost estimates."""

from __future__ import annotations

from typing import Any


def _reasoning_model(model: Any) -> dict[str, Any] | None:
    service = str(getattr(model, "_inference_service_", "") or "").lower()
    name = str(getattr(model, "model", "") or "").lower()
    parameters = dict(getattr(model, "parameters", {}) or {})
    setting = parameters.get("reasoning_effort", parameters.get("reasoning"))
    openai_reasoning_name = name.startswith(("gpt-5", "o1", "o3", "o4"))
    explicit_reasoning = setting is not None
    if not (explicit_reasoning or (service.startswith("openai") and openai_reasoning_name)):
        return None
    return {
        "inference_service": service,
        "model": name,
        "reasoning_setting": setting,
        "reasoning_setting_source": "explicit" if explicit_reasoning else "model_default",
    }


def apply_cost_estimate_contract(job: Any, response_json: dict) -> dict:
    """Normalize server cost data and expose known reasoning-token uncertainty."""
    cost = {
        "credits_hold": response_json.get("cost_in_credits"),
        "usd": response_json.get("cost_in_usd"),
    }
    # Prefer a richer server contract when available and retain its assumptions.
    for key in (
        "estimate_kind",
        "lower_bound_usd",
        "expected_usd",
        "upper_bound_usd",
        "lower_bound_credits",
        "expected_credits",
        "upper_bound_credits",
        "assumptions",
        "pricing_revision",
        "warnings",
    ):
        if key in response_json:
            cost[key] = response_json[key]

    if "estimate_kind" in response_json:
        return cost

    reasoning_models = [
        details
        for model in getattr(job, "models", [])
        if (details := _reasoning_model(model)) is not None
    ]
    cost["is_exact"] = False
    if reasoning_models:
        warning = (
            "The server point estimate does not specify a reasoning-token assumption; "
            "treat this amount as a lower bound because billed reasoning usage is workload-dependent."
        )
        cost.update(
            {
                "estimate_kind": "lower_bound",
                "lower_bound_usd": cost["usd"],
                "expected_usd": None,
                "upper_bound_usd": None,
                "lower_bound_credits": cost["credits_hold"],
                "expected_credits": None,
                "upper_bound_credits": None,
                "assumptions": {
                    "ordinary_input_tokens": "included in server estimate",
                    "cached_input_tokens": "server-defined",
                    "visible_output_tokens": "included in server estimate",
                    "reasoning_tokens": {
                        "included_in_point_estimate": False,
                        "expected_tokens": None,
                        "upper_bound_tokens": None,
                        "models": reasoning_models,
                    },
                    "pricing_revision": response_json.get("pricing_revision"),
                },
                "warnings": [warning],
            }
        )
    else:
        cost.update(
            {
                "estimate_kind": "point_estimate",
                "assumptions": {
                    "reasoning_tokens": {
                        "included_in_point_estimate": True,
                        "expected_tokens": 0,
                        "models": [],
                    },
                    "pricing_revision": response_json.get("pricing_revision"),
                },
                "warnings": [],
            }
        )
    return cost
