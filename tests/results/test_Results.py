import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from edsl.results.exceptions import (
    ResultsBadMutationstringError,
    ResultsInvalidNameError,
    ResultsError,
)

from edsl.results import Results
from edsl.language_models import LanguageModel


class TestResults(unittest.TestCase):
    def setUp(self):
        self.example_results = Results.example()

    def test_instance(self):
        self.assertIsInstance(self.example_results, Results)

    def test_parse_column_exception(self):
        with self.assertRaises(Exception):
            self.example_results.select("poop")

    def test_bad_mutate(self):
        with self.assertRaises(ResultsBadMutationstringError):
            self.example_results.mutate('how_feeling_two -> how_feeling + "!!"')

    def test_invalid_name(self):
        with self.assertRaises(ResultsInvalidNameError):
            self.example_results.mutate('class = how_feeling + "!!"')

    def test_mutate(self):
        self.assertEqual(
            self.example_results.mutate("how_feeling_two = how_feeling + '!!'")
            .select("how_feeling_two")
            .first()
            .endswith("!!"),
            True,
        )

    def test_csv_export(self):
        # Just prints to screen
        csv = self.example_results.to_csv().text
        self.assertIsInstance(csv, str)
        self.assertIn("how_feeling", csv)
        # Saves the file
        csv = self.example_results.to_csv().write("test.csv")
        self.assertIsNone(csv)
        os.remove("test.csv")

    def test_to_dict(self):
        results_dict = self.example_results.to_dict()

        self.assertIsInstance(results_dict, dict)
        self.assertIn("data", results_dict)
        self.assertIn("survey", results_dict)
        self.assertIsInstance(results_dict["data"], list)
        self.assertIsInstance(results_dict["survey"], dict)

    def test_from_dict(self):
        results_dict = self.example_results.to_dict()
        results_obj = Results.from_dict(results_dict)

        self.assertIsInstance(results_obj, Results)
        self.assertEqual(print(self.example_results), print(results_obj))

    def test_question_names(self):
        self.assertIsInstance(self.example_results.question_names, list)
        self.assertEqual(
            self.example_results.question_names,
            ["how_feeling", "how_feeling_yesterday"],
        )

    def test_filter(self):
        first_answer = self.example_results.data[0].answer["how_feeling"]
        self.assertEqual(
            self.example_results.filter(f"how_feeling == '{first_answer}'")
            .select("how_feeling")
            .first(),
            first_answer,
        )

    def test_relevant_columns(self):
        self.assertIn("answer.how_feeling", self.example_results.relevant_columns())

    def test_answer_keys(self):
        self.assertIn("how_feeling", self.example_results.answer_keys.keys())

    def test_select(self):
        first_answer = self.example_results.data[0].answer["how_feeling"]
        self.assertIn(
            self.example_results.select("how_feeling").first(),
            first_answer,
        )

    def test_select_scenario(self):
        self.assertIn(
            self.example_results.select("period").first(), ["morning", "afternoon"]
        )

    def flatten(self):
        self.assertEqual(
            self.example_results.select("how_feeling").flatten(),
            ["Great", "Great", "Good", "OK", "Bad", "Bad"],
        )

    def test_print(self):
        with StringIO() as buf, redirect_stdout(buf):
            self.example_results.select("how_feeling").print()
            output = buf.getvalue()
        # raise Exception("Just to see if working")
        # breakpoint()
        # self.assertIn("Great", output)
        # self.assertIn("Terrible", output)

    def test_fetch_list(self):
        self.assertEqual(
            self.example_results._fetch_list("answer", "how_feeling"),
            [result.answer.get("how_feeling") for result in self.example_results.data],
        )

    def test_shuffle(self):
        # Just check that no exceptions are thrown
        shuffled = self.example_results.shuffle()
        shuffled2 = self.example_results.select("answer.*").shuffle()

    def test_cache_control(self):
        d = self.example_results.to_dict(include_cache=True)
        self.assertIn("cache", d)

        d = self.example_results.to_dict(include_cache=False)
        self.assertNotIn("cache", d)

    def test_cache_history(self):

        self.assertEqual(self.example_results.task_history.has_exceptions, False)
        self.assertNotIn("task_history", self.example_results.to_dict())

        self.assertIn(
            "task_history", self.example_results.to_dict(include_task_history=True)
        )

        from edsl.questions import QuestionFreeText

        q = QuestionFreeText.example()

        m = LanguageModel.example(test_model=True, throw_exception=True)
        results = q.by(m).run(
            n=2,
            disable_remote_inference=True,
            cache=False,
            disable_remote_cache=True,
            print_exceptions=True,
        )
        self.assertIn("task_history", results.to_dict())
        new_results = Results.from_dict(results.to_dict())
        self.assertEqual(new_results.task_history.has_exceptions, True)

    def test_sample(self):
        shuffled = self.example_results.sample(n=1)
        assert len(shuffled) == 1
        shuffled2 = self.example_results.select("answer.*").sample(n=1)
        assert len(shuffled2) == 1

    def test_add(self):
        # just check that no exceptions are thrown
        r1 = self.example_results
        r2 = self.example_results
        r3 = r1 + r2
        assert len(r3) == len(r1) + len(r2)

    def test_to_csv(self):
        import tempfile
        import csv

        with tempfile.TemporaryDirectory() as tmpdirname:
            self.example_results.to_csv(tmpdirname + "/test.csv")

            with open(tmpdirname + "/test.csv") as f:
                reader = csv.reader(f)
                rows = list(reader)
                assert len(rows) == len(self.example_results) + 1

    def test_to_disk_and_from_disk(self):
        """Test saving and loading Results to/from disk."""
        import tempfile
        import os
        import zipfile
        import json

        # Create a temporary file path
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            filepath = tmp.name

        try:
            # Debug original data
            print(f"Original data length: {len(self.example_results)}")
            print(f"Original data type: {type(self.example_results.data)}")
            if hasattr(self.example_results.data, 'db_path'):
                print(f"Original db_path: {self.example_results.data.db_path}")

            # Save the example results to disk
            self.example_results.to_disk(filepath)

            # Verify the file was created
            self.assertTrue(os.path.exists(filepath))

            # Debug zip contents
            with zipfile.ZipFile(filepath, 'r') as zipf:
                print("Zip contents:", zipf.namelist())
                if 'metadata.json' in zipf.namelist():
                    metadata = json.loads(zipf.read('metadata.json').decode())
                    print("Metadata:", json.dumps(metadata, indent=2))

            # Load the results back
            loaded_results = Results.from_disk(filepath)

            # Debug loaded data
            print(f"Loaded data length: {len(loaded_results)}")
            print(f"Loaded data type: {type(loaded_results.data)}")
            if hasattr(loaded_results.data, 'db_path'):
                print(f"Loaded db_path: {loaded_results.data.db_path}")

            # Verify the loaded results match the original
            self.assertEqual(len(loaded_results), len(self.example_results))
            self.assertEqual(loaded_results.survey, self.example_results.survey)
            self.assertEqual(loaded_results.created_columns, self.example_results.created_columns)
            self.assertEqual(loaded_results.completed, self.example_results.completed)

            # Compare the first result from both
            self.assertEqual(loaded_results[0].to_dict(), self.example_results[0].to_dict())

        finally:
            # Clean up
            if os.path.exists(filepath):
                os.remove(filepath)

    def test_to_disk_invalid_path(self):
        """Test error handling for invalid file path."""
        with self.assertRaises(ResultsError):
            self.example_results.to_disk("/nonexistent/path/results.zip")

    def test_from_disk_invalid_path(self):
        """Test error handling for loading from invalid file path."""
        with self.assertRaises(ResultsError):
            Results.from_disk("/nonexistent/path/results.zip")

    def test_from_disk_invalid_format(self):
        """Test error handling for loading from invalid file format."""
        import tempfile
        import os
        
        # Create a temporary file with invalid content
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            filepath = tmp.name
            tmp.write(b'invalid content')
        
        try:
            with self.assertRaises(ResultsError):
                Results.from_disk(filepath)
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)


if __name__ == "__main__":
    unittest.main()
    TestResults().test_print_latest()
