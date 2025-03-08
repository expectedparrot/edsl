import pytest
import unittest
from unittest.mock import Mock
from edsl.invigilators import InvigilatorHuman
from edsl.surveys import Survey


class TestInvigilatorHuman(unittest.TestCase):
    def test_answer_question(self):
        agent = Mock()
        agent.answer_question_directly.return_value = "Human Answer"
        question = Mock()
        question._validate_response.side_effect = lambda x: x  # Just return the input
        scenario = Mock()
        model = Mock()
        memory_plan = Mock()
        current_answers = Mock()

        invigilator = InvigilatorHuman(
            agent=agent,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            survey=Survey.example(),
        )
        response = invigilator.answer_question()
        self.assertEqual(
            response.comment, "This is a real survey response from a human."
        )
        # self.assertEqual(response["model"], "human")
        # self.assertEqual(response["scenario"], scenario)


# Similarly, write test cases for InvigilatorFunctional and InvigilatorAI

if __name__ == "__main__":
    unittest.main()
