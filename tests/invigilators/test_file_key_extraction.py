import unittest
import tempfile
from edsl.invigilators.question_template_replacements_builder import QuestionTemplateReplacementsBuilder
from edsl.invigilators.prompt_constructor import PromptConstructor
from edsl.scenarios import Scenario, FileStore
from edsl.questions import QuestionMultipleChoice
from edsl.agents import Agent
from edsl.surveys import Survey
from edsl.language_models.model import Model
from edsl.surveys.memory import MemoryPlan


class TestFileKeyExtraction(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.tmp_file = tempfile.NamedTemporaryFile()
        self.tmp_file.write(b"Test file content")
        self.tmp_file.seek(0)
        self.file_store = FileStore(self.tmp_file.name)
        
    def tearDown(self):
        # Clean up the temporary file
        self.tmp_file.close()
        
    def test_direct_key_reference(self):
        scenario = Scenario({"file1": self.file_store})
        question = QuestionMultipleChoice(
            question_text="What do you think of this file: {{ file1 }}",
            question_name="q0", 
            question_options=["good", "bad"]
        )
        qtrb = QuestionTemplateReplacementsBuilder(
            scenario=scenario,
            question=question,
            prior_answers_dict={},
            agent=None
        )
        file_keys = qtrb.question_file_keys()
        self.assertEqual(file_keys, ["file1"])
        
    def test_scenario_key_reference(self):
        scenario = Scenario({"print": self.file_store})  # Using 'print' as the key
        question = QuestionMultipleChoice(
            question_text="What do you think of this print: {{ scenario.print }}",
            question_name="q0", 
            question_options=["good", "bad"]
        )
        qtrb = QuestionTemplateReplacementsBuilder(
            scenario=scenario,
            question=question,
            prior_answers_dict={},
            agent=None
        )
        file_keys = qtrb.question_file_keys()
        self.assertEqual(file_keys, ["print"])
        
    def test_mixed_references(self):
        scenario = Scenario({"file1": self.file_store, "print": self.file_store})
        question = QuestionMultipleChoice(
            question_text="Compare {{ file1 }} with {{ scenario.print }}",
            question_name="q0", 
            question_options=["good", "bad"]
        )
        qtrb = QuestionTemplateReplacementsBuilder(
            scenario=scenario,
            question=question,
            prior_answers_dict={},
            agent=None
        )
        file_keys = sorted(qtrb.question_file_keys())
        self.assertEqual(file_keys, ["file1", "print"])
        
    def test_prompt_constructor_file_keys(self):
        """Test just the file_keys_from_question property, without running get_prompts()."""
        scenario = Scenario({"file1": self.file_store, "print": self.file_store})
        question = QuestionMultipleChoice(
            question_text="Compare {{ file1 }} with {{ scenario.print }}",
            question_name="q0", 
            question_options=["good", "bad"]
        )
        
        # Create a minimal constructor that doesn't try to build full prompts
        constructor = PromptConstructor(
            agent=Agent(),
            question=question,
            scenario=scenario,
            survey=Survey(),
            model=Model(),
            current_answers={},
            memory_plan=MemoryPlan()
        )
        
        # Test just the file_keys_from_question property
        file_keys = sorted(constructor.file_keys_from_question)
        self.assertEqual(file_keys, ["file1", "print"])


if __name__ == "__main__":
    unittest.main()