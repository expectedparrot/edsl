import asyncio
import pytest
import unittest
from unittest.mock import patch
from typing import Any
from tempfile import NamedTemporaryFile

from edsl.exceptions.language_models import LanguageModelAttributeTypeError
from edsl.enums import InferenceServiceType
from edsl.language_models import LanguageModel


def create_temp_env_file(contents):
    temp_file = NamedTemporaryFile(delete=False)
    temp_file.write(contents.encode())
    temp_file.close()
    return temp_file.name


class TestLanguageModel(unittest.TestCase):
    def setUp(self):
        pass

    def test_tokens(self):
        import random

        random_tpm = random.randint(0, 100)
        random_tpm = random.randint(0, 100)
        m = LanguageModel.example()
        m.rpm = random_tpm
        m.tpm = random_tpm
        # m.set_rate_limits(tpm=random_tpm, rpm=random_tpm)
        self.assertEqual(m.tpm, random_tpm)
        self.assertEqual(m.rpm, random_tpm)

        m.rpm = 45
        self.assertEqual(m.rpm, 45)

    def test_execute_model_call(self):
        from edsl.data import Cache

        example_cache = Cache()

        m = LanguageModel.example(test_model=True, canned_response="Hello, world!")
        imco = m._get_intended_model_call_outcome(
            user_prompt="Hello world",
            system_prompt="You are a helpful agent",
            cache=example_cache,
        )
        self.assertEqual(imco.response["message"][0]["text"], "Hello, world!")
        self.assertEqual(imco.cached_response, None)

        self.assertEqual(len(example_cache), 1)

        self.assertEqual(
            list(example_cache.data.values())[0]["user_prompt"], "Hello world"
        )

        imco = m._get_intended_model_call_outcome(
            user_prompt="Hello world",
            system_prompt="You are a helpful agent",
            cache=example_cache,
        )

        self.assertEqual(len(example_cache), 1)

    # def test_get_response(self):
    #     from edsl.data.Cache import Cache

    #     m = self.good_class()
    #     response = m.get_response(
    #         user_prompt="Hello world",
    #         system_prompt="You are a helpful agent",
    #         cache=Cache(),
    #     )
    #     expected_response = {
    #         "answer": "Hello world",
    #         "usage": {},
    #     }
    #     for key, value in expected_response.items():
    #         self.assertEqual(response[key], value)

    # def test_cache_write_and_read(self):

    #     m = self.good_class(
    #         model="fake model", parameters={"temperature": 0.5}, iteration=1
    #     )
    #     from edsl.data.Cache import Cache

    #     cache = Cache(method="memory")

    #     m.get_response(
    #         user_prompt="Hello world",
    #         system_prompt="You are a helpful agent",
    #         cache=cache,
    #     )

    #     expected_response = {
    #         #            "id": 1,
    #         "model": "fake model",
    #         "parameters": {"temperature": 0.5},
    #         "system_prompt": "You are a helpful agent",
    #         "user_prompt": "Hello world",
    #         "output": '{"text": "Hello world"}',
    #         "iteration": 1,
    #     }

    #     from edsl.data.Cache import Cache

    #     outcome = list(cache.data.values())[0].to_dict()

    #     outcome.pop("timestamp")

    #     self.assertEqual(outcome, expected_response)

    #     # call again with same prompt - should not write to db again
    #     m.get_response(
    #         user_prompt="Hello world",
    #         system_prompt="You are a helpful agent",
    #         cache=cache,
    #     )

    #     self.assertEqual(len(cache.data.values()), 1)

    # def test_parser_exception(self):
    #     class TestLanguageModelGood(LanguageModel):
    #         _model_ = "test"
    #         _parameters_ = {"temperature": 0.5}
    #         _inference_service_ = InferenceServiceType.TEST.value

    #         async def async_execute_model_call(
    #             self, user_prompt: str, system_prompt: str
    #         ) -> dict[str, Any]:
    #             await asyncio.sleep(0.1)
    #             return {
    #                 "message": """{"answer": "Hello world", 'cached_response': False}"""
    #             }

    #         def parse_response(self, raw_response: dict[str, Any]) -> str:
    #             return raw_response["message"]

    #     m = TestLanguageModelGood()
    #     results = m.parse_response(raw_response={"message": "Hello world"})

    #     with pytest.raises(KeyError):
    #         m.parse_response(raw_response={"messPOOPage": "Hello world"})

    # def test_key_check(self):
    #     class TestLanguageModelGood(LanguageModel):
    #         _model_ = "test"
    #         _parameters_ = {"temperature": 0.5}
    #         _inference_service_ = InferenceServiceType.TEST.value

    #         async def async_execute_model_call(
    #             self, user_prompt: str, system_prompt: str
    #         ) -> dict[str, Any]:
    #             await asyncio.sleep(0.1)
    #             return {
    #                 "message": """{"answer": "Hello world", 'cached_response': False}"""
    #             }

    #         def parse_response(self, raw_response: dict[str, Any]) -> str:
    #             return raw_response["message"]

    #     m = TestLanguageModelGood()
    #     # all test models have a valid api key
    #     assert m.has_valid_api_key()


if __name__ == "__main__":
    unittest.main()
