import pytest
import unittest
import asyncio
from typing import Any
from unittest.mock import Mock
from edsl.agents.Invigilator import InvigilatorAI

from edsl import Agent
from edsl.language_models import LanguageModel
from edsl.enums import InferenceServiceType


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


# def test_bad_answer_not_cached():
#     from edsl import Survey

#     cache = Cache()
#     from edsl.language_models import LanguageModel

#     m = LanguageModel.example(test_model=True, canned_response="bad")
#     results = q.by(m).run(cache=cache)
#     results.select("answer.*").print()
#     assert cache.data == {}

#     m = LanguageModel.example(test_model=True, canned_response="1")
#     results = q.by(m).run(cache=cache)
#     results.select("answer.*").print()
#     assert cache.data != {}


def test_good_answer_cached():
    cache = Cache()

    m = LanguageModel.example(test_model=True, canned_response="1")
    results = q.by(m).run(cache=cache)
    results.select("answer.*").print()
    assert cache.data != {}

    # from edsl import Survey

    # m = create_language_model(
    #     exception=ValueError, fail_at_number=10, invalid_json=False
    # )()
    # i = InvigilatorTest(
    #     agent=a,
    #     model=m,
    #     question=q,
    #     scenario={},
    #     memory_plan=Mock(),
    #     current_answers={},
    #     survey=Survey.example(),
    #     cache=c,
    # )

    # response = i.answer_question()

    # assert c.data != {}
