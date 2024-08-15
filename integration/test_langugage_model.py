import asyncio
from typing import Any, Coroutine

from edsl.language_models import LanguageModel


class DummyModel(LanguageModel):
    model_ = "dummy"

    async def async_execute_model_call(self, *args, **kwargs) -> Coroutine:
        await asyncio.sleep(0)
        data = {"content": """{"answer": "SPAM", "comment": "This is a comment"}"""}
        return data

    def parse_response(self, raw_response: dict[str, Any]) -> str:
        return raw_response["content"]


def test_lm():
    lm = DummyModel())
    lm.model = "dummy"
    lm.parameters = {}
    assert lm.get_response(user_prompt="blah", system_prompt="blah") == {
        "answer": "SPAM",
        "comment": "This is a comment",
    }
