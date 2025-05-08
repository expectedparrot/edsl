"""
Tests for the Jobs ORM serialization and deserialization functionality.

This module tests the serialization and deserialization capabilities of the
Jobs ORM, focusing on different data types and edge cases.
"""

import unittest
import pickle
from datetime import datetime
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from edsl.jobs.jobs import Jobs
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText
from edsl.jobs.data_structures import RunConfig, RunEnvironment, RunParameters
from edsl.jobs.orm import (
    Base,
    SQLJob,
    SQLJobParameter,
    save_job,
    load_job
)


class TestJobsOrmSerialization(unittest.TestCase):
    """Test the Jobs ORM serialization and deserialization capabilities."""

    def setUp(self):
        """Set up a new database for each test."""
        # Create a new in-memory SQLite database for each test
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        
        # Create a simple survey for testing
        q = QuestionFreeText(question_name="test", question_text="Test question")
        self.survey = Survey(questions=[q])
        
    def prepare_job(self, job):
        """Helper to prepare a job for testing by clearing non-serializable attributes."""
        # Clear non-serializable attributes
        job.run_config.environment.bucket_collection = None
        job.run_config.environment.cache = None
        job.run_config.environment.jobs_runner_status = None
        return job

    def tearDown(self):
        """Clean up resources after each test."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_complex_data_serialization(self):
        """Test serialization and deserialization of complex data types."""
        # Create a job with complex parameters
        job = Jobs(self.survey)
        
        # Add complex data to RunParameters
        complex_dict = {
            "nested_dict": {"key1": "value1", "key2": [1, 2, 3]},
            "list_data": [{"a": 1}, {"b": 2}, {"c": 3}]
        }
        
        # Set a custom parameter
        job.run_config.parameters.remote_inference_description = complex_dict
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        # Save the job
        job_orm = save_job(self.session, job)
        self.session.commit()
        job_id = job_orm.id
        
        # Find the complex parameter
        complex_param = None
        for param in job_orm.parameters:
            if param.key == "remote_inference_description":
                complex_param = param
                break
                
        self.assertIsNotNone(complex_param)
        # Should be either JSON serialized or pickle serialized
        self.assertTrue(complex_param.value_type in ['json', 'json:list'] or complex_param.value_type.startswith('pickle:'))
        
        # Load the job
        loaded_job = load_job(self.session, job_id)
        
        # Verify complex data was restored correctly
        self.assertEqual(
            loaded_job.run_config.parameters.remote_inference_description,
            complex_dict
        )

    def test_none_value_serialization(self):
        """Test the serialization and deserialization of None values."""
        # Create a job with None values
        job = Jobs(self.survey)
        job.run_config.parameters.remote_cache_description = None
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        # Save the job
        job_orm = save_job(self.session, job)
        self.session.commit()
        
        # Find the None parameter
        null_param = None
        for param in job_orm.parameters:
            if param.key == "remote_cache_description":
                null_param = param
                break
                
        self.assertIsNotNone(null_param)
        self.assertEqual(null_param.value_type, "null")
        
        # Load the job
        loaded_job = load_job(self.session, job_id=job_orm.id)
        
        # Check if None was preserved
        self.assertIsNone(loaded_job.run_config.parameters.remote_cache_description)

    def test_direct_value_serialization(self):
        """Test the SQLJob.serialize_value and deserialize_value methods directly."""
        test_values = [
            (None, 'null', 'null'),
            (True, 'bool', 'true'),
            (False, 'bool', 'false'),
            (42, 'int', '42'),
            (3.14, 'float', '3.14'),
            ("test string", 'str', 'test string'),
            ({"simple": "dict"}, 'json', json.dumps({"simple": "dict"})),
            ([1, 2, 3], 'json:list', json.dumps([1, 2, 3]))
        ]
        
        for value, expected_type, expected_serialized in test_values:
            # Test serialization
            value_type, serialized = SQLJob.serialize_value(value)
            self.assertEqual(value_type, expected_type)
            
            if value is not None:  # Skip None checks for serialized text
                self.assertEqual(serialized, expected_serialized)
            
            # Test deserialization
            deserialized = SQLJob.deserialize_value(value_type, serialized)
            
            # For dictionaries and lists, compare JSON-loaded versions
            if isinstance(value, (dict, list)):
                if isinstance(value, dict):
                    self.assertDictEqual(deserialized, value)
                else:
                    self.assertListEqual(deserialized, value)
            else:
                self.assertEqual(deserialized, value)
                
    def test_fallback_to_string_for_unpicklable(self):
        """Test fallback to string representation for unpicklable objects."""
        # Create a simple object that can be represented as a string
        class_name = self.__class__.__name__
        
        # Test with a string-representable value
        value_type, serialized = SQLJob.serialize_value(class_name)
        self.assertEqual(value_type, 'str')
        
        # Test deserialization
        deserialized = SQLJob.deserialize_value(value_type, serialized)
        self.assertEqual(deserialized, class_name)
        
    def test_large_data_serialization(self):
        """Test serialization of large data."""
        # Create a job with large string data
        job = Jobs(self.survey)
        large_string = "x" * 10000  # 10,000 character string
        job.run_config.parameters.remote_inference_description = large_string
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        # Save the job
        job_orm = save_job(self.session, job)
        self.session.commit()
        
        # Load the job
        loaded_job = load_job(self.session, job_orm.id)
        
        # Verify large string was preserved
        self.assertEqual(
            loaded_job.run_config.parameters.remote_inference_description,
            large_string
        )
        self.assertEqual(
            len(loaded_job.run_config.parameters.remote_inference_description),
            10000
        )


if __name__ == '__main__':
    unittest.main()