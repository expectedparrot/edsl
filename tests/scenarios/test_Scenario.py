import unittest
from edsl.scenarios.Scenario import Scenario
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.jobs.Jobs import Jobs
from edsl.agents.Agent import Agent
from edsl.surveys.Survey import Survey

import doctest
import edsl.scenarios


def test_doctests():
    doctest.testmod(edsl.scenarios)


class TestScenario(unittest.TestCase):
    def setUp(self):
        self.example_scenario = {"price": 100, "quantity": 2}

    def test_valid_case(self):
        try:
            a = Scenario(self.example_scenario)
            self.assertTrue(True)
        except Exception as e:
            self.assertTrue(False, f"Exception occurred: {e}")

    def test_add(self):
        s1 = Scenario(self.example_scenario)
        s2 = Scenario({"color": "red"})
        self.assertEqual(
            s1 + s2, Scenario({"price": 100, "quantity": 2, "color": "red"})
        )
        self.assertIsInstance(s1 + s2, Scenario)

        s3 = Scenario({"color": None})
        self.assertEqual(
            s1 + s3, Scenario({"price": 100, "quantity": 2, "color": None})
        )

    def test_rename(self):
        s = Scenario({"food": "wood chips"})
        result = s.rename({"food": "food_preference"})
        self.assertEqual(result, Scenario({"food_preference": "wood chips"}))


if __name__ == "__main__":
    unittest.main()
