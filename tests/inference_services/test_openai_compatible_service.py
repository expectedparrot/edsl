import asyncio
import os

import pytest

from edsl.inference_services.inference_service_registry import InferenceServiceRegistry
from edsl.inference_services.services.openai_compatible_service import (
    OpenAICompatibleService,
)
from edsl.language_models import Model


def test_service_is_registered():
    registry = InferenceServiceRegistry()
    assert "openai_compatible" in registry.list_registered_services()


def test_model_connection_round_trip():
    model = Model(
        "local-model",
        service_name="openai_compatible",
        base_url="http://127.0.0.1:8080/v1",
        api_key_env="LOCAL_API_KEY",
        temperature=0.2,
    )
    restored = model.from_dict(model.to_dict())
    assert restored._inference_service_ == "openai_compatible"
    assert restored.base_url == "http://127.0.0.1:8080/v1"
    assert restored.api_key_env == "LOCAL_API_KEY"
    assert restored.temperature == 0.2
    assert "base_url" not in restored.parameters


def test_close_async_clients_clears_subclass_cache():
    class FakeClient:
        closed = False

        async def close(self):
            self.closed = True

    client = FakeClient()
    OpenAICompatibleService._async_client_instances = {("local", "url"): client}
    asyncio.run(OpenAICompatibleService.close_async_clients())
    assert client.closed is True
    assert OpenAICompatibleService._async_client_instances == {}


def test_live_openai_compatible_endpoint():
    """Run only when a developer explicitly supplies a local endpoint and model."""
    base_url = os.getenv("EDSL_OPENAI_COMPATIBLE_TEST_URL")
    model_name = os.getenv("EDSL_OPENAI_COMPATIBLE_TEST_MODEL")
    if not base_url or not model_name:
        pytest.skip(
            "Set EDSL_OPENAI_COMPATIBLE_TEST_URL and "
            "EDSL_OPENAI_COMPATIBLE_TEST_MODEL for the live integration test"
        )

    from edsl import Model, QuestionFreeText

    model = Model(
        model_name,
        service_name="openai_compatible",
        base_url=base_url,
        max_tokens=64,
        temperature=0.0,
    )
    question = QuestionFreeText(
        question_name="local_smoke",
        question_text="Reply with the single word ok.",
    )
    results = question.by(model).run(
        cache=False,
        disable_remote_inference=True,
        progress_bar=False,
    )

    answer = results.select("answer.local_smoke").first()
    assert isinstance(answer, str)
    assert answer.strip()
    assert results[0].model._inference_service_ == "openai_compatible"
