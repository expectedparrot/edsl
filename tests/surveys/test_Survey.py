import unittest
from edsl.surveys.Survey import Survey
from edsl.questions import QuestionMultipleChoice


class TestSurvey(unittest.TestCase):
    def gen_survey(self):
        q1 = QuestionMultipleChoice(
            question_text="Do you like school?",
            question_options=["yes", "no"],
            question_name="like_school",
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

        s = Survey(questions=[q1, q2, q3])
        return s

    def test_default_sequence(self):
        s = self.gen_survey()
        self.assertEqual(s._questions[0], s.first_question())
        self.assertEqual(s._questions[1], s.next_question("like_school", {}))
        self.assertEqual(s._questions[2], s.next_question("favorite_subject", {}))

    def test_simple_skip(self):
        s = self.gen_survey()
        q1, q2, q3 = s._questions
        s.add_rule(q1, "like_school == 'no'", q3)
        self.assertEqual(q3, s.next_question("like_school", {"like_school": "no"}))

    def test_add_memory(self):
        survey = self.gen_survey()
        # breakpoint()
        survey.add_targeted_memory("favorite_subject", "like_school")

    def test_add_memory_wrong_order(self):
        survey = self.gen_survey()
        with self.assertRaises(ValueError):
            survey.add_targeted_memory("like_school", "favorite_subject")

    def test_add_memory_invalid_question(self):
        survey = self.gen_survey()
        with self.assertRaises(ValueError):
            survey.add_targeted_memory("like_school", "invalid_question")

    def test_add_memory_duplicate_question(self):
        survey = self.gen_survey()
        survey.add_targeted_memory("favorite_subject", "like_school")
        with self.assertRaises(ValueError):
            survey.add_targeted_memory("favorite_subject", "like_school")

    def test_full_memory(self):
        from edsl.surveys.Memory import Memory

        survey = self.gen_survey()
        survey.set_full_memory_mode()
        self.assertEqual(
            survey.memory_plan.data,
            {
                "favorite_subject": Memory(prior_questions=["like_school"]),
                "manual": Memory(prior_questions=["like_school", "favorite_subject"]),
            },
        )


if __name__ == "__main__":
    unittest.main()

    s = TestSurvey().gen_survey()
