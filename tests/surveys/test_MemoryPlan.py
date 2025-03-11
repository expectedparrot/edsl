import unittest
from unittest.mock import Mock
from edsl.surveys.memory import MemoryPlan


class TestMemoryPlan(unittest.TestCase):
    @property
    def question_texts(self):
        return ["How are you?", "What is your age?", "Where are you from?"]

    @property
    def answers_dict(self):
        return {"q1": "Good!", "q2": "None of your business", "q3": "Outerspace"}

    @property
    def question_names(self):
        return ["q1", "q2", "q3"]

    def example(self):
        survey = Mock()
        survey.questions = []
        for question_name, question_text in zip(
            self.question_names, self.question_texts
        ):
            fake_question = Mock()
            fake_question.question_text = question_text
            fake_question.question_name = question_name
            survey.questions.append(fake_question)
        memory_plan = MemoryPlan(survey=survey)
        return memory_plan

    def test_initialization(self):
        memory_plan = self.example()
        self.assertIsInstance(memory_plan, MemoryPlan)
        self.assertEqual(self.question_names, memory_plan.survey_question_names)

    def test_check_valid_question_name(self):
        memory_plan = self.example()
        memory_plan._check_valid_question_name("q1")
        with self.assertRaises(ValueError):
            memory_plan._check_valid_question_name("invalid_question")

    def test_add_single_memory(self):
        memory_plan = self.example()
        memory_plan.add_single_memory("q2", "q1")
        self.assertIn("q1", memory_plan["q2"])

    def test_add_memory_collection(self):
        memory_plan = self.example()
        memory_plan.add_memory_collection("q3", ["q1", "q2"])
        self.assertEqual(memory_plan["q3"], ["q1", "q2"])

    def test_to_dict(self):
        memory_plan = self.example()
        memory_plan.add_single_memory("q2", "q1")
        expected_dict = {
            "survey_question_names": self.question_names,
            "survey_question_texts": self.question_texts,
            "data": {"q2": {"prior_questions": ["q1"]}},
        }
        self.assertEqual(memory_plan.to_dict(), expected_dict)

    def test_from_dict(self):
        from edsl.surveys.memory import Memory

        data = {
            "survey_question_names": self.question_names,
            "survey_question_texts": self.question_texts,
            "data": {"q2": Memory(["q1"]).to_dict()},
        }
        new_memory_plan = MemoryPlan.from_dict(data)
        self.assertIn("q1", new_memory_plan["q2"])

    def test_prompt_fragment(self):
        memory_plan = self.example()
        memory_plan.add_single_memory("q2", "q1")
        prompt = memory_plan.get_memory_prompt_fragment("q2", self.answers_dict)
        self.assertIn("How are you?", prompt)


if __name__ == "__main__":
    unittest.main()
