import pytest


@pytest.fixture(scope="function")
def test_language_model_good_fixture():
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
            await asyncio.sleep(random.uniform(0.0, 0.5))
            my_answer = str(uuid.uuid4())
            return {"message": '{"answer": "' + my_answer + '"}'}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["message"]

    model = TestLanguageModelGood
    return model
