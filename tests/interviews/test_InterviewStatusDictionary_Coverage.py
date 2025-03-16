import unittest
from edsl.interviews.interview_status_dictionary import InterviewStatusDictionary
from edsl.tasks.task_status_enum import TaskStatus

class TestInterviewStatusDictionaryCoverage(unittest.TestCase):
    def setUp(self):
        """Set up for tests"""
        self.status_dict = InterviewStatusDictionary()
    
    def test_initialization(self):
        """Test initialization"""
        # Should start empty
        self.assertEqual(len(self.status_dict), 0)
        
        # Initialize with values
        status_dict = InterviewStatusDictionary({
            "q1": TaskStatus.NOT_STARTED,
            "q2": TaskStatus.SUCCESS
        })
        
        self.assertEqual(len(status_dict), 2)
        self.assertEqual(status_dict["q1"], TaskStatus.NOT_STARTED)
        self.assertEqual(status_dict["q2"], TaskStatus.SUCCESS)
    
    def test_set_and_get_items(self):
        """Test setting and getting items"""
        # Set an item
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        
        # Get the item
        self.assertEqual(self.status_dict["q1"], TaskStatus.NOT_STARTED)
        
        # Set another item
        self.status_dict["q2"] = TaskStatus.SUCCESS
        
        # Check both items
        self.assertEqual(self.status_dict["q1"], TaskStatus.NOT_STARTED)
        self.assertEqual(self.status_dict["q2"], TaskStatus.SUCCESS)
    
    def test_contains(self):
        """Test the contains operation"""
        # Add an item
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        
        # Check contains
        self.assertIn("q1", self.status_dict)
        self.assertNotIn("q2", self.status_dict)
    
    def test_iteration(self):
        """Test iteration through the dictionary"""
        # Add some items
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        self.status_dict["q2"] = TaskStatus.SUCCESS
        
        # Iterate and check keys
        keys = list(self.status_dict)
        self.assertIn("q1", keys)
        self.assertIn("q2", keys)
    
    def test_dictionary_methods(self):
        """Test that it supports standard dictionary methods"""
        # Add some items
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        self.status_dict["q2"] = TaskStatus.SUCCESS
        
        # Test keys, values, items
        self.assertEqual(set(self.status_dict.keys()), {"q1", "q2"})
        self.assertEqual(set(self.status_dict.values()), {TaskStatus.NOT_STARTED, TaskStatus.SUCCESS})
        self.assertEqual(set(self.status_dict.items()), {("q1", TaskStatus.NOT_STARTED), ("q2", TaskStatus.SUCCESS)})
    
    def test_history_tracking(self):
        """Test that history is tracked correctly"""
        # Set an item
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        
        # Change its status
        self.status_dict["q1"] = TaskStatus.WAITING_FOR_DEPENDENCIES
        self.status_dict["q1"] = TaskStatus.SUCCESS
        
        # Check the history
        history = self.status_dict.get_history("q1")
        
        # Should have 3 entries
        self.assertEqual(len(history), 3)
        
        # In the correct order
        self.assertEqual(history[0]["value"], TaskStatus.NOT_STARTED)
        self.assertEqual(history[1]["value"], TaskStatus.WAITING_FOR_DEPENDENCIES)
        self.assertEqual(history[2]["value"], TaskStatus.SUCCESS)
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        # Add some items
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        self.status_dict["q2"] = TaskStatus.SUCCESS
        
        # Convert to dict
        dict_repr = self.status_dict.to_dict()
        
        # Check it has the expected structure
        self.assertIn("current_state", dict_repr)
        self.assertIn("history", dict_repr)
        
        # Check current state
        self.assertEqual(dict_repr["current_state"]["q1"], 1)  # TaskStatus.NOT_STARTED value
        self.assertEqual(dict_repr["current_state"]["q2"], 8)  # TaskStatus.SUCCESS value
        
        # Check history
        self.assertEqual(len(dict_repr["history"]["q1"]), 1)
        self.assertEqual(len(dict_repr["history"]["q2"]), 1)
    
    def test_from_dict(self):
        """Test restoration from dictionary"""
        # Create a dictionary representation
        dict_repr = {
            "current_state": {
                "q1": 1,  # TaskStatus.NOT_STARTED
                "q2": 8   # TaskStatus.SUCCESS
            },
            "history": {
                "q1": [{"value": 1, "log_time": 0}],
                "q2": [{"value": 8, "log_time": 0}]
            }
        }
        
        # Create from dict
        status_dict = InterviewStatusDictionary.from_dict(dict_repr)
        
        # Check it has the expected values
        self.assertEqual(status_dict["q1"], TaskStatus.NOT_STARTED)
        self.assertEqual(status_dict["q2"], TaskStatus.SUCCESS)
        
        # Check history
        history_q1 = status_dict.get_history("q1")
        history_q2 = status_dict.get_history("q2")
        
        self.assertEqual(len(history_q1), 1)
        self.assertEqual(len(history_q2), 1)
        self.assertEqual(history_q1[0]["value"], TaskStatus.NOT_STARTED)
        self.assertEqual(history_q2[0]["value"], TaskStatus.SUCCESS)
    
    def test_all_completed(self):
        """Test the all_completed method"""
        # Empty dict should return True (vacuously all completed)
        self.assertTrue(self.status_dict.all_completed())
        
        # Add a non-completed task
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        self.assertFalse(self.status_dict.all_completed())
        
        # Add a completed task
        self.status_dict["q2"] = TaskStatus.SUCCESS
        self.assertFalse(self.status_dict.all_completed())
        
        # Complete all tasks
        self.status_dict["q1"] = TaskStatus.SUCCESS
        self.assertTrue(self.status_dict.all_completed())
    
    def test_get_completed_tasks(self):
        """Test getting completed tasks"""
        # Add a mix of completed and uncompleted tasks
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        self.status_dict["q2"] = TaskStatus.SUCCESS
        self.status_dict["q3"] = TaskStatus.API_CALL_IN_PROGRESS
        self.status_dict["q4"] = TaskStatus.SUCCESS
        
        # Get completed tasks
        completed = self.status_dict.get_completed_tasks()
        
        # Should have q2 and q4
        self.assertEqual(len(completed), 2)
        self.assertIn("q2", completed)
        self.assertIn("q4", completed)
    
    def test_get_uncompleted_tasks(self):
        """Test getting uncompleted tasks"""
        # Add a mix of completed and uncompleted tasks
        self.status_dict["q1"] = TaskStatus.NOT_STARTED
        self.status_dict["q2"] = TaskStatus.SUCCESS
        self.status_dict["q3"] = TaskStatus.API_CALL_IN_PROGRESS
        self.status_dict["q4"] = TaskStatus.SUCCESS
        
        # Get uncompleted tasks
        uncompleted = self.status_dict.get_uncompleted_tasks()
        
        # Should have q1 and q3
        self.assertEqual(len(uncompleted), 2)
        self.assertIn("q1", uncompleted)
        self.assertIn("q3", uncompleted)

if __name__ == "__main__":
    unittest.main()