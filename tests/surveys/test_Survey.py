import unittest
from edsl.surveys.Survey import Survey
from edsl.questions import QuestionMultipleChoice


class TestSurvey(unittest.TestCase):
    def gen_survey(self):
        q1 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="like_schoool",
        )
        q2 = QuestionMultipleChoice(
            question_text="What is your favorite subject?",
            question_options=["math", "science", "english", "history"],
            question_name="favorite_subject",
        )
        q3 = QuestionMultipleChoice(
            question_text="Do you like working with your hands?",
            question_options=["yes", "no"],
            question_name="manual",
        )

        s = Survey(questions=[q1, q2, q3], question_names=["q1", "q2", "q3"])
        return s

    def test_default_sequence(self):
        s = self.gen_survey()
        q1, q2, q3 = s._questions
        self.assertEqual(q1, s.next_question())
        self.assertEqual(q2, s.next_question("q1", {}))
        self.assertEqual(q3, s.next_question("q2", {}))

    def test_simple_skip(self):
        s = self.gen_survey()
        q1, q2, q3 = s._questions
        s.add_rule(q1, "q1 == 'no'", q3)
        self.assertEqual(q3, s.next_question("q1", {"q1": "no"}))


if __name__ == "__main__":
    unittest.main()
