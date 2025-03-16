import unittest
import asyncio
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any

from edsl.agents import Agent
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.scenarios import Scenario
from edsl.interviews import Interview
from edsl.tasks.task_status_enum import TaskStatus

class TestInterviewCoverage(unittest.TestCase):
    def setUp(self):
        """Set up common test objects"""
        # Create a simple survey with a few questions
        self.survey = Survey()
        self.q1 = QuestionFreeText(question_text="Question 1", question_name="q1")
        self.q2 = QuestionFreeText(question_text="Question 2", question_name="q2")
        self.q3 = QuestionFreeText(question_text="Question 3", question_name="q3")
        self.survey.add_question(self.q1)
        self.survey.add_question(self.q2)
        self.survey.add_question(self.q3)
        
        # Create a scenario
        self.scenario = Scenario({"context": "Test context"})
        
        # Create an agent
        self.agent = Agent(traits={"trait1": "value1"})
        
        # Mock language model class
        self.model = MagicMock()
        
        # Mock to_dict method on the mock model
        self.model.to_dict = MagicMock(return_value={"model": "test_model", "inference_service": "test_service"})
        
        # Create the interview object
        self.interview = Interview(
            agent=self.agent,
            survey=self.survey,
            scenario=self.scenario,
            model=self.model
        )
    
    def test_initialization(self):
        """Test that the Interview initializes correctly"""
        # Check basic attribute initialization
        self.assertEqual(self.interview.agent, self.agent)
        self.assertEqual(self.interview.scenario, self.scenario)
        self.assertEqual(self.interview.model, self.model)
        
        # Check derived attributes
        self.assertEqual(len(self.interview.to_index), 3)
        self.assertEqual(self.interview.to_index['q1'], 0)
        self.assertEqual(self.interview.to_index['q2'], 1)
        self.assertEqual(self.interview.to_index['q3'], 2)
        
        # Check empty collections
        self.assertEqual(len(self.interview.answers), 0)
        self.assertEqual(len(self.interview.exceptions), 0)
        self.assertEqual(len(self.interview.failed_questions), 0)
    
    def test_property_accessors(self):
        """Test the property accessors and setters"""
        # Test cache property
        mock_cache = MagicMock()
        self.interview.cache = mock_cache
        self.assertEqual(self.interview.cache, mock_cache)
        
        # Test skip_retry property
        self.assertFalse(self.interview.skip_retry)
        self.interview.running_config.skip_retry = True
        self.assertTrue(self.interview.skip_retry)
        
        # Test raise_validation_errors property
        self.assertTrue(self.interview.raise_validation_errors)
        self.interview.running_config.raise_validation_errors = False
        self.assertFalse(self.interview.raise_validation_errors)
    
    def test_hash(self):
        """Test the hash function"""
        # Create a duplicate interview
        interview2 = Interview(
            agent=self.agent,
            survey=self.survey,
            scenario=self.scenario,
            model=self.model
        )
        
        # Their hashes should be equal
        self.assertEqual(hash(self.interview), hash(interview2))
        
        # Change something and check the hash changes
        interview2.iteration = 1
        self.assertNotEqual(hash(self.interview), hash(interview2))
    
    def test_equality(self):
        """Test equality comparison"""
        # Create an identical interview
        interview2 = Interview(
            agent=self.agent,
            survey=self.survey,
            scenario=self.scenario,
            model=self.model
        )
        
        # They should be equal
        self.assertEqual(self.interview, interview2)
        
        # Change something and check they're no longer equal
        interview2.iteration = 1
        self.assertNotEqual(self.interview, interview2)
    
    @patch('edsl.interviews.interview.Interview._extract_valid_results')
    @patch('edsl.interviews.interview.AnswerQuestionFunctionConstructor')
    @patch('edsl.interviews.interview.ModelBuckets')
    @patch('edsl.interviews.interview.Interview.task_status_logs', new_callable=PropertyMock)
    def test_async_conduct_interview_basics(self, mock_status_logs, mock_buckets, mock_constructor, mock_extract_results):
        """Test the basic flow of async_conduct_interview"""
        # Setup mocks
        mock_buckets.return_value.get_bucket.return_value = MagicMock()
        mock_constructor.return_value.construct.return_value = MagicMock()
        
        # Mock task_status_logs to return SUCCESS status for each question
        mock_status_logs.return_value = {
            'q1': [{'value': TaskStatus.SUCCESS}],
            'q2': [{'value': TaskStatus.SUCCESS}],
            'q3': [{'value': TaskStatus.SUCCESS}]
        }
        
        # Mock _extract_valid_results to return mock results
        mock_results = []
        for _ in range(3):  # One for each question
            result_mock = MagicMock()
            mock_results.append(result_mock)
        
        mock_extract_results.return_value = mock_results
        
        # Run the interview using a synchronous event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Run the interview
            result = loop.run_until_complete(self.interview.async_conduct_interview())
            
            # Check that all questions are marked as completed
            status_logs = self.interview.task_status_logs
            self.assertEqual(len(status_logs), 3)
            for question_name in ['q1', 'q2', 'q3']:
                log_entries = status_logs[question_name]
                final_status = log_entries[-1]['value']
                self.assertEqual(final_status, TaskStatus.SUCCESS)
        finally:
            loop.close()
    
    def test_example(self):
        """Test the example method"""
        example = Interview.example()
        
        # Verify it returns a valid Interview instance
        self.assertIsInstance(example, Interview)
        self.assertIsInstance(example.agent, Agent)
        self.assertIsInstance(example.survey, Survey)
        self.assertIsInstance(example.scenario, Scenario)
    
    def test_to_dict(self):
        """Test serialization to dict"""
        dict_repr = self.interview.to_dict()
        
        # Check dict structure
        self.assertIn('agent', dict_repr)
        self.assertIn('survey', dict_repr)
        self.assertIn('scenario', dict_repr)
        self.assertIn('model', dict_repr)
        self.assertIn('iteration', dict_repr)
        self.assertEqual(dict_repr['iteration'], 0)
    
    def test_from_dict(self):
        """Test deserialization from dict using the example method"""
        # Use example() method which properly creates a real instance
        interview_example = Interview.example()
        
        # Create a dictionary representation from that real instance
        dict_repr = interview_example.to_dict()
        
        # Create a new instance from the dict
        new_interview = Interview.from_dict(dict_repr)
        
        # Check key properties match
        self.assertEqual(dict(new_interview.to_index), dict(interview_example.to_index))
        self.assertEqual(new_interview.iteration, interview_example.iteration)
        
        # Check basic attributes to ensure deserialization worked
        self.assertIsNotNone(new_interview.agent)
        self.assertIsNotNone(new_interview.survey)
        self.assertIsNotNone(new_interview.scenario)
        self.assertIsNotNone(new_interview.model)

if __name__ == "__main__":
    unittest.main()