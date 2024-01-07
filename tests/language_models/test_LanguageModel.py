import unittest
import os
from contextlib import redirect_stdout
from io import StringIO

from edsl.language_models.LanguageModel import LanguageModel
from edsl.data.crud import CRUDOperations


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

        import os
        from edsl.config import BASE_DIR
        from edsl.data.crud import Database

        self.database_file_path = os.path.join(BASE_DIR, "data/test_database.db")
        test_path = f"sqlite:///{self.database_file_path}"
        d = Database(config={"EDSL_DATABASE_PATH": test_path})
        self.crud = CRUDOperations(d)

    def tearDown(self) -> None:
        os.remove(self.database_file_path)

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

    def test_cache_write_and_read(self):
        #########################################
        ## Set up a database for testing purposes
        #########################################

        m = self.good_class(
            crud=self.crud,
            use_cache=True,
            model="fake model",
            parameters={"temperature": 0.5},
        )
        m.get_response(prompt="Hello world", system_prompt="You are a helpful agent")

        import sqlite3

        expected_response = {
            "id": 1,
            "model": "fake model",
            "parameters": "{'temperature': 0.5}",
            "system_prompt": "You are a helpful agent",
            "prompt": "Hello world",
            "output": '{"message": "{\\"answer\\": \\"Hello world\\"}"}',
        }

        connect = sqlite3.connect(self.database_file_path)
        cursor = connect.cursor()
        response_from_db = cursor.execute("SELECT * FROM responses").fetchall()[0]
        self.assertEqual(response_from_db, tuple(expected_response.values()))

        # call again with same prompt - should not write to db again
        m.get_response(prompt="Hello world", system_prompt="You are a helpful agent")
        new_responses = cursor.execute("SELECT * FROM responses").fetchall()
        num_responses = len(new_responses)
        self.assertEqual(num_responses, 1)
        self.assertEqual(new_responses[0], tuple(expected_response.values()))


if __name__ == "__main__":
    unittest.main()
