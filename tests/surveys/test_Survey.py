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
        # self.assertEqual(s._questions[0], s.first_question())
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

    def test_dag(self):
        survey = self.gen_survey()
        survey.add_rule(
            survey._questions[0], "like_school == 'no'", survey._questions[2]
        )
        survey.add_rule(
            survey._questions[1], "favorite_subject == 'math'", survey._questions[2]
        )
        survey.add_rule(
            survey._questions[1], "favorite_subject == 'science'", survey._questions[2]
        )
        survey.add_rule(
            survey._questions[1], "favorite_subject == 'english'", survey._questions[2]
        )
        survey.add_rule(
            survey._questions[1], "favorite_subject == 'history'", survey._questions[2]
        )
        survey.add_targeted_memory("favorite_subject", "like_school")
        # breakpoint()
        self.assertEqual(survey.dag(), {1: {0}, 2: {0, 1}})

    def test_eos_skip_logic(self):
        from edsl.questions import QuestionMultipleChoice, QuestionYesNo

        q1 = QuestionMultipleChoice(
            question_name="snow_shoveling",
            question_text="Do you enjoy snow shoveling?",
            question_options=["Yes", "No", "I do not know"],
        )

        q2 = QuestionYesNo(
            question_name="own_shovel", question_text="Do you own a shovel?"
        )

        from edsl import Agent

        d = Agent()

        def answer_question_directly(self, question, scenario):
            return "No"

        d.add_direct_question_answering_method(answer_question_directly)

        survey = q1.add_question(q2).add_stop_rule(
            "snow_shoveling", "snow_shoveling == 'No'"
        )
        dag = survey.dag()
        # breakpoint()

        jobs = survey.by(d)

        results = jobs.run()
        # with this skip logic, the second question should not be answered
        assert results[0].answer["own_shovel"] == None


if __name__ == "__main__":
    unittest.main()
    # s = TestSurvey().gen_survey()
    # TestSurvey().test_eos_skip_logic()
