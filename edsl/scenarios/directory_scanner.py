"""
DirectoryScanner provides functionality for scanning directories and creating ScenarioLists from files.

This module contains the DirectoryScanner class which handles scanning directories,
filtering files based on patterns, and creating Scenario objects from files.
"""

import os
from typing import Optional, List, Callable, Any
from .scenario import Scenario
from .file_store import FileStore
from .exceptions import FileNotFoundScenarioError

class DirectoryScanner:
    """A class for scanning directories and creating ScenarioLists from files."""

    def __init__(self, directory_path: str):
        """Initialize the DirectoryScanner with a directory path.

        Args:
            directory_path (str): The path to the directory to scan.

        Raises:
            FileNotFoundScenarioError: If the specified directory does not exist.
        """
        self.directory_path = directory_path
        if not os.path.isdir(directory_path):
            raise FileNotFoundScenarioError(f"Directory not found: {directory_path}")

    def scan(
        self,
        factory: Callable[[str], Any] = FileStore,
        recursive: bool = False,
        suffix_allow_list: Optional[List[str]] = None,
        example_suffix: Optional[str] = None,
    ) -> List[Any]:
        """Scan the directory and create objects from files.

        Args:
            factory (Callable[[str], Any]): A function that creates objects from file paths.
                Defaults to FileStore.
            recursive (bool): Whether to scan subdirectories recursively.
            suffix_allow_list (Optional[List[str]]): List of file extensions to include.
            example_suffix (Optional[str]): Example suffix pattern for filtering.

        Returns:
            List[Any]: List of objects created by the factory function.
        """
        result = []
        
        def should_include_file(filename: str) -> bool:
            if suffix_allow_list:
                return any(filename.endswith(f".{suffix}") for suffix in suffix_allow_list)
            if example_suffix:
                if example_suffix.startswith("*."):
                    return filename.endswith(example_suffix[1:])
                # Handle other wildcard patterns if needed
            return True

        def scan_dir(current_path: str):
            for entry in os.scandir(current_path):
                if entry.is_file() and should_include_file(entry.name):
                    try:
                        result.append(factory(entry.path))
                    except Exception as e:
                        import warnings
                        warnings.warn(f"Failed to process file {entry.path}: {str(e)}")
                elif entry.is_dir() and recursive:
                    scan_dir(entry.path)

        scan_dir(self.directory_path)
        return result

    @classmethod
    def scan_directory(
        cls,
        directory: str,
        pattern: str = "*",
        recursive: bool = False,
        metadata: bool = True,
        ignore_dirs: List[str] = None,
        ignore_files: List[str] = None,
    ) -> Any:
        """Scan a directory and create a ScenarioList from the files.
        
        Args:
            directory (str): The directory path to scan
            pattern (str): File pattern to match (e.g., "*.txt", "*.{jpg,png}")
            recursive (bool): Whether to scan subdirectories recursively
            metadata (bool): Whether to include file metadata in the scenarios
            ignore_dirs (List[str]): List of directory names to ignore
            ignore_files (List[str]): List of file patterns to ignore
            
        Returns:
            ScenarioList: A ScenarioList containing one scenario per matching file
        """
        from .scenario_list import ScenarioList
        
        # Handle default values
        ignore_dirs = ignore_dirs or []
        ignore_files = ignore_files or []
        
        # Import glob for pattern matching
        import glob
        import fnmatch
        
        # Normalize directory path
        directory = os.path.abspath(directory)
        
        # Prepare result container
        scenarios = []
        
        # Pattern matching function
        def matches_pattern(filename, pattern):
            return fnmatch.fnmatch(filename, pattern)
        
        # File gathering function
        def gather_files(current_dir, current_pattern):
            # Create the full path pattern
            path_pattern = os.path.join(current_dir, current_pattern)
            
            # Get all matching files
            for file_path in glob.glob(path_pattern, recursive=recursive):
                if os.path.isfile(file_path):
                    # Check if file should be ignored
                    file_name = os.path.basename(file_path)
                    if any(matches_pattern(file_name, ignore_pattern) for ignore_pattern in ignore_files):
                        continue
                    
                    # Create FileStore object
                    file_store = FileStore(file_path)
                    
                    # Create scenario
                    scenario_data = {"file": file_store}
                    
                    # Add metadata if requested
                    if metadata:
                        file_stat = os.stat(file_path)
                        scenario_data.update({
                            "file_path": file_path,
                            "file_name": file_name,
                            "file_size": file_stat.st_size,
                            "file_created": file_stat.st_ctime,
                            "file_modified": file_stat.st_mtime,
                        })
                    
                    scenarios.append(Scenario(scenario_data))
        
        # Process the directory
        if recursive:
            for root, dirs, files in os.walk(directory):
                # Skip ignored directories
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                
                # Process files in this directory
                gather_files(root, pattern)
        else:
            gather_files(directory, pattern)
        
        # Return as ScenarioList
        return ScenarioList(scenarios)
        
    @classmethod
    def create_scenario_list(
        cls,
        path: Optional[str] = None,
        recursive: bool = False,
        key_name: str = "content",
        factory: Callable[[str], Any] = FileStore,
        suffix_allow_list: Optional[List[str]] = None,
        example_suffix: Optional[str] = None,
    ) -> Any:
        """Create a ScenarioList from files in a directory.

        Args:
            path (Optional[str]): The directory path to scan, optionally including a wildcard pattern.
            recursive (bool): Whether to scan subdirectories recursively.
            key_name (str): The key to use for the FileStore object in each Scenario.
            factory (Callable[[str], Any]): Factory function to create objects from files.
            suffix_allow_list (Optional[List[str]]): List of file extensions to include.
            example_suffix (Optional[str]): Example suffix pattern for filtering.

        Returns:
            ScenarioList: A ScenarioList containing Scenario objects for all matching files.

        Raises:
            FileNotFoundScenarioError: If the specified directory does not exist.
        """
        # Import here to avoid circular import
        from .scenario_list import ScenarioList
        
        # Handle default case - use current directory
        if path is None:
            directory_path = os.getcwd()
            pattern = None
        else:
            # Special handling for "**" pattern which indicates recursive scanning
            has_recursive_pattern = "**" in path if path else False

            # Check if path contains any wildcard
            if path and ("*" in path):
                # Handle "**/*.ext" pattern - find the directory part before the **
                if has_recursive_pattern:
                    # Extract the base directory by finding the part before **
                    parts = path.split("**")
                    if parts and parts[0]:
                        # Remove trailing slash if any
                        directory_path = parts[0].rstrip("/")
                        if not directory_path:
                            directory_path = os.getcwd()
                        # Get the pattern after **
                        pattern = parts[1] if len(parts) > 1 else None
                        if pattern and pattern.startswith("/"):
                            pattern = pattern[1:]  # Remove leading slash
                    else:
                        directory_path = os.getcwd()
                        pattern = None
                # Handle case where path is just a pattern (e.g., "*.py")
                elif os.path.dirname(path) == "":
                    directory_path = os.getcwd()
                    pattern = os.path.basename(path)
                else:
                    # Split into directory and pattern
                    directory_path = os.path.dirname(path)
                    if not directory_path:
                        directory_path = os.getcwd()
                    pattern = os.path.basename(path)
            else:
                # Path is a directory with no pattern
                directory_path = path
                pattern = None

        # Create scanner and get file stores
        scanner = cls(directory_path)
        
        # Configure suffix filtering
        if pattern:
            if pattern.startswith("*."):
                suffix_allow_list = [pattern[2:]]
            elif "*" in pattern:
                example_suffix = pattern
            else:
                example_suffix = pattern

        # Use scanner to find files and create objects
        file_stores = scanner.scan(
            factory=factory,
            recursive=recursive,
            suffix_allow_list=suffix_allow_list,
            example_suffix=example_suffix,
        )

        # Convert to ScenarioList
        result = ScenarioList()
        for file_store in file_stores:
            result.append(Scenario({key_name: file_store}))
            
        return result
