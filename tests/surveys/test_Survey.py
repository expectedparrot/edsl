import pytest
import unittest
from edsl.surveys import Survey
from edsl.questions import QuestionMultipleChoice
from edsl.agents import Agent


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
        self.assertEqual(q3, s.next_question("like_school", {"like_school.answer": "no"}))

    def test_skip_question(self):
        survey = self.gen_survey()
        q1, q2, q3 = survey._questions
        # "like school", "favorite subject", "manual"
        survey = survey.add_skip_rule(q2, "True")
        next_question = survey.next_question("like_school", {})
        assert next_question == q3

    def test_add_memory(self):
        survey = self.gen_survey()
        # breakpoint()
        survey.add_targeted_memory("favorite_subject", "like_school")

    def test_add_memory_wrong_order(self):
        survey = self.gen_survey()
        with self.assertRaises(Exception):
            survey.add_targeted_memory("like_school", "favorite_subject")

    def test_add_memory_invalid_question(self):
        survey = self.gen_survey()
        with self.assertRaises(Exception):
            survey.add_targeted_memory("like_school", "invalid_question")

    def test_add_memory_duplicate_question(self):
        survey = self.gen_survey()
        survey.add_targeted_memory("favorite_subject", "like_school")
        with self.assertRaises(Exception):
            survey.add_targeted_memory("favorite_subject", "like_school")

    def test_full_memory(self):
        from edsl.surveys.memory import Memory

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

        d = Agent()

        def answer_question_directly(self, question, scenario):
            return "No"

        d.add_direct_question_answering_method(answer_question_directly)

        survey = q1.add_question(q2).add_stop_rule(
            "snow_shoveling", "snow_shoveling.answer == 'No'"
        )
        dag = survey.dag()
        # breakpoint()

        jobs = survey.by(d)

        from edsl.data import Cache

        results = jobs.run(cache=Cache())
        # with this skip logic, the second question should not be answered
        assert results[0].answer["own_shovel"] == None

    def test_serialiation_with_memory(self):
        from edsl.questions import QuestionYesNo, QuestionLinearScale
        from edsl.surveys import Survey

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
        # assert (
        #     survey.code()
        #     == """from edsl.surveys import Survey\nfrom edsl import Question\n\nlike_school = Question(\n    "multiple_choice",\n    question_name=\"\"\"like_school\"\"\",\n    question_text=\"\"\"Do you like school?\"\"\",\n    question_options=["yes", "no"],\n)\nfavorite_subject = Question(\n    "multiple_choice",\n    question_name=\"\"\"favorite_subject\"\"\",\n    question_text=\"\"\"What is your favorite subject?\"\"\",\n    question_options=["math", "science", "english", "history"],\n)\nmanual = Question(\n    "multiple_choice",\n    question_name=\"\"\"manual\"\"\",\n    question_text=\"\"\"Do you like working with your hands?\"\"\",\n    question_options=["yes", "no"],\n)\nsurvey = Survey(questions=[like_school, favorite_subject, manual])\n"""
        # )
        # # for now, just make sure it doesn't crash
        # _ = survey.docx()

    @pytest.mark.linux_only
    def test_visualization_for_flow(self):
        s = self.gen_survey()
        # make sure doesn't crash
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            s.show_flow(filename=f.name)

    def test_insertion(self):
        survey = self.gen_survey()
        q1, q2, q3 = survey._questions
        survey.add_rule(q1, "like_school == 'no'", q3)

        original_length = len(survey._questions)
        from edsl.questions import QuestionFreeText

        new_q = QuestionFreeText(
            question_text="Where are you from?", question_name="hometown"
        )
        # insert a new question at the begining
        insertion_index = 1
        survey.add_question(new_q, index=insertion_index)
        assert len(survey._questions) == original_length + 1
        assert survey._questions[insertion_index] == new_q

        path = survey.gen_path_through_survey()
        survey._questions[0] = next(path)

    def test_deletion(self):
        survey = self.gen_survey()
        q1, q2, q3 = survey._questions
        survey.add_rule(q1, "like_school == 'no'", q3)

        original_length = len(survey._questions)

        # Remember the question to be deleted
        question_to_delete = survey._questions[1]  # q2

        # Delete the second question
        deletion_index = 1
        new_survey = survey.delete_question(deletion_index)

        # Assert that the new survey is returned
        assert isinstance(new_survey, type(survey))

        # Check that the survey length has decreased
        assert len(new_survey._questions) == original_length - 1

        # Check that the deleted question is no longer in the survey
        assert question_to_delete not in new_survey._questions

        # Check that the remaining questions are in the correct order
        assert new_survey._questions == [q1, q3]

        # # Check that the rule has been updated (q3 should now be at index 1)
        # assert new_survey._rules == {0: {("like_school == 'no'", 1)}}

        # Check that the memory plan has been updated
        assert (
            question_to_delete.question_name
            not in new_survey.memory_plan.survey_question_names
        )
        assert (
            question_to_delete.question_text
            not in new_survey.memory_plan.question_texts
        )

        # If the deleted question was part of any memory, check that it's been removed
        for memory in new_survey.memory_plan.values():
            assert question_to_delete.question_name not in memory.prior_questions

        # Generate a new path through the survey to ensure it still works
        path = new_survey.gen_path_through_survey()
        first_question = next(path)
        assert first_question == q1

    def test_simulations(self):
        for index in range(10):
            print("Running simulation:" + str(index))
            s = Survey.random_survey()
            s.simulate()

    def test_draw(self):
        from edsl import Survey, QuestionMultipleChoice, Agent, Model

        q = QuestionMultipleChoice(
            question_text="What is your favorite color?",
            question_options=["Red", "Blue", "Green"],
            question_name="color",
        )
        a = Agent(
            traits={
                "persona": "You are a lazy survey-taker that always selects the first option."
            }
        )
        s = Survey([q], questions_to_randomize=["color"])
        m = Model("test", canned_response="Red")
        jobs = s.by(a).by(m)
        results = jobs.run(
            n=10, disable_remote_inference=True, disable_remote_cache=True
        )
        color_list = results.select("question_options.color")

        assert (
            "".join(["".join(l) for l in color_list.to_list()])
            == "BlueGreenRedBlueRedGreenBlueRedGreenBlueGreenRedGreenRedBlueGreenBlueRedGreenBlueRedRedBlueGreenBlueRedGreenGreenBlueRed"
        )


if __name__ == "__main__":
    unittest.main()
    # s = TestSurvey().gen_survey()
    # TestSurvey().test_eos_skip_logic()
