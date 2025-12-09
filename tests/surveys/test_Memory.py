import unittest
import random
import asyncio
from typing import Any

from edsl.surveys.memory import Memory
from edsl.language_models import LanguageModel
from edsl.enums import InferenceServiceType
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText


class TestMemory(unittest.TestCase):
    def test_initialization(self):
        memory = Memory(["question1", "question2"])
        self.assertEqual(memory, ["question1", "question2"])

        empty_memory = Memory()
        self.assertEqual(empty_memory, [])

    def test_add_prior_question(self):
        memory = Memory()
        memory.add_prior_question("question1")
        self.assertIn("question1", memory)

    def test_repr(self):
        memory = Memory(["question1"])
        self.assertEqual(repr(memory), "Memory(prior_questions=['question1'])")

    def test_to_dict(self):
        memory = Memory(["question1"])
        self.assertEqual(memory.to_dict(), {"prior_questions": ["question1"]})

    def test_from_dict(self):
        memory = Memory.from_dict({"prior_questions": ["question1"]})
        self.assertEqual(memory, ["question1"])

    def test_adding_memories(self):

        def create_exception_throwing_model(exception: Exception, probability: float):
            class TestLanguageModelGood(LanguageModel):
                _model_ = "test"
                _parameters_ = {"temperature": 0.5}
                _inference_service_ = InferenceServiceType.TEST.value

                async def async_execute_model_call(
                    self, user_prompt: str, system_prompt: str
                ) -> dict[str, Any]:
                    await asyncio.sleep(0.1)
                    if random.random() < probability:
                        raise exception
                    return {"message": """{"answer": "SPAM!"}"""}

                def parse_response(self, raw_response: dict[str, Any]) -> str:
                    return raw_response["message"]

            return TestLanguageModelGood()

        survey = Survey()
        for i in range(10):
            q = QuestionFreeText(
                question_text="How are you?", question_name=f"question_{i}"
            )
            survey.add_question(q)
            if i > 0:
                survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
