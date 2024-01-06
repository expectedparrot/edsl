import unittest
from contextlib import redirect_stdout
from io import StringIO
from edsl.results.Results import Results, create_example_results


class TestResults(unittest.TestCase):
    def setUp(self):
        self.example_results = create_example_results(debug=True)

    def test_instance(self):
        self.assertIsInstance(self.example_results, Results)

    def test_parse_column_exception(self):
        from edsl.results.Results import ColumnNotFoundError

        with self.assertRaises(ColumnNotFoundError):
            self.example_results._parse_column("poop")

    def test_bad_mutate(self):
        from edsl.results.Results import BadMutationstringError

        with self.assertRaises(BadMutationstringError):
            self.example_results.mutate('how_feeling_two -> how_feeling + "!!"')

    def test_invalid_name(self):
        from edsl.results.Results import InvalidNameError

        with self.assertRaises(InvalidNameError):
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
        csv = self.example_results.to_csv()
        self.assertIsInstance(csv, str)
        self.assertIn("how_feeling", csv)
        # Saves the file
        csv = self.example_results.to_csv(filename="test.csv")
        self.assertIsNone(csv)

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
            self.example_results.question_names, ["how_feeling", "elapsed"]
        )

    def test_filter(self):
        self.assertEqual(
            self.example_results.filter("how_feeling == 'Great'")
            .select("how_feeling")
            .first(),
            "Great",
        )

    def test_relevant_columns(self):
        # should return all - this is just checking one
        self.assertIn("how_feeling", self.example_results.relevant_columns())

    def test_answer_keys(self):
        self.assertIn("how_feeling", self.example_results.answer_keys.keys())

    def test_select(self):
        # results = self.example_results.select('how_feeling').first()
        self.assertIn(
            self.example_results.select("how_feeling").first(),
            ["Great", "Good", "OK", "Bad"],
        )

    def test_select_scenario(self):
        # breakpoint()
        # print(self.example_results.select('period'))
        self.assertIn(
            self.example_results.select("period").first(), ["morning", "afternoon"]
        )

    def flatten(self):
        self.assertEqual(
            self.example_results.select("how_feeling").flatten(),
            ["Great", "Great", "Good", "OK", "Bad", "Bad"],
        )

    def print(self):
        with StringIO() as buf, redirect_stdout(buf):
            self.example_results.print()
            output = buf.getvalue()
        self.assertIn("Great", output)
        self.assertIn("Bad", output)

    ## Test the fetch mixin
    def test_fetch_list(self):
        self.assertEqual(
            self.example_results.fetch_list("answer", "how_feeling"),
            ["Bad", "Bad", "Great", "Great"],
        )

    def test_fetch_answer_data(self):
        from edsl.report.InputOutputDataTypes import (
            CategoricalData,
            NumericalData,
            FreeTextData,
        )

        self.assertEqual(
            self.example_results._fetch_answer_data(
                "how_feeling", CategoricalData
            ).responses,
            ["Bad", "Bad", "Great", "Great"],
        )


if __name__ == "__main__":
    unittest.main()
