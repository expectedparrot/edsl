import pytest

from edsl.inference_services.services.deep_infra_service import DeepInfraService
from edsl.inference_services.services.open_router_service import OpenRouterService
from edsl.inference_services.services.open_ai_service import OpenAIParameterBuilder
from edsl.inference_services.services.google_service import GoogleService
from edsl.language_models.output_token_policy import (
    model_token_policy,
    reasoning_capability,
    token_limit_warnings,
)


@pytest.mark.parametrize("service", [DeepInfraService, OpenRouterService])
@pytest.mark.parametrize(
    "name",
    [
        "deepseek-ai/DeepSeek-R1",
        "Qwen/QwQ-32B",
        "openai/gpt-5.4",
        "google/gemini-3.1-pro",
    ],
)
def test_reasoning_defaults_across_services(service, name):
    factory = service.create_model(name)
    default = factory(skip_api_key_check=True)
    assert default.max_tokens == 16000
    explicit = factory(max_tokens=1000, skip_api_key_check=True)
    assert explicit.max_tokens == 1000
    assert token_limit_warnings([explicit])
    restored = factory(parameters=explicit.parameters, skip_api_key_check=True)
    assert restored.max_tokens == 1000
    assert model_token_policy(default)["reasoning"] is True


def test_unknown_model_has_conservative_inspectable_policy():
    model = DeepInfraService.create_model("unknown/model")(skip_api_key_check=True)
    assert model.max_tokens == 2000
    assert model_token_policy(model)["reasoning"] is None
    assert not token_limit_warnings([model])
    assert reasoning_capability("gpt-4o-mini") is False


def test_google_aliases_and_serialized_limits_are_preserved():
    factory = GoogleService.create_model("gemini-2.5-pro")
    assert factory(skip_api_key_check=True).maxOutputTokens == 16000
    for kwargs in (
        {"max_tokens": 999},
        {"max_output_tokens": 999},
        {"maxOutputTokens": 999},
        {"parameters": {"maxOutputTokens": 999}},
    ):
        assert factory(skip_api_key_check=True, **kwargs).maxOutputTokens == 999


def test_openai_builder_does_not_increase_explicit_limit():
    assert (
        OpenAIParameterBuilder.build_params("o3", [], max_tokens=1000)[
            "max_completion_tokens"
        ]
        == 1000
    )
    assert (
        OpenAIParameterBuilder.build_params("o3", [])["max_completion_tokens"] == 16000
    )


def test_low_limit_warning_at_job_submission():
    from edsl import QuestionFreeText
    from edsl.runner.service import JobService
    from edsl.runner.storage import InMemoryStorage

    model = DeepInfraService.create_model("deepseek-ai/DeepSeek-R1")(
        max_tokens=1000, skip_api_key_check=True
    )
    job = QuestionFreeText(question_name="q", question_text="Hi").by(model)
    with pytest.warns(UserWarning, match="share the output budget"):
        JobService(InMemoryStorage()).submit_job(job)
    assert model.max_tokens == 1000


@pytest.mark.parametrize("service", [DeepInfraService, OpenRouterService])
@pytest.mark.parametrize("limit", [None, 1000])
def test_resolved_budget_reaches_provider_request(monkeypatch, service, limit):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    kwargs = {} if limit is None else {"max_tokens": limit}
    model = service.create_model("deepseek-ai/DeepSeek-R1")(
        skip_api_key_check=True, **kwargs
    )
    create = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {"choices": []}))
    monkeypatch.setattr(
        model,
        "async_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )
    monkeypatch.setattr(model, "sync_client", lambda: None)
    asyncio.run(model.async_execute_model_call(user_prompt="Hi", system_prompt=""))
    params = create.call_args.kwargs
    assert params.get("max_tokens", params.get("max_completion_tokens")) == (
        16000 if limit is None else limit
    )


def test_explicit_thinking_and_azure_limits():
    from edsl.inference_services.services.anthropic_service import AnthropicService
    from edsl.inference_services.services.azure_ai import AzureParameterBuilder

    model = AnthropicService.create_model("claude-sonnet-4-5")(
        thinking={"type": "enabled", "budget_tokens": 8000},
        skip_api_key_check=True,
    )
    assert model.max_tokens == 16000
    assert (
        AzureParameterBuilder.build_params("o3", [], max_tokens=999)["max_tokens"]
        == 999
    )


def test_costing_exposes_increased_output_budget():
    from edsl import QuestionNumerical
    from edsl.jobs.cost_estimation.job_cost_estimator import JobCostEstimator

    factory = DeepInfraService.create_model("deepseek-ai/DeepSeek-R1")
    prices = {
        ("deep_infra", "deepseek-ai/DeepSeek-R1"): {
            side: {
                "one_usd_buys": 1_000_000,
                "service_stated_token_price": 1,
                "service_stated_token_qty": 1_000_000,
            }
            for side in ("input", "output")
        }
    }
    estimates = []
    for limit in (1000, 16000):
        model = factory(max_tokens=limit, skip_api_key_check=True)
        job = QuestionNumerical(question_name="q", question_text="One decimal?").by(
            model
        )
        estimates.append(JobCostEstimator().estimate_cost(job, price_lookup=prices))
    assert any(
        "share the output budget" in warning for warning in estimates[0].warnings
    )
    low, high = (estimate._rows[0] for estimate in estimates)
    assert high["output_budget_cost_usd"] == 16 * low["output_budget_cost_usd"]
    assert high["output_token_limit"] == 16000


def test_mistral_does_not_drop_configured_output_limit(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    pytest.importorskip("mistralai")
    from edsl.inference_services.services.mistral_ai_service import MistralAIService

    model = MistralAIService.create_model("mistral-small-latest")(
        max_tokens=1234, skip_api_key_check=True
    )
    complete = AsyncMock(
        return_value=SimpleNamespace(model_dump=lambda: {"choices": []})
    )
    monkeypatch.setattr(
        model,
        "async_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(complete_async=complete)),
    )
    asyncio.run(model.async_execute_model_call(user_prompt="Hi"))
    assert complete.call_args.kwargs["max_tokens"] == 1234


def test_meta_payload_forwards_configured_limit():
    from edsl.inference_services.services.meta_service import MetaService

    model = MetaService.create_model("muse-spark-1.1")(
        max_tokens=1234, skip_api_key_check=True
    )
    assert model._payload(user_prompt="Hi")["max_output_tokens"] == 1234
    assert reasoning_capability("mistralai/magistral-small-2509") is True
