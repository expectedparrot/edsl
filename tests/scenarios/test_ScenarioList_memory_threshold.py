import pytest
import sys
import os
import random
import string
from unittest.mock import patch
from edsl.scenarios import Scenario, ScenarioList
from edsl.db_list.sql_list import SQLList


def test_scenario_list_memory_threshold_with_mock():
    """
    Test that ScenarioList respects memory threshold and offloads to SQLite.
    
    This test uses mocking to simulate exceeding the memory threshold.
    Since sys.getsizeof() doesn't accurately capture the full size of the list contents,
    we need to mock the _check_memory_threshold method to force offloading.
    """
    # Setup a memory threshold
    memory_threshold = 1024 * 1024  # 1MB
    
    # Create a ScenarioList with the threshold
    scenario_list = ScenarioList(memory_threshold=memory_threshold)
    
    # Verify we start in memory-only mode
    assert scenario_list.is_memory_only
    
    # Add some data
    for i in range(3):
        scenario_list.append(Scenario({"index": i, "data": "test"}))
    
    # The list should still be memory-only at this point
    assert scenario_list.is_memory_only
    assert len(scenario_list) == 3
    
    # Now we'll directly trigger the _offload_to_db method on the underlying SQLList
    scenario_list.data._offload_to_db()
    
    # The list should now be using SQLite storage
    assert not scenario_list.is_memory_only
    
    # Verify all data is still accessible
    assert len(scenario_list) == 3
    assert scenario_list[0]["index"] == 0
    assert scenario_list[2]["index"] == 2
    
    # Add more data after offloading
    scenario_list.append(Scenario({"index": 3, "data": "test"}))
    assert len(scenario_list) == 4
    assert scenario_list[3]["index"] == 3


def test_scenario_list_with_threshold_enforcement():
    """
    Test that ScenarioList memory threshold is enforced when adding data.
    
    This test patches the sys.getsizeof function to return values that will 
    trigger the memory threshold check.
    """
    threshold = 5 * 1024 * 1024  # 5MB
    
    # Original getsizeof function to use for objects other than the memory_list
    original_getsizeof = sys.getsizeof
    
    # Counter to track calls to getsizeof for memory_list
    call_count = [0]
    
    def mock_getsizeof(obj):
        # For the memory_list object in SQLList, return increasing sizes
        # to simulate memory growth and eventually trigger offloading
        if isinstance(obj, list) and hasattr(obj, '__dict__') is False:
            # Check if this is the memory_list in our SQLList
            if call_count[0] < 5:  # First few calls return small size
                call_count[0] += 1
                return threshold // 2  # Below threshold
            else:
                # After a few items, exceed threshold to trigger offloading
                return threshold + 1024  # Above threshold
        # For all other objects, use the original function
        return original_getsizeof(obj)
    
    # Patch sys.getsizeof to use our mock function
    with patch('sys.getsizeof', side_effect=mock_getsizeof):
        # Create ScenarioList with the threshold
        scenario_list = ScenarioList(memory_threshold=threshold)
        
        # Add data until offloading occurs
        for i in range(10):
            scenario_list.append(Scenario({"index": i, "data": "test data"}))
            
            # Check if offloading occurred
            if not scenario_list.is_memory_only:
                # Offloading should happen after call_count exceeds 5
                assert call_count[0] >= 5
                break
        
        # Verify offloading occurred
        assert not scenario_list.is_memory_only, "ScenarioList was not offloaded to SQLite as expected"
        
        # Verify data is still accessible after offloading
        count = len(scenario_list)
        assert count > 0
        assert scenario_list[0]["index"] == 0
        
        # Add more data after offloading
        scenario_list.append(Scenario({"index": count, "data": "more test data"}))
        assert len(scenario_list) == count + 1
        assert scenario_list[count]["index"] == count


def test_scenario_list_memory_threshold_with_patch():
    """
    Test ScenarioList memory threshold behavior with a more realistic approach.
    
    This test creates a ScenarioList with a 5MB threshold, then patches
    the _check_memory_threshold method to directly trigger offloading when
    the list reaches 10 items (simulating exceeding the threshold).
    """
    # Set the memory threshold
    memory_threshold = 5 * 1024 * 1024  # 5MB
    
    # Create scenarios with realistic data
    scenarios = []
    for i in range(20):
        # Each scenario has a medium-sized data field (about 10KB per scenario)
        data = {
            "id": i,
            "title": f"Scenario {i}",
            "description": f"This is a detailed description for scenario {i}",
            "data": "x" * 10 * 1024  # 10KB of data
        }
        scenarios.append(Scenario(data))
    
    # Define a patched version of _check_memory_threshold that triggers offloading
    # after 10 items (simulating a 10MB dataset with 5MB threshold)
    original_check = SQLList._check_memory_threshold
    
    def patched_check_memory_threshold(self):
        if self.is_memory_only and len(self.memory_list) >= 10:
            self._offload_to_db()
    
    # Apply the patch to the method
    with patch.object(SQLList, '_check_memory_threshold', patched_check_memory_threshold):
        # Create a ScenarioList with our threshold
        scenario_list = ScenarioList(memory_threshold=memory_threshold)
        
        # Add the first 5 scenarios (should stay in memory)
        for i in range(5):
            scenario_list.append(scenarios[i])
        
        # Verify it's still in memory
        assert scenario_list.is_memory_only
        assert len(scenario_list) == 5
        
        # Add 5 more scenarios to trigger offloading (now at 10 total)
        for i in range(5, 10):
            scenario_list.append(scenarios[i])
        
        # Verify offloading occurred after adding the 10th item
        assert not scenario_list.is_memory_only, "ScenarioList was not offloaded to SQLite as expected"
        
        # Verify all data is still accessible
        assert len(scenario_list) == 10
        for i in range(10):
            assert scenario_list[i]["id"] == i
        
        # Add remaining scenarios after offloading
        for i in range(10, 20):
            scenario_list.append(scenarios[i])
        
        # Verify all data after offloading
        assert len(scenario_list) == 20
        for i in range(20):
            assert scenario_list[i]["id"] == i
            
        # Test slice access
        middle_slice = scenario_list[5:15]
        assert len(middle_slice) == 10
        assert middle_slice[0]["id"] == 5
        assert middle_slice[9]["id"] == 14


if __name__ == "__main__":
    pytest.main()