import unittest
from edsl.interviews.interview_status_log import InterviewStatusLog
from edsl.tasks.task_status_enum import TaskStatus

class TestInterviewStatusLogSimple(unittest.TestCase):
    """Simple tests for the InterviewStatusLog class.
    
    These tests only verify the list-like behavior of the class.
    """
    
    def setUp(self):
        """Setup test data"""
        self.log = InterviewStatusLog()
        
        # Add some status entries
        self.log.append(TaskStatus.NOT_STARTED)
        self.log.append(TaskStatus.API_CALL_IN_PROGRESS)
        self.log.append(TaskStatus.SUCCESS)
    
    def test_append_and_length(self):
        """Test appending values and checking length"""
        # Should have 3 entries from setUp
        self.assertEqual(len(self.log), 3)
        
        # Append one more
        self.log.append(TaskStatus.FAILED)
        self.assertEqual(len(self.log), 4)
    
    def test_latest_methods(self):
        """Test latest and latest_value methods"""
        # Latest should be SUCCESS
        latest = self.log.latest()
        self.assertEqual(latest["value"], TaskStatus.SUCCESS)
        
        # Latest value should also be SUCCESS
        latest_value = self.log.latest_value()
        self.assertEqual(latest_value, TaskStatus.SUCCESS)
    
    def test_contains_status(self):
        """Test checking if the log contains a specific status"""
        # Should contain these statuses
        self.assertTrue(self.log.contains_status(TaskStatus.NOT_STARTED))
        self.assertTrue(self.log.contains_status(TaskStatus.API_CALL_IN_PROGRESS))
        self.assertTrue(self.log.contains_status(TaskStatus.SUCCESS))
        
        # Should not contain this status
        self.assertFalse(self.log.contains_status(TaskStatus.CANCELLED))

if __name__ == "__main__":
    unittest.main()