import unittest
from contextlib import redirect_stdout
from io import StringIO

from edsl.language_models.LanguageModel import LanguageModel


class TestLanguageModel(unittest.TestCase):
    def setUp(self):
        class TestLanguageModelBad(LanguageModel):
            pass

        self.bad_class = TestLanguageModelBad

        class TestLanguageModelGood(LanguageModel):
            use_cache = False

            def execute_model_call(self, prompt, system_prompt):
                return {"message": """{"answer": "Hello world"}"""}

            def parse_response(self, raw_response):
                return raw_response["message"]

        self.good_class = TestLanguageModelGood

    def test_abstract_methods_missing(self):
        with self.assertRaises(TypeError):
            m = self.bad_class()

    def test_execute_model_call(self):
        m = self.good_class()
        response = m._get_raw_response(
            prompt="Hello world", system_prompt="You are a helpful agent"
        )
        print(response)
        self.assertEqual(response["message"], """{"answer": "Hello world"}""")
        self.assertEqual(response["cached_response"], False)

    def test_get_response(self):
        m = self.good_class()
        response = m.get_response(
            prompt="Hello world", system_prompt="You are a helpful agent"
        )
        self.assertEqual(response, {"answer": "Hello world"})


if __name__ == "__main__":
    unittest.main()
