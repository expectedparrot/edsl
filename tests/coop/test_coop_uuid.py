import unittest

from edsl.surveys import Survey
from edsl.results import Results
from edsl.jobs import Jobs
from edsl.scenarios import ScenarioList
from edsl.notebooks import Notebook
import pytest
import time 
class TestCoopUUIDFromObjectHash(unittest.TestCase):
    """Test getting UUID from object hash for various EDSL objects."""
    @pytest.mark.coop
    def test_push_get_uuid_pull(self):
        """Test pushing objects to remote, getting their UUIDs, and pulling them back."""
        # Create test objects
        survey = Survey.example()
        results = Results.example()
        scenario_list = ScenarioList.example()
        notebook = Notebook.example()
        
        test_objects = [survey, results, scenario_list, notebook]
        
        for obj in test_objects:
            # Push the object to remote
            response = obj.push(description=f"Test {obj.__class__.__name__}", visibility="unlisted")
            
            # Get UUID from the push response
            uuid_from_push = response["uuid"]
            # Get UUID using the get_uuid method (which uses object hash)
            uuid_from_hash = obj.get_uuid()
            
            assert uuid_from_hash != None, f"UUID from hash is None for {obj.__class__.__name__}"
            # Pull the object from remote using UUID
            time.sleep(2)
            pulled_obj = obj.pull(uuid_from_push)
            
            # Verify pulled object has same hash
            self.assertEqual(pulled_obj.get_hash(), obj.get_hash())
            


if __name__ == "__main__":
    unittest.main()
