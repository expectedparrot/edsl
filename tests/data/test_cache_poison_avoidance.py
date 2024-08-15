import pytest
import unittest
import asyncio
from typing import Any
from unittest.mock import Mock
from edsl.agents.Invigilator import InvigilatorAI

from edsl import Agent
from edsl.language_models import LanguageModel
from edsl.enums import InferenceServiceType


def create_language_model(
    exception: Exception, fail_at_number: int, never_ending=False, invalid_json=False
):
    class TestLanguageModel(LanguageModel):
        _model_ = "gpt-4-1106-preview"
        _parameters_ = {"temperature": 0.5}
        _inference_service_ = InferenceServiceType.TEST.value

        async def async_execute_model_call(
            self, user_prompt: str, system_prompt: str
        ) -> dict[str, Any]:
            question_number = int(
                user_prompt.split("XX")[1]
            )  ## grabs the question number from the prompt
            await asyncio.sleep(0.1)
            if never_ending:  ## you're not going anywhere buddy
                await asyncio.sleep(float("inf"))
            if question_number == fail_at_number:
                if asyncio.iscoroutinefunction(exception):
                    await exception()
                else:
                    raise exception
            if invalid_json:
                return {"message": """{"answer_bad_key": "SPAM!"}"""}
            else:
                return {"message": """{"answer": 1}"""}

        def parse_response(self, raw_response: dict[str, Any]) -> str:
            return raw_response["message"]

    return TestLanguageModel


from edsl.data import Cache
from edsl.prompts.Prompt import Prompt


c = Cache()
a = Agent()

from edsl.questions import QuestionNumerical

q = QuestionNumerical.example()


class InvigilatorTest(InvigilatorAI):
    def get_prompts(self):
        return {
            "user_prompt": Prompt("XX1XX"),
            "system_prompt": Prompt("XX1XX"),
        }


def test_bad_answer_not_cached():
    from edsl import Survey

    m = create_language_model(
        exception=ValueError, fail_at_number=10, invalid_json=True
    )()
    i = InvigilatorTest(
        agent=a,
        model=m,
        question=q,
        scenario={},
        memory_plan=Mock(),
        current_answers=Mock(),
        survey=Survey.example(),
        cache=c,
    )

    with pytest.raises(Exception):
        response = i.answer_question()

    assert c.data == {}


def test_good_answer_cached():
    from edsl import Survey

    m = create_language_model(
        exception=ValueError, fail_at_number=10, invalid_json=False
    )()
    i = InvigilatorTest(
        agent=a,
        model=m,
        question=q,
        scenario={},
        memory_plan=Mock(),
        current_answers={},
        survey=Survey.example(),
        cache=c,
    )

    response = i.answer_question()

    assert c.data != {}
