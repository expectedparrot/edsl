import pytest
import asyncio
from typing import Any
from edsl.data.Cache import main
from edsl.enums import LanguageModelType, InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel
from edsl.data.Cache import Cache


def test_Cache_main():
    main()

class TestLanguageModelGood(LanguageModel):
    use_cache = False
    _model_ = LanguageModelType.TEST.value
    _parameters_ = {"temperature": 0.5}
    _inference_service_ = InferenceServiceType.TEST.value

    async def async_execute_model_call(
        self, user_prompt: str, system_prompt: str
    ) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        return {"message": """{"answer": "Hello world"}"""}

    def parse_response(self, raw_response: dict[str, Any]) -> str:
        return raw_response["message"]
    

def test_caching():
    m = TestLanguageModelGood()
    c = Cache()
    from edsl import QuestionFreeText
    results = QuestionFreeText.example().by(m).run(cache = c)
    assert not results.select('raw_model_response.how_are_you_raw_model_response').first()['cached_response']
    results = QuestionFreeText.example().by(m).run(cache = c)
    assert results.select('raw_model_response.how_are_you_raw_model_response').first()['cached_response']
    
if __name__ == "__main__":
    test_Cache_main()
    test_caching()