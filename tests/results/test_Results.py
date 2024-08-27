import os
import unittest
from contextlib import redirect_stdout
from io import StringIO
from edsl.exceptions import (
    ResultsBadMutationstringError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
)

# from edsl.report.InputOutputDataTypes import CategoricalData
from edsl.results import Results


class TestResults(unittest.TestCase):
    def setUp(self):
        self.example_results = Results.example(debug=False)

    def test_instance(self):
        self.assertIsInstance(self.example_results, Results)

    def test_parse_column_exception(self):
        with self.assertRaises(ResultsColumnNotFoundError):
            self.example_results._parse_column("poop")

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
        csv = self.example_results.to_csv()
        self.assertIsInstance(csv, str)
        self.assertIn("how_feeling", csv)
        # Saves the file
        csv = self.example_results.to_csv(filename="test.csv")
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

    def test_sample(self):
        shuffled = self.example_results.sample(n=1)
        assert len(shuffled) == 1
        shuffled2 = self.example_results.select("answer.*").sample(n=1)
        assert len(shuffled2) == 1
        # with self.assertRaises(Exception):
        #    shuffled3 = self.example_results.sample(frac = 1.1, with_replacement = False)

    # def test_fetch_answer_data(self):
    #     self.assertEqual(
    #         self.example_results._fetch_answer_data(
    #             "how_feeling", CategoricalData
    #         ).responses,
    #         [result.answer.get("how_feeling") for result in self.example_results.data],
    #     )

    def test_print_long(self):
        from edsl.questions import QuestionLinearScale, QuestionMultipleChoice

        from edsl import Agent

        def answer_question_directly(self, question, scenario):
            return "Never"

        from edsl.data.Cache import Cache

        cache = Cache()
        agent = Agent()
        agent.add_direct_question_answering_method(answer_question_directly)

        q = QuestionMultipleChoice(
            question_name="exercise",
            question_text="How often do you typically exercise each week?",
            question_options=["Never", "Sometimes", "Often"],
        )
        results = q.by(agent).run(cache=cache)

        with StringIO() as buf, redirect_stdout(buf):
            results.select("answer.*").print()
            output = buf.getvalue()
        self.assertIn("Never", output)

        with StringIO() as buf, redirect_stdout(buf):
            results.select("answer.*").print_long()
            output = buf.getvalue()
        self.assertIn("Never", output)

    def test_add(self):
        # just check that no exceptions are thrown
        r1 = self.example_results
        r2 = self.example_results
        r3 = r1 + r2
        assert len(r3) == len(r1) + len(r2)

    # def test_stefan(self):
    #     from edsl.questions import QuestionBase
    #     from edsl.results import Results
    #     from edsl.surveys import Survey
    #     results = Survey.example().run()

    #     res_dect = results.to_dict()
    #     res = Results.from_dict(res_dect)


if __name__ == "__main__":
    unittest.main()
    TestResults().test_print_latest()
