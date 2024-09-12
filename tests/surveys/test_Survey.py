import pytest
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

    def test_skip_question(self):
        survey = self.gen_survey()
        q1, q2, q3 = survey._questions
        # "like school", "favorite subject", "manual"
        survey = survey.add_skip_rule(q2, "True")
        next_question = survey.next_question("like_school", {})
        assert next_question == q3
        #breakpoint()
        # self.assertEqual(q3, s.next_question("like_school", {"like_school": "no"}))
        # s = self.gen_survey()
        # with self.assertRaises(ValueError):
        #     # can't skip the first question in the survey
        #     s.add_skip_rule(q1, "True")

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

        from edsl.data.Cache import Cache

        results = jobs.run(cache=Cache())
        # with this skip logic, the second question should not be answered
        assert results[0].answer["own_shovel"] == None

    def test_serialiation_with_memory(self):
        from edsl.questions import QuestionYesNo, QuestionLinearScale
        from edsl import Survey

        q1 = QuestionYesNo(
            question_name="enjoy",
            question_text="Do you enjoy clothes shopping?",
        )
        q2 = QuestionLinearScale(
            question_name="enjoy_scale",
            question_text="On a scale of 0-10, how much do you typically enjoy clothes shopping?",
            question_options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            option_labels={0: "Not at all", 10: "Very much"},
        )
        survey = Survey(questions=[q1, q2])
        survey.add_targeted_memory(q2, q1)
        d = survey.to_dict()
        newsurvey = Survey.from_dict(d)
        try:
            assert survey == newsurvey
        except AssertionError:
            survey.diff(newsurvey)
            raise AssertionError

    def test_export_code(self):
        survey = self.gen_survey()
        # breakpoint()
        assert (
            survey.code()
            == """from edsl.surveys.Survey import Survey\nfrom edsl import Question\n\nlike_school = Question(\n    "multiple_choice",\n    question_name=\"\"\"like_school\"\"\",\n    question_text=\"\"\"Do you like school?\"\"\",\n    question_options=["yes", "no"],\n)\nfavorite_subject = Question(\n    "multiple_choice",\n    question_name=\"\"\"favorite_subject\"\"\",\n    question_text=\"\"\"What is your favorite subject?\"\"\",\n    question_options=["math", "science", "english", "history"],\n)\nmanual = Question(\n    "multiple_choice",\n    question_name=\"\"\"manual\"\"\",\n    question_text=\"\"\"Do you like working with your hands?\"\"\",\n    question_options=["yes", "no"],\n)\nsurvey = Survey(questions=[like_school, favorite_subject, manual])\n"""
        )
        # for now, just make sure it doesn't crash
        _ = survey.docx()

    @pytest.mark.linux_only
    def test_visualization_for_flow(self):
        s = self.gen_survey()
        # make sure doesn't crash
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            s.show_flow(filename=f.name)


if __name__ == "__main__":
    unittest.main()
    # s = TestSurvey().gen_survey()
    # TestSurvey().test_eos_skip_logic()
