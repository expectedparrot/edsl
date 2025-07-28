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

        from edsl.caching import Cache

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

        # No need to sort manually as results are now ordered by iteration automatically
        color_list = results.select("question_options.color").to_list()


        assert (
            "".join(["".join(l) for l in color_list])
            == "BlueGreenRedBlueRedGreenBlueRedGreenBlueGreenRedGreenRedBlueGreenBlueRedGreenBlueRedRedBlueGreenBlueRedGreenGreenBlueRed"
        )

    def test_rename_question_basic(self):
        """Test basic question renaming functionality."""
        s = self.gen_survey()
        original_names = s.question_names
        
        # Rename the first question
        s_renamed = s.rename_question("like_school", "school_preference")
        
        # Check that the question name was updated
        self.assertEqual(s_renamed.question_names[0], "school_preference")
        self.assertEqual(s_renamed.question_names[1:], original_names[1:])
        
        # Check that the renamed question can be retrieved
        renamed_question = s_renamed.get("school_preference")
        self.assertEqual(renamed_question.question_name, "school_preference")
        self.assertEqual(renamed_question.question_text, "Do you like school?")
        
        # Check that the old name is no longer available
        with self.assertRaises(Exception):
            s_renamed.get("like_school")

    def test_rename_question_with_rules(self):
        """Test that rules are updated when questions are renamed."""
        from edsl.questions import QuestionFreeText
        
        q1 = QuestionFreeText(question_text="What is your name?", question_name="name")
        q2 = QuestionFreeText(question_text="What is your age?", question_name="age")
        q3 = QuestionFreeText(question_text="Any comments?", question_name="comments")
        
        s = Survey([q1, q2, q3])
        
        # Add rule with new format (Jinja2)
        s = s.add_rule("name", "{{ name.answer }} == 'John'", "comments")
        
        # Verify rule before rename
        rule_expressions_before = [rule.expression for rule in s.rule_collection if "name" in rule.expression]
        self.assertTrue(any("{{ name.answer }}" in expr for expr in rule_expressions_before))
        
        # Rename the question
        s_renamed = s.rename_question("name", "full_name")
        
        # Verify rule after rename
        rule_expressions_after = [rule.expression for rule in s_renamed.rule_collection if "full_name" in rule.expression]
        self.assertTrue(any("{{ full_name.answer }}" in expr for expr in rule_expressions_after))
        
        # Verify old name is gone from rules
        rule_expressions_old = [rule.expression for rule in s_renamed.rule_collection if "{{ name.answer }}" in rule.expression]
        self.assertEqual(len(rule_expressions_old), 0)

    def test_rename_question_with_piping(self):
        """Test that piping references are updated when questions are renamed."""
        from edsl.questions import QuestionFreeText, QuestionMultipleChoice
        
        q1 = QuestionFreeText(question_text="What is your name?", question_name="user_name")
        q2 = QuestionMultipleChoice(
            question_text="Hello {{ user_name.answer }}, do you like surveys?",
            question_options=["yes", "no"],
            question_name="likes_surveys"
        )
        q3 = QuestionFreeText(
            question_text="{{ user_name.answer }}, since you said {{ likes_surveys.answer }}, please explain.",
            question_name="explanation"
        )
        
        s = Survey([q1, q2, q3])
        
        # Verify piping before rename
        self.assertIn("{{ user_name.answer }}", s.get("likes_surveys").question_text)
        self.assertIn("{{ user_name.answer }}", s.get("explanation").question_text)
        
        # Rename the question
        s_renamed = s.rename_question("user_name", "participant_name")
        
        # Verify piping after rename
        self.assertIn("{{ participant_name.answer }}", s_renamed.get("likes_surveys").question_text)
        self.assertIn("{{ participant_name.answer }}", s_renamed.get("explanation").question_text)
        
        # Verify old name is gone from piping
        self.assertNotIn("{{ user_name.answer }}", s_renamed.get("likes_surveys").question_text)
        self.assertNotIn("{{ user_name.answer }}", s_renamed.get("explanation").question_text)

    def test_rename_question_with_memory_plan(self):
        """Test that memory plans are updated when questions are renamed."""
        s = self.gen_survey()
        
        # Add memory relationship
        s = s.add_targeted_memory("favorite_subject", "like_school")
        
        # Verify memory plan before rename
        memory_plan_before = dict(s.memory_plan)
        self.assertIn("favorite_subject", memory_plan_before)
        self.assertIn("like_school", memory_plan_before["favorite_subject"].data)
        
        # Rename the focal question
        s_renamed = s.rename_question("favorite_subject", "preferred_subject")
        memory_plan_after = dict(s_renamed.memory_plan)
        
        # Verify focal question name updated
        self.assertIn("preferred_subject", memory_plan_after)
        self.assertNotIn("favorite_subject", memory_plan_after)
        self.assertIn("like_school", memory_plan_after["preferred_subject"].data)
        
        # Rename the prior question
        s_renamed2 = s_renamed.rename_question("like_school", "school_preference")
        memory_plan_final = dict(s_renamed2.memory_plan)
        
        # Verify prior question name updated
        self.assertIn("school_preference", memory_plan_final["preferred_subject"].data)
        self.assertNotIn("like_school", memory_plan_final["preferred_subject"].data)

    def test_rename_question_with_instructions(self):
        """Test that instructions are updated when questions are renamed."""
        from edsl.instructions import Instruction
        
        s = self.gen_survey()
        
        # Add instruction that references a question
        instruction = Instruction(
            text="Pay attention to your answer for {{ like_school.answer }} when answering later questions.",
            name="attention"
        )
        s_with_instruction = s.add_instruction(instruction)
        
        # Verify instruction before rename
        instruction_text_before = s_with_instruction._instruction_names_to_instructions["attention"].text
        self.assertIn("{{ like_school.answer }}", instruction_text_before)
        
        # Rename the question
        s_renamed = s_with_instruction.rename_question("like_school", "school_preference")
        
        # Verify instruction after rename
        instruction_text_after = s_renamed._instruction_names_to_instructions["attention"].text
        self.assertIn("{{ school_preference.answer }}", instruction_text_after)
        self.assertNotIn("{{ like_school.answer }}", instruction_text_after)

    def test_rename_question_error_conditions(self):
        """Test error conditions for question renaming."""
        s = self.gen_survey()
        
        # Test renaming non-existent question
        with self.assertRaises(Exception) as context:
            s.rename_question("nonexistent", "new_name")
        self.assertIn("not found", str(context.exception))
        
        # Test renaming to existing name
        with self.assertRaises(Exception) as context:
            s.rename_question("like_school", "favorite_subject")
        self.assertIn("already exists", str(context.exception))
        
        # Test invalid identifier
        with self.assertRaises(Exception) as context:
            s.rename_question("like_school", "123invalid")
        self.assertIn("not a valid Python identifier", str(context.exception))
        
        # Test invalid identifier with spaces
        with self.assertRaises(Exception) as context:
            s.rename_question("like_school", "invalid name")
        self.assertIn("not a valid Python identifier", str(context.exception))

    def test_rename_question_preserves_survey_structure(self):
        """Test that renaming preserves overall survey structure."""
        s = self.gen_survey()
        original_question_count = len(s.questions)
        original_question_texts = [q.question_text for q in s.questions]
        
        # Add some complexity
        s = s.add_rule("like_school", "{{ like_school.answer }} == 'yes'", "manual")
        s = s.add_targeted_memory("manual", "like_school")
        
        # Rename a question
        s_renamed = s.rename_question("like_school", "school_preference")
        
        # Verify structure preservation
        self.assertEqual(len(s_renamed.questions), original_question_count)
        renamed_question_texts = [q.question_text for q in s_renamed.questions]
        self.assertEqual(renamed_question_texts, original_question_texts)
        
        # Verify that survey is still functional
        next_q = s_renamed.next_question("school_preference", {"school_preference.answer": "yes"})
        self.assertEqual(next_q.question_name, "manual")

    def test_rename_question_method_chaining(self):
        """Test that rename_question can be chained with other methods."""
        s = self.gen_survey()
        
        # Test method chaining
        s_chained = (s.rename_question("like_school", "school_preference")
                    .rename_question("favorite_subject", "preferred_subject")
                    .rename_question("manual", "hands_on"))
        
        expected_names = ["school_preference", "preferred_subject", "hands_on"]
        self.assertEqual(s_chained.question_names, expected_names)
        
        # Verify each question can be retrieved
        for name in expected_names:
            self.assertIsNotNone(s_chained.get(name))

    def test_rename_question_complex_scenario(self):
        """Test renaming in a complex scenario with multiple interdependencies."""
        from edsl.questions import QuestionFreeText, QuestionMultipleChoice
        from edsl.instructions import Instruction
        
        # Create complex survey
        q1 = QuestionFreeText(question_text="What is your name?", question_name="user_name")
        q2 = QuestionMultipleChoice(
            question_text="Hello {{ user_name.answer }}, do you like {{ user_name }} questions?",
            question_options=["yes", "no"],
            question_name="likes_questions"
        )
        q3 = QuestionFreeText(
            question_text="{{ user_name.answer }}, you said {{ likes_questions.answer }}. Why?",
            question_name="explanation"
        )
        
        s = Survey([q1, q2, q3])
        
        # Add complex rule
        s = s.add_rule("user_name", "{{ user_name.answer }} == 'Bob'", "explanation")
        
        # Add memory relationships
        s = s.add_targeted_memory("explanation", "user_name")
        s = s.add_targeted_memory("explanation", "likes_questions")
        
        # Add instruction
        instruction = Instruction(
            text="Remember that {{ user_name.answer }} should be consistent throughout.",
            name="consistency"
        )
        s = s.add_instruction(instruction)
        
        # Rename the central question
        s_renamed = s.rename_question("user_name", "participant_name")
        
        # Verify all components were updated
        # 1. Question text piping
        q2_text = s_renamed.get("likes_questions").question_text
        self.assertIn("{{ participant_name.answer }}", q2_text)
        self.assertIn("{{ participant_name }}", q2_text)  # Test both formats
        
        # 2. Rules
        rule_expressions = [rule.expression for rule in s_renamed.rule_collection if "participant_name" in rule.expression]
        self.assertTrue(any("{{ participant_name.answer }}" in expr for expr in rule_expressions))
        
        # 3. Memory plan
        memory_plan = dict(s_renamed.memory_plan)
        self.assertIn("participant_name", memory_plan["explanation"].data)
        
        # 4. Instructions
        instruction_text = s_renamed._instruction_names_to_instructions["consistency"].text
        self.assertIn("{{ participant_name.answer }}", instruction_text)
        
        # 5. Verify no old references remain
        all_texts = [q.question_text for q in s_renamed.questions]
        all_texts.append(instruction_text)
        all_texts.extend([rule.expression for rule in s_renamed.rule_collection])
        
        for text in all_texts:
            self.assertNotIn("{{ user_name.answer }}", text)


if __name__ == "__main__":
    unittest.main()
    # s = TestSurvey().gen_survey()
    # TestSurvey().test_eos_skip_logic()
