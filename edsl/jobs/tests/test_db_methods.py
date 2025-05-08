"""Tests for the to_db and from_db methods of the Jobs class.

This module tests the implementation of the to_db and from_db abstract methods
from the Base class in the Jobs domain object.
"""

import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock, create_autospec
import json

# Import the Jobs ORM implementation directly
from edsl.jobs.orm import SQLJob, save_job, load_job, to_db_impl, from_db_impl
from edsl.base.db_manager import get_db_manager, DBManager


class TestJobsDBMethods(unittest.TestCase):
    """Test the to_db and from_db methods of the Jobs class."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary SQLite database
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()
        
        # Create a DBManager with the temporary database
        self.db_manager = get_db_manager(f"sqlite:///{self.db_path}")
        
        # Create all tables
        self.db_manager.initialize_tables()
    
    def tearDown(self):
        """Clean up after tests."""
        # Close database connections and remove temp file
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.engine.dispose()
        
        # Delete the temporary database file
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_serialization_functions(self):
        """Test the serialize_value and deserialize_value functions."""
        # Test serializing basic types
        val_type, val_text = SQLJob.serialize_value("test string")
        self.assertEqual(val_type, "str")
        self.assertEqual(val_text, "test string")
        
        val_type, val_text = SQLJob.serialize_value(123)
        self.assertEqual(val_type, "int")
        self.assertEqual(val_text, "123")
        
        val_type, val_text = SQLJob.serialize_value(True)
        self.assertEqual(val_type, "bool")
        self.assertEqual(val_text, "true")
        
        # Test deserializing basic types
        value = SQLJob.deserialize_value("str", "test string")
        self.assertEqual(value, "test string")
        
        value = SQLJob.deserialize_value("int", "123")
        self.assertEqual(value, 123)
        
        value = SQLJob.deserialize_value("bool", "true")
        self.assertEqual(value, True)
        
        # Test JSON serialization
        test_dict = {"key1": "value1", "key2": 2}
        val_type, val_text = SQLJob.serialize_value(test_dict)
        self.assertEqual(val_type, "json")
        self.assertEqual(json.loads(val_text), test_dict)
        
        # Test JSON deserialization
        value = SQLJob.deserialize_value("json", json.dumps(test_dict))
        self.assertEqual(value, test_dict)
    
    @patch('edsl.jobs.orm.save_job')
    def test_to_db_impl(self, mock_save_job):
        """Test the to_db_impl function."""
        # Create a mock Jobs class and instance
        mock_job = MagicMock()
        
        # Create a mock SQLJob to return
        mock_job_orm = MagicMock()
        mock_job_orm.id = 123
        mock_save_job.return_value = mock_job_orm
        
        # Mock the session scope
        with patch('edsl.base.db_manager.DBManager.session_scope') as mock_session_scope:
            # Create a mock context manager
            mock_context = MagicMock()
            mock_session = MagicMock()
            mock_context.__enter__.return_value = mock_session
            mock_session_scope.return_value = mock_context
            
            # Call to_db_impl
            job_id = to_db_impl(mock_job, self.db_manager)
            
            # Verify ID is returned
            self.assertEqual(job_id, 123)
            
            # Verify save_job was called with the right parameters
            mock_save_job.assert_called_once_with(mock_session, mock_job)
    
    @patch('edsl.jobs.orm.load_job')
    def test_from_db_impl(self, mock_load_job):
        """Test the from_db_impl function."""
        # Create a mock Jobs class and instance
        mock_jobs_class = MagicMock()
        mock_job = MagicMock()
        
        # Set up the mock to return our job
        mock_load_job.return_value = mock_job
        
        # Mock the session scope
        with patch('edsl.base.db_manager.DBManager.session_scope') as mock_session_scope:
            # Create a mock context manager
            mock_context = MagicMock()
            mock_session = MagicMock()
            mock_context.__enter__.return_value = mock_session
            mock_session_scope.return_value = mock_context
            
            # Call from_db_impl
            result = from_db_impl(mock_jobs_class, self.db_manager, 123)
            
            # Verify the result
            self.assertEqual(result, mock_job)
            
            # Verify load_job was called with the correct parameters
            mock_load_job.assert_called_once_with(mock_session, 123)


if __name__ == "__main__":
    unittest.main()