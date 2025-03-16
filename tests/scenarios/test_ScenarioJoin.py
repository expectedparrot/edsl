import pytest
from unittest.mock import patch
import io
import sys
from edsl.scenarios import Scenario, ScenarioList
from edsl.scenarios.scenario_join import ScenarioJoin

class TestScenarioJoin:
    def setup_method(self):
        # Create test datasets
        self.s1 = ScenarioList([
            Scenario({'name': 'Alice', 'age': 30}),
            Scenario({'name': 'Bob', 'age': 25}),
            Scenario({'name': 'Eve', 'age': 22})
        ])
        
        self.s2 = ScenarioList([
            Scenario({'name': 'Alice', 'location': 'New York'}),
            Scenario({'name': 'Charlie', 'location': 'Los Angeles'}),
            Scenario({'name': 'Bob', 'location': 'Chicago'})
        ])
        
        # Initialize join object
        self.join = ScenarioJoin(self.s1, self.s2)
    
    def test_init(self):
        # Test initialization
        join = ScenarioJoin(self.s1, self.s2)
        assert join.left == self.s1
        assert join.right == self.s2
    
    def test_validate_join_keys_valid(self):
        # Test with valid join key
        self.join._validate_join_keys('name')
        
        # Test with valid join keys list
        self.join._validate_join_keys(['name'])
    
    def test_validate_join_keys_empty(self):
        # Test with empty join key
        with pytest.raises(ValueError, match="Join keys cannot be empty"):
            self.join._validate_join_keys('')
        
        # Test with empty join keys list
        with pytest.raises(ValueError, match="Join keys cannot be empty"):
            self.join._validate_join_keys([])
    
    def test_validate_join_keys_missing(self):
        # Test with key missing from one list
        with pytest.raises(ValueError, match="Join key.*not found in both ScenarioLists"):
            self.join._validate_join_keys('age_group')
        
        # Test with key missing from one list in a multi-key scenario
        with pytest.raises(ValueError, match="Join key.*not found in both ScenarioLists"):
            self.join._validate_join_keys(['name', 'nonexistent'])
    
    def test_get_key_tuple(self):
        # Test get_key_tuple with single key
        scenario = Scenario({'name': 'Alice', 'age': 30})
        assert ScenarioJoin._get_key_tuple(scenario, ['name']) == ('Alice',)
        
        # Test get_key_tuple with multiple keys
        scenario = Scenario({'name': 'Alice', 'age': 30, 'location': 'New York'})
        assert ScenarioJoin._get_key_tuple(scenario, ['name', 'location']) == ('Alice', 'New York')
    
    def test_create_lookup_dict(self):
        # Test creating lookup dictionary
        lookup_dict = self.join._create_lookup_dict(self.s2, ['name'])
        
        # Check dict keys and values
        assert len(lookup_dict) == 3
        assert lookup_dict[('Alice',)]['location'] == 'New York'
        assert lookup_dict[('Bob',)]['location'] == 'Chicago'
        assert lookup_dict[('Charlie',)]['location'] == 'Los Angeles'
    
    def test_get_all_keys(self):
        # Test getting all unique keys
        all_keys = self.join._get_all_keys()
        assert all_keys == {'name', 'age', 'location'}
    
    def test_handle_matching_scenario_no_conflict(self):
        # Test handling matching scenario with no conflicting keys
        new_scenario = {'name': 'Alice', 'age': 30}
        left_scenario = Scenario({'name': 'Alice', 'age': 30})
        right_scenario = Scenario({'name': 'Alice', 'location': 'New York'})
        
        self.join._handle_matching_scenario(new_scenario, left_scenario, right_scenario, ['name'])
        
        # Check that non-overlapping keys were added
        assert new_scenario == {'name': 'Alice', 'age': 30, 'location': 'New York'}
    
    def test_handle_matching_scenario_with_conflict(self):
        # Test handling matching scenario with a conflicting key that isn't a join key
        new_scenario = {'name': 'Alice', 'age': 30}
        left_scenario = Scenario({'name': 'Alice', 'age': 30})
        right_scenario = Scenario({'name': 'Alice', 'age': 35, 'location': 'New York'})
        
        # Capture print output to verify warning is issued
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        self.join._handle_matching_scenario(new_scenario, left_scenario, right_scenario, ['name'])
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        # Check that warning was issued and left value was kept
        assert "Warning: Conflicting values for key 'age'" in captured_output.getvalue()
        assert new_scenario == {'name': 'Alice', 'age': 30, 'location': 'New York'}
    
    def test_left_join(self):
        # Test left join method
        joined = self.join.left_join('name')
        
        # Check joined result
        assert len(joined) == 3
        
        # Check that Alice has data from both lists
        alice = [s for s in joined if s['name'] == 'Alice'][0]
        assert alice['age'] == 30
        assert alice['location'] == 'New York'
        
        # Check that Bob has data from both lists
        bob = [s for s in joined if s['name'] == 'Bob'][0]
        assert bob['age'] == 25
        assert bob['location'] == 'Chicago'
        
        # Check that Eve has data only from left list
        eve = [s for s in joined if s['name'] == 'Eve'][0]
        assert eve['age'] == 22
        assert eve['location'] is None
    
    def test_left_join_multiple_keys(self):
        # Create data with multiple join keys
        s1 = ScenarioList([
            Scenario({'first_name': 'Alice', 'last_name': 'Smith', 'age': 30}),
            Scenario({'first_name': 'Bob', 'last_name': 'Jones', 'age': 25})
        ])
        
        s2 = ScenarioList([
            Scenario({'first_name': 'Alice', 'last_name': 'Smith', 'location': 'New York'}),
            Scenario({'first_name': 'Alice', 'last_name': 'Johnson', 'location': 'Boston'})
        ])
        
        join = ScenarioJoin(s1, s2)
        joined = join.left_join(['first_name', 'last_name'])
        
        # Check joined result
        assert len(joined) == 2
        
        # Check that only the exact match has data from both lists
        alice = [s for s in joined if s['first_name'] == 'Alice'][0]
        assert alice['age'] == 30
        assert alice['location'] == 'New York'
        
        # Check that Bob has no location (no match in right list)
        bob = [s for s in joined if s['first_name'] == 'Bob'][0]
        assert bob['age'] == 25
        assert bob['location'] is None
    
    def test_create_joined_scenarios(self):
        # Test creating joined scenarios
        by_keys = ['name']
        other_dict = self.join._create_lookup_dict(self.s2, by_keys)
        all_keys = self.join._get_all_keys()
        
        joined_scenarios = self.join._create_joined_scenarios(by_keys, other_dict, all_keys)
        
        # Check number of scenarios
        assert len(joined_scenarios) == 3
        
        # Check all scenarios are instances of Scenario
        for scenario in joined_scenarios:
            assert isinstance(scenario, Scenario)

if __name__ == "__main__":
    pytest.main()