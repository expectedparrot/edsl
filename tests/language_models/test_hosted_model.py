from edsl.language_models.hosted_model import (
    HostedModel,
    HostedOpenAICompatibleLanguageModel,
)


def test_hosted_model_accepts_an_injected_api_token():
    model = HostedModel(
        "custom-model",
        base_url="https://models.example/v1/",
        api_token="secret-token",
    )

    assert model.api_token == "secret-token"
    assert model.base_url == "https://models.example/v1"


def test_hosted_model_public_name_is_the_concrete_type():
    model = HostedModel("custom-model", base_url="https://models.example/v1")

    assert isinstance(model, HostedModel)
    assert isinstance(model, HostedOpenAICompatibleLanguageModel)
