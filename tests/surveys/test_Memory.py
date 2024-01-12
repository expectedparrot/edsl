import unittest
from edsl.surveys.memory import Memory, MemoryPlan


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
