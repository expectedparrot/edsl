"""Regression tests for the Google Vertex review fixes:

1. a custodial service-account key never lands in serialized model parameters;
2. a supplied-but-invalid key raises instead of silently using another account;
3. the cached client is rebuilt when the Vertex settings change.
"""

import asyncio
import json

import pytest

from edsl import Model
from edsl.inference_services.services import google_service as gs

SECRET = '{"type": "service_account", "private_key": "-----BEGIN SECRET-----"}'


def _google_model(**kwargs):
    return Model("gemini-2.5-flash", service_name="google", **kwargs)


# ---- 1. no private key in serialized parameters ----------------------------


def test_vertex_credentials_not_a_parameter():
    m = _google_model()
    assert "vertex_credentials" not in m.parameters


def test_key_passed_as_kwarg_never_serialized():
    m = _google_model(vertex_credentials=SECRET)
    blob = json.dumps(m.to_dict())
    assert "BEGIN SECRET" not in blob
    assert "vertex_credentials" not in m.parameters
    # still usable by the client builder
    assert m.vertex_credentials == SECRET


def test_key_set_by_worker_never_serialized():
    m = _google_model()
    m.vertex_credentials = SECRET  # what coopr's worker does server-side
    assert "BEGIN SECRET" not in json.dumps(m.to_dict())


# ---- 2. invalid supplied key raises, never falls back ----------------------


@pytest.mark.parametrize("bad", ['{invalid', "not-json-at-all"])
def test_invalid_explicit_key_raises(bad):
    with pytest.raises(ValueError) as exc:
        gs._vertex_credentials_and_project(bad)
    assert "BEGIN" not in str(exc.value)  # key material not echoed


def test_invalid_env_key_raises(monkeypatch):
    var = gs._VERTEX_SA_JSON_ENV_VARS[0]
    monkeypatch.setenv(var, "{broken")
    with pytest.raises(ValueError):
        gs._vertex_credentials_and_project(None)


def test_no_key_supplied_falls_back_to_adc(monkeypatch):
    for var in gs._VERTEX_SA_JSON_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    assert gs._vertex_credentials_and_project(None) == (None, None)


# ---- 3. client cache keyed on vertex settings -------------------------------


def test_client_rebuilt_when_vertex_settings_change(monkeypatch):
    builds = []

    def fake_build(api_token, **kw):
        builds.append(kw)
        return object()  # a "client"; using it fails, so no network call

    monkeypatch.setattr(gs, "_build_genai_client", fake_build)
    m = _google_model(use_vertex=True, vertex_project="proj-a")
    m._api_token = "test-token"

    def call():
        try:
            asyncio.run(m.async_execute_model_call(user_prompt="hi"))
        except Exception:
            pass

    call()
    call()  # same settings -> cached client reused, no rebuild
    assert len(builds) == 1
    m.vertex_project = "proj-b"  # same api token, different project
    call()
    m.vertex_credentials = SECRET  # credentials change -> rebuild too
    call()
    assert [b["vertex_project"] for b in builds] == ["proj-a", "proj-b", "proj-b"]


def test_gemini_3_keeps_explicit_sampling_overrides(monkeypatch):
    captured = {}

    class FakeTypes:
        @staticmethod
        def SafetySetting(**kwargs):
            return kwargs

        @staticmethod
        def ThinkingConfig(**kwargs):
            return kwargs

        @staticmethod
        def GenerateContentConfig(**kwargs):
            return kwargs

    class FakeModels:
        async def generate_content(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"model_dump": lambda self, **kw: {"text": "ok"}})()

    class FakeClient:
        aio = type("Aio", (), {"models": FakeModels()})()

    monkeypatch.setattr(gs, "_get_types", lambda: FakeTypes)
    monkeypatch.setattr(gs, "_build_genai_client", lambda *args, **kwargs: FakeClient())
    model = gs.GoogleService.create_model("gemini-3-flash-preview")(
        temperature=0.3,
        topP=0.8,
        topK=12,
        skip_api_key_check=True,
    )
    asyncio.run(model.async_execute_model_call(user_prompt="hello"))

    config = captured["config"]
    assert config["temperature"] == 0.3
    assert config["top_p"] == 0.8
    assert config["top_k"] == 12
    assert config["thinking_config"] == {"thinking_level": "HIGH"}

    model_with_budget = gs.GoogleService.create_model("gemini-3-flash-preview")(
        thinking_budget=128,
        skip_api_key_check=True,
    )
    asyncio.run(model_with_budget.async_execute_model_call(user_prompt="hello"))

    assert captured["config"]["thinking_config"] == {"thinking_budget": 128}
