import json
import os
import pytest
from unittest.mock import MagicMock
import tempfile
from edsl.data.Cache import Cache

@pytest.fixture
def mock_data():
    """Provides mock data for testing."""
    return {"key1": {"subkey": "value1"}, "key2": {"subkey": "value2"}}

@pytest.fixture
def temp_filename(tmp_path):
    """Generates a temporary filename for testing."""
    return tmp_path / "test_output.jsonl"

def test_write_jsonl_with_mock_data(mock_data, temp_filename):
    # Instance of the class containing the write_jsonl method
    instance = Cache()
    # Mock the data attribute with the provided mock data
    instance.data = mock_data

    temp_dir = tempfile.gettempdir()

    # Call the method under test
    instance.write_jsonl(str(temp_filename))
    
    # Verify the file contents
    with open(temp_filename, 'r') as f:
        lines = f.readlines()
    
    # There should be as many lines as items in mock_data
    assert len(lines) == len(mock_data)
    
    # Convert each line back to dict and compare with original data
    for line in lines:
        item = json.loads(line.strip())
        key, value = next(iter(item.items()))
        assert mock_data[key] == value


