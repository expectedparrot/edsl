import asyncio

from edsl.inference_services.services.meta_service import MetaService


def test_meta_payload_uses_responses_input_text_shape():
    model_class = MetaService.create_model("muse-spark-1.1")
    model = model_class(skip_api_key_check=True)

    payload = model._payload(
        user_prompt="Write a haiku.",
        system_prompt="Be concise.",
    )

    assert payload["model"] == "muse-spark-1.1"
    assert payload["stream"] is False
    assert payload["input"] == [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": "Be concise."}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": "Write a haiku."}],
        },
    ]


def test_meta_response_text_extracts_output_text():
    model_class = MetaService.create_model("muse-spark-1.1")

    assert model_class._response_text({"output_text": "hello"}) == "hello"
    assert (
        model_class._response_text(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "hello"},
                            {"type": "output_text", "text": "world"},
                        ]
                    }
                ]
            }
        )
        == "hello\nworld"
    )


def test_meta_async_call_normalizes_response(monkeypatch):
    captured = {}

    class DummyResponse:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def raise_for_status(self):
            return None

        async def json(self):
            return {
                "output": [{"content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {"input_tokens": 3, "output_tokens": 2, "total": 5},
            }

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def post(self, url, headers, json, timeout):
            captured.update(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": timeout,
                }
            )
            return DummyResponse()

    monkeypatch.setattr(
        "edsl.inference_services.services.meta_service.aiohttp.ClientSession",
        DummySession,
    )

    model_class = MetaService.create_model("muse-spark-1.1")
    model = model_class(skip_api_key_check=True)
    model._api_token = "test-token"

    response = asyncio.run(model.async_execute_model_call("hello"))

    assert captured["url"] == "https://api.meta.ai/v1/responses"
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    assert captured["json"]["input"][0]["content"][0]["type"] == "input_text"
    assert response["choices"][0]["message"]["content"] == "ok"
    assert response["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }
