"""Verify reasoning settings at the SDK boundary without credentials or network."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from edsl import Jobs, QuestionFreeText
from edsl.inference_services.services.open_ai_service import (
    OpenAIParameterBuilder,
    OpenAIService,
)
from edsl.inference_services.services.open_ai_service_v2 import OpenAIServiceV2
from edsl.language_models import LanguageModel


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(LanguageModel, "_set_key_lookup", lambda *a, **kw: {})
    monkeypatch.setattr("edsl.coop.Coop.report_error", AsyncMock())

    def unexpected_network(*args, **kwargs):
        pytest.fail("These adapter tests must not access the network")

    monkeypatch.setattr("socket.socket.connect", unexpected_network)


@pytest.fixture(params=[OpenAIService, OpenAIServiceV2], ids=["chat", "responses"])
def service(request):
    return request.param


def mock_create(monkeypatch, model):
    create = AsyncMock(return_value=SimpleNamespace(model_dump=lambda: {}))
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        responses=SimpleNamespace(create=create),
    )
    monkeypatch.setattr(type(model), "async_client", lambda self: client)
    monkeypatch.setattr(type(model), "sync_client", lambda self: client)
    return create


def request_effort(service, params):
    if service is OpenAIService:
        assert "reasoning" not in params
        return params.get("reasoning_effort")
    assert "reasoning_effort" not in params
    return params.get("reasoning", {}).get("effort")


@pytest.mark.parametrize(
    "name,effort",
    [
        ("gpt-6", "xhigh"),
        ("gpt-6-astra", "xhigh"),
        ("gpt-6-astra-2026-09-01", "xhigh"),
        ("gpt-5", "high"),
        ("gpt-5.6-terra", "high"),
        ("o1", "medium"),
        ("o3-mini-2025-01-31", "high"),
        ("o4-mini", "low"),
    ],
)
def test_explicit_effort_and_token_limit(monkeypatch, service, name, effort):
    model = service.create_model(name)(reasoning_effort=effort, max_tokens=64000)
    create = mock_create(monkeypatch, model)
    asyncio.run(model.async_execute_model_call("Return ok."))
    params = create.call_args.kwargs
    assert request_effort(service, params) == effort
    token_field = (
        "max_completion_tokens" if service is OpenAIService else "max_output_tokens"
    )
    assert params[token_field] == 64000
    assert "max_tokens" not in params


@pytest.mark.parametrize("round_trip", ["model", "jobs"])
@pytest.mark.parametrize("limit", [64, 64000])
def test_serialized_spec_preserves_outgoing_settings(
    monkeypatch, service, round_trip, limit
):
    model = service.create_model("gpt-6-astra")(
        reasoning_effort="xhigh", max_tokens=limit
    )
    if round_trip == "model":
        restored = LanguageModel.from_dict(json.loads(json.dumps(model.to_dict())))
    else:
        jobs = QuestionFreeText(question_name="q", question_text="Return ok.").by(model)
        restored = Jobs.from_dict(json.loads(json.dumps(jobs.to_dict()))).models[0]
    assert restored._inference_service_ == service._inference_service_
    create = mock_create(monkeypatch, restored)
    asyncio.run(restored.async_execute_model_call("Return ok."))
    params = create.call_args.kwargs
    assert request_effort(service, params) == "xhigh"
    token_field = (
        "max_completion_tokens" if service is OpenAIService else "max_output_tokens"
    )
    assert params[token_field] == limit


@pytest.mark.parametrize(
    "name", ["gpt-6", "gpt-6-astra", "gpt-5", "o3", "gpt-4o", "gpt-7"]
)
@pytest.mark.parametrize("options", [{}, {"reasoning_effort": None}])
def test_unspecified_effort_and_defaults(monkeypatch, service, name, options):
    model = service.create_model(name)(**options)
    create = mock_create(monkeypatch, model)
    asyncio.run(model.async_execute_model_call("Return ok."))
    params = create.call_args.kwargs
    known_reasoning = name not in {"gpt-4o", "gpt-7"}
    if service is OpenAIService:
        assert request_effort(service, params) == (
            "medium" if known_reasoning else None
        )
        assert params["max_completion_tokens"] == (5000 if known_reasoning else 1000)
    else:
        assert request_effort(service, params) is None
        assert params.get("reasoning") == (
            {"summary": "auto"} if known_reasoning else None
        )
        assert params["max_output_tokens"] == (16000 if known_reasoning else 2000)
    if not known_reasoning:
        assert "reasoning_effort" not in params
        assert "reasoning" not in params


@pytest.mark.parametrize("name", ["gpt-6-astra", "gpt-4o"])
@pytest.mark.parametrize(
    "options,expected",
    [
        (
            {"reasoning": {"effort": "xhigh", "summary": "detailed"}},
            {"effort": "xhigh", "summary": "detailed"},
        ),
        (
            {
                "reasoning": {"effort": "low", "summary": None},
                "reasoning_effort": "xhigh",
            },
            {"effort": "xhigh", "summary": None},
        ),
        (
            {"reasoning": {"effort": "high"}, "reasoning_effort": None},
            {"effort": "high"},
        ),
        ({"reasoning": {}}, {}),
    ],
)
def test_responses_dictionary_precedence_after_serialization(
    monkeypatch, name, options, expected
):
    original_options = json.loads(json.dumps(options))
    model = OpenAIServiceV2.create_model(name)(**options)
    restored = LanguageModel.from_dict(json.loads(json.dumps(model.to_dict())))
    create = mock_create(monkeypatch, restored)
    asyncio.run(restored.async_execute_model_call("Return ok."))
    defaults = {"summary": "auto"} if name == "gpt-6-astra" else {}
    assert create.call_args.kwargs["reasoning"] == {**defaults, **expected}
    assert model.reasoning == original_options["reasoning"]
    assert options == original_options


@pytest.mark.parametrize(
    "name,effort", [("gpt-4o", "xhigh"), ("gpt-6-astra", "none"), ("gpt-6-astra", "")]
)
def test_unsupported_effort_reaches_provider_and_error_propagates(
    monkeypatch, service, name, effort
):
    import httpx
    from openai import BadRequestError

    model = service.create_model(name)(reasoning_effort=effort)
    create = mock_create(monkeypatch, model)
    error = BadRequestError(
        "Unsupported reasoning effort for this model",
        response=httpx.Response(
            400, request=httpx.Request("POST", "https://example.test")
        ),
        body=None,
    )
    create.side_effect = error
    with pytest.raises(BadRequestError) as caught:
        asyncio.run(model.async_execute_model_call("Return ok."))
    assert caught.value is error
    create.assert_awaited_once()
    assert request_effort(service, create.call_args.kwargs) == effort


@pytest.mark.parametrize("reasoning", ["xhigh", [], False])
def test_invalid_reasoning_dictionary_fails_visibly(monkeypatch, reasoning):
    model = OpenAIServiceV2.create_model("gpt-6-astra")(reasoning=reasoning)
    create = mock_create(monkeypatch, model)
    with pytest.raises(ValueError, match="reasoning must be a dictionary or None"):
        asyncio.run(model.async_execute_model_call("Return ok."))
    create.assert_not_awaited()


def test_builder_defaults_do_not_raise_explicit_token_limits():
    assert (
        OpenAIParameterBuilder.build_params("gpt-6-astra", [])["max_completion_tokens"]
        == 5000
    )
    params = OpenAIParameterBuilder.build_params("gpt-6-astra", [], max_tokens=64)
    assert params["max_completion_tokens"] == 64
