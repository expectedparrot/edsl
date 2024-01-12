import unittest
from edsl.surveys.memory import MemoryPlan


class TestMemoryPlan(unittest.TestCase):
    def example(self):
        survey_questions = ["q1", "q2", "q3"]
        memory_plan = MemoryPlan(survey_question_names=survey_questions)
        return memory_plan, survey_questions

    def test_initialization(self):
        memory_plan, survey_questions = self.example()
        self.assertIsInstance(memory_plan, MemoryPlan)
        self.assertEqual(survey_questions, memory_plan.survey_question_names)

    def test_check_valid_question_name(self):
        memory_plan, _ = self.example()
        memory_plan.check_valid_question_name("q1")
        with self.assertRaises(ValueError):
            memory_plan.check_valid_question_name("invalid_question")

    def test_add_single_memory(self):
        memory_plan, _ = self.example()
        memory_plan.add_single_memory("q2", "q1")
        self.assertIn("q1", memory_plan["q2"])

    def test_add_memory_collection(self):
        memory_plan, _ = self.example()
        memory_plan.add_memory_collection("q3", ["q1", "q2"])
        self.assertEqual(memory_plan["q3"], ["q1", "q2"])

    def test_to_dict(self):
        memory_plan, _ = self.example()
        memory_plan.add_single_memory("q2", "q1")
        expected_dict = {
            "survey_question_names": ["q1", "q2", "q3"],
            "data": {"q2": {"prior_questions": ["q1"]}},
        }
        self.assertEqual(memory_plan.to_dict(), expected_dict)

    def test_from_dict(self):
        data = {
            "survey_question_names": ["q1", "q2", "q3"],
            "data": {"q2": {"prior_questions": ["q1"]}},
        }
        new_memory_plan = MemoryPlan.from_dict(data)
        self.assertIn("q1", new_memory_plan["q2"])


if __name__ == "__main__":
    unittest.main()
