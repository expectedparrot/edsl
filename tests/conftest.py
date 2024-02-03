import pytest


@pytest.fixture(scope="function")
def model_with_cache_fixture():
    """A fixture that returns a fake model that uses the cache."""
    import asyncio
    import random
    import uuid
    from typing import Any
    from edsl.language_models.LanguageModel import LanguageModel
    from edsl.enums import LanguageModelType, InferenceServiceType

    class TestLanguageModelGood(LanguageModel):
        _model_ = LanguageModelType.TEST.value
        _parameters_ = {"temperature": 0.5, "use_cache": True}
        _inference_service_ = InferenceServiceType.TEST.value

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            await asyncio.sleep(random.uniform(0.0, 10.0))
            my_answer = str(uuid.uuid4())
            return {"message": '{"answer": "' + my_answer + '"}'}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["message"]

    model = TestLanguageModelGood
    return model


@pytest.fixture(scope="function")
def longer_api_timeout_fixture(monkeypatch):
    """A fixture that sets a longer timeout for API calls."""
    from edsl import CONFIG

    original_get = CONFIG.get
    new_timeout = "200"

    def custom_get(env_var):
        if env_var == "API_CALL_TIMEOUT_SEC":
            return new_timeout
        return original_get(env_var)

    monkeypatch.setattr(CONFIG, "get", custom_get)
    yield
    monkeypatch.setattr(CONFIG, "get", original_get)
