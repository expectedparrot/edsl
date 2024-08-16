import asyncio
import pytest
import unittest
from unittest.mock import patch
from typing import Any
from tempfile import NamedTemporaryFile

from edsl.exceptions.language_models import LanguageModelAttributeTypeError
from edsl.enums import InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel


def create_temp_env_file(contents):
    temp_file = NamedTemporaryFile(delete=False)
    temp_file.write(contents.encode())
    temp_file.close()
    return temp_file.name


class TestLanguageModel(unittest.TestCase):
    def setUp(self):
        class TestLanguageModelBad(LanguageModel):
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value
            pass

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {
                    "message": """{"answer": "Hello world", 'cached_response': False, 'usage': {}}"""
                }

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        self.bad_class = TestLanguageModelBad

        class TestLanguageModelGood(LanguageModel):
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {"message": """{"answer": "Hello world"}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        self.good_class = TestLanguageModelGood

    def test_instantiation(self):
        class Mixin:
            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {"message": """{"answer": "Hello world"}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        # with pytest.raises(LanguageModelAttributeTypeError):

        #     class TestLanguageModelGood(Mixin, LanguageModel):
        #         _model_ = "fake model"
        #         _parameters_ = {"temperature": 0.5}
        #         _inference_service_ = InferenceServiceType.TEST.value

    def test_params_passed_to_parent(self):
        pass

    def test_missing_class_attributes(self):
        with self.assertRaises(Exception):
            # This should fail because the class is missing the _parameters_ attribute
            class TestLanguageModelGood(LanguageModel):
                _model_ = "fake model"

                async def async_execute_model_call(self, user_prompt, system_prompt):
                    await asyncio.sleep(0.1)
                    return {"message": """{"answer": "Hello world"}"""}

                def parse_response(self, raw_response: dict[str, Any]):
                    return raw_response["message"]

            TestLanguageModelGood()

    def test_execute_model_call(self):
        from edsl.data.Cache import Cache

        m = self.good_class()
        response, cached_response, cache_key = m.get_raw_response(
            user_prompt="Hello world",
            system_prompt="You are a helpful agent",
            cache=Cache(),
        )
        print(response)
        self.assertEqual(response["message"], """{"answer": "Hello world"}""")
        self.assertEqual(cached_response, False)

    def test_get_response(self):
        from edsl.data.Cache import Cache

        m = self.good_class()
        response = m.get_response(
            user_prompt="Hello world",
            system_prompt="You are a helpful agent",
            cache=Cache(),
        )
        expected_response = {
            "answer": "Hello world",
            "usage": {},
        }
        for key, value in expected_response.items():
            self.assertEqual(response[key], value)

    def test_cache_write_and_read(self):

        m = self.good_class(
            model="fake model", parameters={"temperature": 0.5}, iteration=1
        )
        from edsl.data.Cache import Cache

        cache = Cache(method="memory")

        m.get_response(
            user_prompt="Hello world",
            system_prompt="You are a helpful agent",
            cache=cache,
        )

        expected_response = {
            #            "id": 1,
            "model": "fake model",
            "parameters": {"temperature": 0.5},
            "system_prompt": "You are a helpful agent",
            "user_prompt": "Hello world",
            "output": '{"message": "{\\"answer\\": \\"Hello world\\"}"}',
            "iteration": 1,
        }

        from edsl.data.Cache import Cache

        outcome = list(cache.data.values())[0].to_dict()

        outcome.pop("timestamp")

        self.assertEqual(outcome, expected_response)

        # call again with same prompt - should not write to db again
        m.get_response(
            user_prompt="Hello world",
            system_prompt="You are a helpful agent",
            cache=cache,
        )

        self.assertEqual(len(cache.data.values()), 1)

    def test_parser_exception(self):
        class TestLanguageModelGood(LanguageModel):
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {
                    "message": """{"answer": "Hello world", 'cached_response': False}"""
                }

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        m = TestLanguageModelGood()
        results = m.parse_response(raw_response={"message": "Hello world"})

        with pytest.raises(KeyError):
            m.parse_response(raw_response={"messPOOPage": "Hello world"})

    def test_key_check(self):
        class TestLanguageModelGood(LanguageModel):
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {
                    "message": """{"answer": "Hello world", 'cached_response': False}"""
                }

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        m = TestLanguageModelGood()
        # all test models have a valid api key
        assert m.has_valid_api_key()


if __name__ == "__main__":
    unittest.main()
