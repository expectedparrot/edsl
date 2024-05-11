import os
import json
from edsl import Results
import pytest

def load_json_data_from_directory(base_dir):
    all_results = []  # Initialize list to store Results objects
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == 'data.json':
                full_path = os.path.join(root, file)
                with open(full_path, 'r') as json_file:
                    data = json.load(json_file)
                    results = Results.from_dict(data)
                    all_results.append(results)
    return all_results

@pytest.fixture
def data_directory():
    # Returns the path to the data directory relative to the test script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data/")

def test_data_load(data_directory):
    # Call the function and get the loaded data
    loaded_data = load_json_data_from_directory(data_directory)
    
    # Assertions to ensure data is loaded correctly
    assert isinstance(loaded_data, list), "The loaded data should be a list"
    assert all(isinstance(item, Results) for item in loaded_data), "All items in the list should be Results instances"
    assert len(loaded_data) > 0, "Data list should not be empty"  # Change this as per actual expected conditions

# Optionally, you can use more specific tests to verify the contents of the loaded data.
