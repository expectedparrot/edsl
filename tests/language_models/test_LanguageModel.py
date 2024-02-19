import asyncio
import pytest
import unittest
from typing import Any
from edsl.data import CRUD
from edsl.exceptions.language_models import LanguageModelAttributeTypeError
from edsl.enums import LanguageModelType, InferenceServiceType
from edsl.language_models.LanguageModel import LanguageModel


class TestLanguageModel(unittest.TestCase):
    def setUp(self):
        class TestLanguageModelBad(LanguageModel):
            _model_ = LanguageModelType.TEST.value
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value
            pass

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {"message": """{"answer": "Hello world", 'cached_response': False, 'usage': {}}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        self.bad_class = TestLanguageModelBad

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

        self.good_class = TestLanguageModelGood
        self.crud = CRUD

    def test_instantiation(self):
        class Mixin:
            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {"message": """{"answer": "Hello world"}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        with pytest.raises(LanguageModelAttributeTypeError):

            class TestLanguageModelGood(Mixin, LanguageModel):
                _model_ = "fake model"
                _parameters_ = {"temperature": 0.5}
                _inference_service_ = InferenceServiceType.TEST.value

    def test_params_passed_to_parent(self):
        m = self.good_class(use_cache=True)
        self.assertEqual(m.use_cache, True)

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
        m = self.good_class()
        response = m.get_raw_response(
            user_prompt="Hello world", system_prompt="You are a helpful agent"
        )
        print(response)
        self.assertEqual(response["message"], """{"answer": "Hello world"}""")
        self.assertEqual(response["cached_response"], False)

    def test_get_response(self):
        m = self.good_class()
        response = m.get_response(
            user_prompt="Hello world", system_prompt="You are a helpful agent"
        )
        self.assertEqual(response, {"answer": "Hello world", 'cached_response': False, 'usage': {}})

    def test_cache_write_and_read(self):
        self.crud.clear_LLMOutputData()
        m = self.good_class(
            crud=self.crud,
            use_cache=True,
            model="fake model",
            parameters={"temperature": 0.5},
        )
        m.get_response(
            user_prompt="Hello world", system_prompt="You are a helpful agent"
        )

        expected_response = {
            "id": 1,
            "model": "fake model",
            "parameters": "{'temperature': 0.5}",
            "system_prompt": "You are a helpful agent",
            "prompt": "Hello world",
            "output": '{"message": "{\\"answer\\": \\"Hello world\\"}"}',
        }

        self.assertEqual(self.crud.get_all_LLMOutputData(), [expected_response])

        # call again with same prompt - should not write to db again
        m.get_response(
            user_prompt="Hello world", system_prompt="You are a helpful agent"
        )
        responses = self.crud.get_all_LLMOutputData()
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses, [expected_response])

    def test_parser_exception(self):
        class TestLanguageModelGood(LanguageModel):
            _model_ = LanguageModelType.TEST.value
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                return {"message": """{"answer": "Hello world", 'cached_response': False}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        m = TestLanguageModelGood()
        results = m.parse_response(raw_response={"message": "Hello world"})

        with pytest.raises(KeyError):
            m.parse_response(raw_response={"messPOOPage": "Hello world"})


if __name__ == "__main__":
    unittest.main()
