import pytest
import os
import tempfile
from pathlib import Path
import shutil

from edsl.scenarios import ScenarioList, FileStore, Scenario


class TestScenarioListFromDirectory:
    """Test suite for the ScenarioList.from_directory method."""

    @pytest.fixture
    def temp_directory(self):
        """Create a temporary directory with various files for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create text files
            for i in range(3):
                with open(os.path.join(tmpdir, f"file{i}.txt"), "w") as f:
                    f.write(f"Content of file {i}")
            
            # Create Python files
            for i in range(2):
                with open(os.path.join(tmpdir, f"script{i}.py"), "w") as f:
                    f.write(f"print('Python script {i}')")
            
            # Create JSON file
            with open(os.path.join(tmpdir, "data.json"), "w") as f:
                f.write('{"key": "value"}')
            
            # Create subdirectory with files
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            
            with open(os.path.join(subdir, "subfile.txt"), "w") as f:
                f.write("Content in subdirectory")
            
            with open(os.path.join(subdir, "subfile.py"), "w") as f:
                f.write("print('Subdirectory Python script')")
            
            yield tmpdir

    def test_from_directory_no_args(self, temp_directory, monkeypatch):
        """Test from_directory with no arguments (using current directory)."""
        # Temporarily change current directory to the temp directory
        original_dir = os.getcwd()
        os.chdir(temp_directory)
        
        try:
            # Call from_directory with no arguments (should use current directory)
            sl = ScenarioList.from_directory()
            
            # Should find all 6 files in the root (not recursive)
            assert len(sl) == 6
            # All items should be Scenario instances with FileStore under the "content" key
            assert all(isinstance(item, Scenario) for item in sl)
            assert all(isinstance(item["content"], FileStore) for item in sl)
            
            # Check if file paths are correct
            file_paths = [os.path.basename(item["content"]["path"]) for item in sl]
            for i in range(3):
                assert f"file{i}.txt" in file_paths
            for i in range(2):
                assert f"script{i}.py" in file_paths
            assert "data.json" in file_paths
            
            # Subdirectory files should not be included
            assert "subfile.txt" not in file_paths
            assert "subfile.py" not in file_paths
        finally:
            os.chdir(original_dir)

    def test_from_directory_with_path(self, temp_directory):
        """Test from_directory with a specific directory path."""
        sl = ScenarioList.from_directory(temp_directory)
        
        # Should find all 6 files in the root (not recursive)
        assert len(sl) == 6
        # All items should be Scenario instances with FileStore under the "content" key
        assert all(isinstance(item, Scenario) for item in sl)
        assert all(isinstance(item["content"], FileStore) for item in sl)

    def test_from_directory_with_wildcard(self, temp_directory):
        """Test from_directory with wildcard pattern."""
        # Get only Python files
        sl = ScenarioList.from_directory(os.path.join(temp_directory, "*.py"))
        
        # Should find 2 Python files in the root
        assert len(sl) == 2
        # All items should be Scenario instances with FileStore under the "content" key
        assert all(isinstance(item, Scenario) for item in sl)
        assert all(isinstance(item["content"], FileStore) for item in sl)
        
        # All files should be Python files
        suffixes = [Path(item["content"]["path"]).suffix for item in sl]
        assert all(suffix == ".py" for suffix in suffixes)

    def test_from_directory_with_just_wildcard(self, temp_directory, monkeypatch):
        """Test from_directory with just a wildcard (no path)."""
        # Temporarily change current directory to the temp directory
        original_dir = os.getcwd()
        os.chdir(temp_directory)
        
        try:
            # Get only text files using just the wildcard
            sl = ScenarioList.from_directory("*.txt")
            
            # Should find 3 text files in the root
            assert len(sl) == 3
            # All files should be text files
            suffixes = [Path(item["content"]["path"]).suffix for item in sl]
            assert all(suffix == ".txt" for suffix in suffixes)
        finally:
            os.chdir(original_dir)

    def test_from_directory_recursive(self, temp_directory):
        """Test from_directory with recursive option."""
        # Get all files recursively
        sl = ScenarioList.from_directory(temp_directory, recursive=True)
        
        # Should find all 8 files (6 in root + 2 in subdir)
        assert len(sl) == 8
        
        # Check if subdirectory files are included
        file_paths = [item["content"]["path"] for item in sl]
        assert os.path.join(temp_directory, "subdir", "subfile.txt") in file_paths
        assert os.path.join(temp_directory, "subdir", "subfile.py") in file_paths

    def test_from_directory_recursive_with_wildcard(self, temp_directory):
        """Test from_directory with recursive option and wildcard."""
        # Get only Python files recursively
        sl = ScenarioList.from_directory(os.path.join(temp_directory, "**/*.py"), recursive=True)
        
        # Should find 3 Python files (2 in root + 1 in subdir)
        assert len(sl) == 3
        
        # Check if subdirectory Python file is included
        file_names = [os.path.basename(item["content"]["path"]) for item in sl]
        assert "subfile.py" in file_names

    def test_from_directory_empty(self):
        """Test from_directory with an empty directory."""
        with tempfile.TemporaryDirectory() as empty_dir:
            sl = ScenarioList.from_directory(empty_dir)
            assert len(sl) == 0

    def test_from_directory_nonexistent(self):
        """Test from_directory with a nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            ScenarioList.from_directory("/path/that/does/not/exist")

    def test_from_directory_custom_key_name(self, temp_directory):
        """Test from_directory with a custom key_name parameter."""
        sl = ScenarioList.from_directory(temp_directory, key_name="file")
        
        # Should find all 6 files in the root (not recursive)
        assert len(sl) == 6
        # All items should be Scenario objects with FileStore under the "file" key
        assert all(isinstance(item, Scenario) for item in sl)
        assert all(isinstance(item["file"], FileStore) for item in sl)
        
        # Check if file paths are accessible through the custom key
        file_paths = [os.path.basename(item["file"]["path"]) for item in sl]
        assert len(file_paths) == 6


if __name__ == "__main__":
    pytest.main()