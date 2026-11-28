from edsl.inference_services.services.groq_service import GroqService


def test_async_client_does_not_pass_openai_specific_http_client(monkeypatch):
    client = object()
    client_kwargs = []

    def make_async_client(**kwargs):
        client_kwargs.append(kwargs)
        return client

    monkeypatch.setattr(
        GroqService, "_resolve_clients", classmethod(lambda cls: None)
    )
    monkeypatch.setattr(GroqService, "_async_client_", make_async_client)
    monkeypatch.setattr(GroqService, "_async_client_instances", {})

    first = GroqService.async_client("test-api-key", "https://groq.example/v1")
    second = GroqService.async_client("test-api-key", "https://groq.example/v1")

    assert first is client
    assert second is client
    assert client_kwargs == [
        {"api_key": "test-api-key", "base_url": "https://groq.example/v1"}
    ]
