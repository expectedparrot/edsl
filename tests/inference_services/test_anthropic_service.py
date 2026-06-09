import asyncio

from edsl.inference_services.services.anthropic_service import AnthropicService


def test_requires_temperature_one_for_models_after_opus_46():
    assert AnthropicService._requires_temperature_one(
        "claude-sonnet-4-6-20260217"
    )
    assert AnthropicService._requires_temperature_one("claude-opus-4-7-20260416")
    assert AnthropicService._requires_temperature_one("claude-opus-4-7")
    assert not AnthropicService._requires_temperature_one("claude-opus-4-6-20260205")
    assert not AnthropicService._requires_temperature_one("claude-opus-4-5-20251124")
    assert not AnthropicService._requires_temperature_one("claude-3-5-sonnet-20241022")


def test_anthropic_request_uses_temperature_one_for_affected_models(monkeypatch):
    captured_kwargs = {}

    class DummyResponse:
        def model_dump(self):
            return {"content": [{"type": "text", "text": "ok"}]}

    class DummyMessages:
        async def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return DummyResponse()

    class DummyAnthropicClient:
        def __init__(self, api_key):
            self.messages = DummyMessages()

    monkeypatch.setattr(
        "edsl.inference_services.services.anthropic_service.AsyncAnthropic",
        DummyAnthropicClient,
    )

    model_class = AnthropicService.create_model("claude-sonnet-4-6-20260217")
    model = model_class(temperature=0.2, skip_api_key_check=True)

    asyncio.run(model.async_execute_model_call("hello"))

    assert captured_kwargs["temperature"] == 1.0
    assert model.temperature == 0.2
    assert model.parameters["temperature"] == 0.2


def test_anthropic_request_preserves_temperature_for_legacy_models(monkeypatch):
    captured_kwargs = {}

    class DummyResponse:
        def model_dump(self):
            return {"content": [{"type": "text", "text": "ok"}]}

    class DummyMessages:
        async def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return DummyResponse()

    class DummyAnthropicClient:
        def __init__(self, api_key):
            self.messages = DummyMessages()

    monkeypatch.setattr(
        "edsl.inference_services.services.anthropic_service.AsyncAnthropic",
        DummyAnthropicClient,
    )

    model_class = AnthropicService.create_model("claude-opus-4-5-20251124")
    model = model_class(temperature=0.2, skip_api_key_check=True)

    asyncio.run(model.async_execute_model_call("hello"))

    assert captured_kwargs["temperature"] == 0.2
