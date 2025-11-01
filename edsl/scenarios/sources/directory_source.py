"""Directory scanning source for ScenarioList creation."""

from __future__ import annotations
import os
import glob
import fnmatch
from typing import List, TYPE_CHECKING

from .base import Source
from ..scenario import Scenario
from ..directory_scanner import DirectoryScanner

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class DirectorySource(Source):
    """Create ScenarioList from files in a directory."""
    
    source_type = "directory"

    def __init__(
        self,
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
        metadata: bool = True,
        ignore_dirs: List[str] = None,
        ignore_files: List[str] = None,
    ):
        self.directory = directory
        self.pattern = pattern
        self.recursive = recursive
        self.metadata = metadata
        self.ignore_dirs = ignore_dirs or []
        self.ignore_files = ignore_files or []

    @classmethod
    def example(cls) -> "DirectorySource":
        """Return an example DirectorySource instance."""
        import tempfile

        # Create a temporary directory for the example
        temp_dir = tempfile.mkdtemp(prefix="edsl_test_")

        # Create some sample files in the directory
        with open(os.path.join(temp_dir, "test1.txt"), "w") as f:
            f.write("Sample content 1")

        with open(os.path.join(temp_dir, "test2.txt"), "w") as f:
            f.write("Sample content 2")

        # Create a subdirectory with a file
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir, exist_ok=True)
        with open(os.path.join(subdir, "test3.txt"), "w") as f:
            f.write("Sample content 3")

        return cls(
            directory=temp_dir,
            pattern="*.txt",
            recursive=True,
            metadata=True,
            ignore_dirs=["__pycache__"],
            ignore_files=["*.pyc"],
        )

    def to_scenario_list(self):
        """Create a ScenarioList from files in a directory."""

        # Set default recursive value
        recursive = self.recursive

        # Handle paths with wildcards properly
        if "*" in self.directory:
            # Handle "**/*.py" patterns (recursive wildcard)
            if "**" in self.directory:
                parts = self.directory.split("**")
                directory = parts[0].rstrip("/\\")
                if not directory:
                    directory = os.getcwd()
                pattern = f"**{parts[1]}" if len(parts) > 1 else "**/*"
                # Force recursive=True for ** patterns
                recursive = True
            # Handle "*.txt" patterns (just wildcard with no directory)
            elif os.path.dirname(self.directory) == "":
                directory = os.getcwd()
                pattern = self.directory
            # Handle "/path/to/dir/*.py" patterns
            else:
                directory = os.path.dirname(self.directory)
                pattern = os.path.basename(self.directory)
        else:
            directory = self.directory
            pattern = self.pattern

        # Check if directory exists
        if not os.path.isdir(directory):
            from ..exceptions import FileNotFoundScenarioError

            raise FileNotFoundScenarioError(f"Directory not found: {directory}")

        # Use glob directly for ** patterns to prevent duplicates
        if "**" in pattern:
            from ..scenario_list import ScenarioList
            from ..file_store import FileStore

            # Handle the pattern directly with glob
            full_pattern = os.path.join(directory, pattern)
            file_paths = glob.glob(full_pattern, recursive=True)

            # Remove duplicates (by converting to a set and back)
            file_paths = list(set(file_paths))

            # Create scenarios
            scenarios = []
            for file_path in file_paths:
                if os.path.isfile(file_path):
                    # Check if file should be ignored
                    file_name = os.path.basename(file_path)
                    if any(
                        fnmatch.fnmatch(file_name, ignore_pattern)
                        for ignore_pattern in self.ignore_files or []
                    ):
                        continue

                    # Create FileStore object
                    file_store = FileStore(file_path)

                    # Create scenario
                    scenario_data = {"file": file_store}

                    # Add metadata if requested
                    if self.metadata:
                        file_stat = os.stat(file_path)
                        scenario_data.update(
                            {
                                "file_path": file_path,
                                "file_name": file_name,
                                "file_size": file_stat.st_size,
                                "file_created": file_stat.st_ctime,
                                "file_modified": file_stat.st_mtime,
                            }
                        )

                    scenarios.append(Scenario(scenario_data))

            return ScenarioList(scenarios)
        else:
            # Use the standard scanning method for non-** patterns
            return DirectoryScanner.scan_directory(
                directory=directory,
                pattern=pattern,
                recursive=recursive,
                metadata=self.metadata,
                ignore_dirs=self.ignore_dirs,
                ignore_files=self.ignore_files,
            )

