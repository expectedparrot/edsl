import unittest
from unittest.mock import Mock
from edsl.agents.Invigilator import InvigilatorDebug, InvigilatorHuman


class TestInvigilatorDebug(unittest.TestCase):
    def test_answer_question(self):
        agent = Mock()
        question = Mock()
        question.simulate_answer.return_value = "Mocked Answer"
        scenario = Mock()
        model = Mock()

        invigilator = InvigilatorDebug(agent, question, scenario, model)
        self.assertEqual(invigilator.answer_question(), "Mocked Answer")


class TestInvigilatorHuman(unittest.TestCase):
    def test_answer_question(self):
        agent = Mock()
        agent.answer_question_directly.return_value = "Human Answer"
        question = Mock()
        question.validate_response.side_effect = lambda x: x  # Just return the input
        scenario = Mock()
        model = Mock()

        invigilator = InvigilatorHuman(agent, question, scenario, model)
        response = invigilator.answer_question()
        self.assertEqual(response["answer"], "Human Answer")
        self.assertEqual(response["model"], "human")
        self.assertEqual(response["scenario"], scenario)


# Similarly, write test cases for InvigilatorFunctional and InvigilatorAI

if __name__ == "__main__":
    unittest.main()
