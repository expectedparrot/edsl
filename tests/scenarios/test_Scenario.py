import unittest
from edsl.scenarios.Scenario import Scenario
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
from edsl.jobs.Jobs import Jobs
from edsl.agents.Agent import Agent
from edsl.surveys.Survey import Survey
from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo

import doctest
import edsl.scenarios


def test_doctests():
    doctest.testmod(edsl.scenarios)


class TestScenario(unittest.TestCase):
    def setUp(self):
        self.example_scenario = {"price": 100, "quantity": 2}

    def test_valid_case(self):
        try:
            a = Scenario(**self.example_scenario)
            self.assertTrue(True)
        except Exception as e:
            self.assertTrue(False, f"Exception occurred: {e}")

    def test_add(self):
        s1 = Scenario(**self.example_scenario)
        s2 = Scenario({"color": "red"})
        self.assertEqual(s1 + s2, {"price": 100, "quantity": 2, "color": "red"})
        self.assertIsInstance(s1 + s2, Scenario)

        s3 = Scenario({"color": None})
        self.assertEqual(s1 + s3, {"price": 100, "quantity": 2, "color": None})

    def test_to(self):
        s = Scenario({"food": "wood chips"})
        q = QuestionMultipleChoice(
            question_text="Do you enjoy the taste of {{food}}?",
            question_options=["Yes", "No"],
            question_name="food_preference",
        )
        self.assertIsInstance(s.to(q), Jobs)
        # checking print instead of Jobs because of uuids
        self.assertEqual(
            print(s.to(q)),
            print(
                Jobs(
                    survey=Survey(
                        questions=[
                            QuestionMultipleChoice(
                                question_text="Do you enjoy the taste of {{food}}?",
                                question_options=["Yes", "No"],
                                question_name="food_preference",
                            )
                        ],
                        name=None,
                    ),
                    agents=[Agent(traits={})],
                    models=[
                        LanguageModelOpenAIThreeFiveTurbo(model="", use_cache=True)
                    ],
                    scenarios=[{"food": "wood chips"}],
                )
            ),
        )

    def test_rename(self):
        s = Scenario({"food": "wood chips"})
        result = s.rename({"food": "food_preference"})
        self.assertEqual(result, {"food_preference": "wood chips"})

    def test_make_question(self):
        s = Scenario(
            {
                "question_name": "feelings",
                "question_text": "How are you feeling?",
                "question_options": [
                    "Very sad",
                    "Sad",
                    "Neutral",
                    "Happy",
                    "Very happy",
                ],
            }
        )
        q = s.make_question(QuestionMultipleChoice)
        # self.assertEqual(print(q), print("QuestionMultipleChoice"))
        self.assertIn("How are you feeling?", q.question_text)
        self.assertEqual(
            q.question_options, ["Very sad", "Sad", "Neutral", "Happy", "Very happy"]
        )
        # self.assertEqual(q.by(Agent(traits = {'feeling': 'Very sad'})).run().select("feelings"), ['Very sad'])

        base_survey = Survey(questions=[q])
        results = base_survey.run(debug=True)
        # self.assertIn(results[0]['result']['feelings'], range(len(q.question_options)))
        self.assertIn(
            q.question_options.index(results[0]["answer"]["feelings"]),
            range(len(q.question_options)),
        )
        self.assertIn(results[0]["answer"]["feelings"], q.question_options)


if __name__ == "__main__":
    unittest.main()
