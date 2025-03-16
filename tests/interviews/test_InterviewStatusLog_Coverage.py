import unittest
import time
from edsl.interviews.interview_status_log import InterviewStatusLog
from edsl.tasks.task_status_enum import TaskStatus

class TestInterviewStatusLogCoverage(unittest.TestCase):
    def setUp(self):
        """Set up for tests"""
        self.status_log = InterviewStatusLog()
    
    def test_initialization(self):
        """Test initialization"""
        # Should start with empty list
        self.assertEqual(len(self.status_log), 0)
        
        # Initialize with a value
        status_log = InterviewStatusLog([
            {"value": TaskStatus.NOT_STARTED, "log_time": 0}
        ])
        
        self.assertEqual(len(status_log), 1)
        self.assertEqual(status_log[0]["value"], TaskStatus.NOT_STARTED)
    
    def test_append(self):
        """Test appending values"""
        # Append a value
        self.status_log.append(TaskStatus.NOT_STARTED)
        
        # Check it was added with a timestamp
        self.assertEqual(len(self.status_log), 1)
        self.assertEqual(self.status_log[0]["value"], TaskStatus.NOT_STARTED)
        self.assertIn("log_time", self.status_log[0])
        
        # Append another value after a small delay
        time.sleep(0.01)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Check it was added with a later timestamp
        self.assertEqual(len(self.status_log), 2)
        self.assertEqual(self.status_log[1]["value"], TaskStatus.SUCCESS)
        self.assertGreater(self.status_log[1]["log_time"], self.status_log[0]["log_time"])
    
    def test_latest(self):
        """Test getting the latest value"""
        # Empty log should return None
        self.assertIsNone(self.status_log.latest())
        
        # Add some values
        self.status_log.append(TaskStatus.NOT_STARTED)
        time.sleep(0.01)
        self.status_log.append(TaskStatus.API_CALL_IN_PROGRESS)
        time.sleep(0.01)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Latest should be SUCCESS
        latest = self.status_log.latest()
        self.assertEqual(latest["value"], TaskStatus.SUCCESS)
    
    def test_latest_value(self):
        """Test getting just the latest value (not the wrapper dict)"""
        # Empty log should return None
        self.assertIsNone(self.status_log.latest_value())
        
        # Add some values
        self.status_log.append(TaskStatus.NOT_STARTED)
        self.status_log.append(TaskStatus.API_CALL_IN_PROGRESS)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Latest value should be SUCCESS
        self.assertEqual(self.status_log.latest_value(), TaskStatus.SUCCESS)
    
    def test_indexing(self):
        """Test indexing the log"""
        # Add some values
        self.status_log.append(TaskStatus.NOT_STARTED)
        self.status_log.append(TaskStatus.API_CALL_IN_PROGRESS)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Access by index
        self.assertEqual(self.status_log[0]["value"], TaskStatus.NOT_STARTED)
        self.assertEqual(self.status_log[1]["value"], TaskStatus.API_CALL_IN_PROGRESS)
        self.assertEqual(self.status_log[2]["value"], TaskStatus.SUCCESS)
        
        # Check IndexError for out of bounds
        with self.assertRaises(IndexError):
            _ = self.status_log[3]
    
    def test_iteration(self):
        """Test iteration through the log"""
        # Add some values
        self.status_log.append(TaskStatus.NOT_STARTED)
        self.status_log.append(TaskStatus.API_CALL_IN_PROGRESS)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Iterate and check
        expected_values = [TaskStatus.NOT_STARTED, TaskStatus.API_CALL_IN_PROGRESS, TaskStatus.SUCCESS]
        for i, entry in enumerate(self.status_log):
            self.assertEqual(entry["value"], expected_values[i])
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        # Add some values
        self.status_log.append(TaskStatus.NOT_STARTED)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Convert to dict
        dict_repr = self.status_log.to_dict()
        
        # Should be a list of dictionaries
        self.assertIsInstance(dict_repr, list)
        self.assertEqual(len(dict_repr), 2)
        
        # Each entry should have value and log_time
        for entry in dict_repr:
            self.assertIn("value", entry)
            self.assertIn("log_time", entry)
        
        # Check values are serialized as integers
        self.assertEqual(dict_repr[0]["value"], 1)  # TaskStatus.NOT_STARTED value
        self.assertEqual(dict_repr[1]["value"], 8)  # TaskStatus.SUCCESS value
    
    def test_from_dict(self):
        """Test restoration from dictionary"""
        # Create a dictionary representation
        dict_repr = [
            {"value": 1, "log_time": 0},  # TaskStatus.NOT_STARTED
            {"value": 8, "log_time": 1}   # TaskStatus.SUCCESS
        ]
        
        # Create from dict
        status_log = InterviewStatusLog.from_dict(dict_repr)
        
        # Should have the expected entries
        self.assertEqual(len(status_log), 2)
        self.assertEqual(status_log[0]["value"], TaskStatus.NOT_STARTED)
        self.assertEqual(status_log[1]["value"], TaskStatus.SUCCESS)
    
    def test_repr(self):
        """Test string representation"""
        # Empty log
        self.assertEqual(repr(self.status_log), "InterviewStatusLog([])")
        
        # With entries
        self.status_log.append(TaskStatus.NOT_STARTED)
        self.status_log.append(TaskStatus.SUCCESS)
        
        # Should include the values
        repr_str = repr(self.status_log)
        self.assertIn("NOT_STARTED", repr_str)
        self.assertIn("SUCCESS", repr_str)
    
    def test_contains_status(self):
        """Test checking if log contains a specific status"""
        # Add some values
        self.status_log.append(TaskStatus.NOT_STARTED)
        self.status_log.append(TaskStatus.API_CALL_IN_PROGRESS)
        
        # Should contain these statuses
        self.assertTrue(self.status_log.contains_status(TaskStatus.NOT_STARTED))
        self.assertTrue(self.status_log.contains_status(TaskStatus.API_CALL_IN_PROGRESS))
        
        # Should not contain others
        self.assertFalse(self.status_log.contains_status(TaskStatus.SUCCESS))
        self.assertFalse(self.status_log.contains_status(TaskStatus.FAILED))

if __name__ == "__main__":
    unittest.main()