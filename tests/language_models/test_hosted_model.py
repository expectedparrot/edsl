import pytest

from edsl import HostedModel
from edsl.inference_services.services.openai_compatible_service import (
    OpenAICompatibleService,
)
from edsl.language_models import LanguageModel


def test_hosted_model_uses_openai_compatible_service():
    model = HostedModel(
        "custom-model",
        base_url="https://models.example.com/v1/",
        api_key_env="CUSTOM_MODEL_API_KEY",
        temperature=0.2,
    )

    assert isinstance(model, LanguageModel)
    assert model.model == "custom-model"
    assert model._inference_service_ == "openai_compatible"
    assert model.base_url == "https://models.example.com/v1"
    assert model.api_key_env == "CUSTOM_MODEL_API_KEY"
    assert model.temperature == 0.2


def test_hosted_model_round_trip_uses_standard_serialization():
    model = HostedModel(
        "custom-model",
        base_url="https://models.example.com/v1",
        api_key_env="CUSTOM_MODEL_API_KEY",
        max_tokens=123,
    )

    serialized = model.to_dict(add_edsl_version=False)
    restored = LanguageModel.from_dict(serialized)

    assert serialized["connection"] == {
        "base_url": "https://models.example.com/v1",
        "api_key_env": "CUSTOM_MODEL_API_KEY",
    }
    assert "api_token" not in str(serialized)
    assert restored._inference_service_ == "openai_compatible"
    assert restored.base_url == model.base_url
    assert restored.api_key_env == model.api_key_env
    assert restored.max_tokens == 123


def test_hosted_model_resolves_credential_from_named_environment_variable(
    monkeypatch,
):
    captured = {}

    def fake_sync_client(cls, api_key, base_url=None):
        captured.update(api_key=api_key, base_url=base_url)
        return object()

    monkeypatch.setenv("CUSTOM_MODEL_API_KEY", "secret-value")
    monkeypatch.setattr(
        OpenAICompatibleService,
        "sync_client",
        classmethod(fake_sync_client),
    )
    model = HostedModel(
        "custom-model",
        base_url="https://models.example.com/v1",
        api_key_env="CUSTOM_MODEL_API_KEY",
    )

    model.sync_client()

    assert captured == {
        "api_key": "secret-value",
        "base_url": "https://models.example.com/v1",
    }


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("", "https://models.example.com/v1", None), "model_name"),
        (("custom-model", "", None), "base_url"),
        (("custom-model", "https://models.example.com/v1", ""), "api_key_env"),
    ],
)
def test_hosted_model_rejects_empty_connection_fields(args, message):
    model_name, base_url, api_key_env = args
    with pytest.raises(ValueError, match=message):
        HostedModel(model_name, base_url=base_url, api_key_env=api_key_env)
