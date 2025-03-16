import unittest
from edsl.interviews.interview_status_dictionary import InterviewStatusDictionary
from edsl.tasks.task_status_enum import TaskStatus

class TestInterviewStatusDictionarySimple(unittest.TestCase):
    def setUp(self):
        """Set up for tests"""
        self.status_dict = InterviewStatusDictionary()
    
    def test_initialization(self):
        """Test initialization"""
        # Should initialize with all TaskStatus enum values set to 0
        for task_status in TaskStatus:
            self.assertEqual(self.status_dict[task_status], 0)
        
        # Should also include number_from_cache
        self.assertEqual(self.status_dict["number_from_cache"], 0)
        
        # Create with custom data
        data = {task_status: 0 for task_status in TaskStatus}
        data["number_from_cache"] = 0
        data[TaskStatus.SUCCESS] = 5  # Set SUCCESS to 5
        
        custom_dict = InterviewStatusDictionary(data)
        self.assertEqual(custom_dict[TaskStatus.SUCCESS], 5)
    
    def test_addition(self):
        """Test adding two dictionaries"""
        # Create two dictionaries
        dict1 = InterviewStatusDictionary()
        dict1[TaskStatus.SUCCESS] = 3
        
        dict2 = InterviewStatusDictionary()
        dict2[TaskStatus.SUCCESS] = 2
        dict2[TaskStatus.FAILED] = 1
        
        # Add them
        result = dict1 + dict2
        
        # Check the result
        self.assertEqual(result[TaskStatus.SUCCESS], 5)
        self.assertEqual(result[TaskStatus.FAILED], 1)
        
        # Original dictionaries should be unchanged
        self.assertEqual(dict1[TaskStatus.SUCCESS], 3)
        self.assertEqual(dict2[TaskStatus.SUCCESS], 2)
    
    def test_waiting_property(self):
        """Test the waiting property"""
        # Initially all waiting statuses should be 0
        self.assertEqual(self.status_dict.waiting, 0)
        
        # Set some waiting statuses
        self.status_dict[TaskStatus.WAITING_FOR_DEPENDENCIES] = 2
        self.status_dict[TaskStatus.WAITING_FOR_REQUEST_CAPACITY] = 3
        
        # Check waiting count
        self.assertEqual(self.status_dict.waiting, 5)
        
        # Set another waiting status
        self.status_dict[TaskStatus.WAITING_FOR_TOKEN_CAPACITY] = 1
        self.assertEqual(self.status_dict.waiting, 6)
    
    def test_repr(self):
        """Test string representation"""
        repr_str = repr(self.status_dict)
        self.assertTrue(repr_str.startswith("InterviewStatusDictionary({"))
        self.assertTrue(repr_str.endswith("})"))

if __name__ == "__main__":
    unittest.main()