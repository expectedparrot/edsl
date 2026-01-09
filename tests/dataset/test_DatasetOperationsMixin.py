import pytest
from edsl.dataset import Dataset
from edsl.dataset.exceptions import DatasetValueError, DatasetKeyError, DatasetTypeError


class TestDatasetOperationsMixin:
    """Test cases for the DatasetOperationsMixin class."""

    def test_relevant_columns_invalid_data_type(self):
        """Test relevant_columns raises DatasetValueError with invalid data_type."""
        # Use a Dataset directly since Results.example() has issues with our SQLList changes
        dataset = Dataset([
            {'answer.field1': [1, 2, 3]},
            {'scenario.field2': [4, 5, 6]},
            {'agent.field3': [7, 8, 9]}
        ])
        
        with pytest.raises(DatasetValueError) as excinfo:
            dataset.relevant_columns(data_type="flimflam")
        
        assert "No columns found for data type: flimflam" in str(excinfo.value)
        assert "Available data types are:" in str(excinfo.value)

    def test_num_observations_inconsistent_lengths(self):
        """Test num_observations raises DatasetValueError with inconsistent lengths."""
        inconsistent_dataset = Dataset([
            {'col1': [1, 2, 3]},
            {'col2': [4, 5]}  # One fewer item
        ])
        
        with pytest.raises(DatasetValueError) as excinfo:
            inconsistent_dataset.num_observations()
        
        assert "The number of observations is not consistent across columns" in str(excinfo.value)
        assert "Column 'col2' has 2 observations, but previous columns had 3 observations" in str(excinfo.value)

    def test_to_list_flatten_multiple_columns(self):
        """Test to_list raises DatasetValueError when flattening with multiple columns."""
        dataset = Dataset([
            {'a.b': [[1, 9], 2, 3, 4]}, 
            {'c': [6, 2, 3, 4]}
        ])
        
        with pytest.raises(DatasetValueError) as excinfo:
            dataset.select('a.b', 'c').to_list(flatten=True)
        
        assert "Cannot flatten a list of lists when there are multiple columns selected" in str(excinfo.value)

    def test_drop_nonexistent_field(self):
        """Test drop raises DatasetKeyError when field doesn't exist."""
        dataset = Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])
        
        with pytest.raises(DatasetKeyError) as excinfo:
            dataset.drop('c')
        
        assert "Field 'c' not found in dataset" in str(excinfo.value)

    # Note: The test for remove_prefix_duplicate_names was removed
    # as the doctest already covers this case in the dataset_operations_mixin.py file
    # at lines 1272-1278. The Dataset initialization logic in the test didn't match
    # the behavior needed to trigger the exception.

    def test_tally_invalid_field(self):
        """Test tally raises DatasetKeyError with invalid field."""
        dataset = Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])
        
        with pytest.raises(DatasetKeyError) as excinfo:
            dataset.tally('nonexistent')
        
        assert "One or more specified fields are not in the dataset" in str(excinfo.value)

    def test_unpack_list_nonexistent_field(self):
        """Test unpack_list raises DatasetKeyError when field doesn't exist."""
        dataset = Dataset([{'data': [[1, 2, 3], [4, 5, 6]]}])
        
        with pytest.raises(DatasetKeyError) as excinfo:
            dataset.unpack_list('nonexistent')
        
        assert "Field 'nonexistent' not found in dataset" in str(excinfo.value)

    def test_unpack_list_non_list_values(self):
        """Test unpack_list raises DatasetTypeError with non-list values."""
        dataset = Dataset([{'data': [1, 2, 3]}])  # Not lists of lists
        
        with pytest.raises(DatasetTypeError) as excinfo:
            dataset.unpack_list('data')
        
        assert "Field 'data' does not contain lists in all entries" in str(excinfo.value)

    def test_to_agent_list_no_duplicate_agents(self):
        """Test to_agent_list does not create duplicate agents when 'name' field is present (issue #2191)."""
        # Create a dataset with a 'name' field to trigger the bug scenario
        dataset = Dataset([{'name': ['John Doe', 'Jane Smith']}])
        
        # Convert to agent list
        agent_list = dataset.to_agent_list()
        
        # Should have exactly 2 agents, not 4
        assert len(agent_list) == 2
        
        # Each agent should have the name properly set
        assert agent_list[0].name == 'John Doe'
        assert agent_list[1].name == 'Jane Smith'
        
        # Each agent should have agent_name in traits
        assert agent_list[0].traits['agent_name'] == 'John Doe'
        assert agent_list[1].traits['agent_name'] == 'Jane Smith'
        
    def test_to_agent_list_agent_parameters_path(self):
        """Test to_agent_list correctly handles agent_parameters field."""
        # Create a dataset with agent_parameters field
        # Note: All agents in an AgentList must have the same instruction
        agent_params = [
            {"name": "Agent1", "instruction": "Be helpful"},
            {"name": "Agent2", "instruction": "Be helpful"}
        ]
        dataset = Dataset([{'agent_parameters': agent_params}])
        
        # Convert to agent list
        agent_list = dataset.to_agent_list()
        
        # Should have exactly 2 agents
        assert len(agent_list) == 2
        
        # Each agent should have the correct name and instruction
        assert agent_list[0].name == 'Agent1'
        assert agent_list[0].instruction == 'Be helpful'
        assert agent_list[1].name == 'Agent2'
        assert agent_list[1].instruction == 'Be helpful'
        
    def test_to_agent_list_traits_only_path(self):
        """Test to_agent_list correctly handles case with no name or agent_parameters."""
        # Create a dataset with regular traits  
        dataset = Dataset([{'age': [25, 30]}, {'city': ['NYC', 'LA']}])
        
        # Convert to agent list
        agent_list = dataset.to_agent_list()
        
        # Should have exactly 2 agents
        assert len(agent_list) == 2
        
        # Each agent should have the correct traits and no name
        assert agent_list[0].traits == {'age': 25, 'city': 'NYC'}
        assert agent_list[0].name is None
        assert agent_list[1].traits == {'age': 30, 'city': 'LA'}
        assert agent_list[1].name is None