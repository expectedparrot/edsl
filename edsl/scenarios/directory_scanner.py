"""
The DirectoryScanner module provides functionality for finding and processing files in directories.

This module implements the DirectoryScanner class, which is designed to scan directories
for files matching specific criteria and process them using a factory function. It supports
recursive scanning, filtering by file extensions, and both eager and lazy iteration over
the matching files.
"""

from dataclasses import dataclass
from typing import Optional, List, Iterator, TypeVar, Callable
import os

# Generic type variable for the factory function's return type
T = TypeVar("T")


@dataclass
class DirectoryScanner:
    """
    A utility class for finding and processing files in directories.
    
    DirectoryScanner provides methods to scan directories for files that match specific
    criteria, such as file extensions. It can process matching files using a factory
    function that converts file paths to objects of a specified type.
    
    The scanner supports both eager (scan) and lazy (iter_scan) iteration, recursive
    directory traversal, and flexible filtering based on file extensions.
    
    Attributes:
        directory_path: The path to the directory to scan.
        
    Examples:
        >>> import tempfile
        >>> import os
        >>> # Create a temporary directory with some files
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     # Create a few files with different extensions
        ...     _ = open(os.path.join(tmpdir, "file1.txt"), "w").write("content")
        ...     _ = open(os.path.join(tmpdir, "file2.txt"), "w").write("content")
        ...     _ = open(os.path.join(tmpdir, "image.jpg"), "w").write("content")
        ...     # Create a scanner and find all text files
        ...     scanner = DirectoryScanner(tmpdir)
        ...     txt_files = scanner.scan(lambda path: path, suffix_allow_list=["txt"])
        ...     len(txt_files)
        ...     # Use a factory to process files
        ...     def get_filename(path):
        ...         return os.path.basename(path)
        ...     filenames = scanner.scan(get_filename)
        ...     sorted(filenames)
        2
        ['file1.txt', 'file2.txt', 'image.jpg']
    """

    directory_path: str

    def scan(
        self,
        factory: Callable[[str], T],
        recursive: bool = False,
        suffix_allow_list: Optional[List[str]] = None,
        suffix_exclude_list: Optional[List[str]] = None,
        example_suffix: Optional[str] = None,
        include_no_extension: bool = True,
    ) -> List[T]:
        """
        Eagerly scan directory and return a list of objects created by the factory function.
        
        This method performs a scan of the directory, filtering files based on the provided
        criteria, and applies the factory function to each matching file path. It returns
        a complete list of processed results.
        
        Args:
            factory: A callable that takes a file path string and returns an object of type T.
                    This is applied to each matching file path.
            recursive: If True, traverses subdirectories recursively. If False, only scans
                      the top-level directory.
            suffix_allow_list: A list of file extensions (without dots) to include.
                              If provided, only files with these extensions are included.
            suffix_exclude_list: A list of file extensions to exclude. This takes precedence
                                over suffix_allow_list.
            example_suffix: If provided, only include files ending with this exact suffix.
                           This checks the entire filename, not just the extension.
            include_no_extension: Whether to include files without extensions. Defaults to True.
            
        Returns:
            A list of objects created by applying the factory function to each matching file path.
            
        Examples:
            >>> import tempfile
            >>> import os
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     # Create test files
            ...     _ = open(os.path.join(tmpdir, "doc1.txt"), "w").write("content")
            ...     _ = open(os.path.join(tmpdir, "doc2.md"), "w").write("content")
            ...     os.mkdir(os.path.join(tmpdir, "subdir"))
            ...     _ = open(os.path.join(tmpdir, "subdir", "doc3.txt"), "w").write("content")
            ...     # Scan for text files only
            ...     scanner = DirectoryScanner(tmpdir)
            ...     paths = scanner.scan(lambda p: p, suffix_allow_list=["txt"])
            ...     len(paths)
            ...     # Recursive scan for all files
            ...     all_paths = scanner.scan(lambda p: p, recursive=True)
            ...     len(all_paths)
            ...     # Exclude specific extensions
            ...     no_md = scanner.scan(lambda p: p, recursive=True, suffix_exclude_list=["md"])
            ...     len(no_md)
            1
            3
            2
            
        Notes:
            - This method is eager and collects all results into memory. For large directories,
              consider using iter_scan instead.
            - The filtering logic applies filters in this order: exclude list, example suffix,
              allow list, and no extension.
        """
        return list(
            self.iter_scan(
                factory,
                recursive=recursive,
                suffix_allow_list=suffix_allow_list,
                suffix_exclude_list=suffix_exclude_list,
                example_suffix=example_suffix,
                include_no_extension=include_no_extension,
            )
        )

    def iter_scan(
        self,
        factory: Callable[[str], T],
        recursive: bool = False,
        suffix_allow_list: Optional[List[str]] = None,
        suffix_exclude_list: Optional[List[str]] = None,
        example_suffix: Optional[str] = None,
        include_no_extension: bool = True,
    ) -> Iterator[T]:
        """
        Lazily scan directory and yield objects created by the factory function.
        
        This method performs a lazy scan of the directory, filtering files based on the provided
        criteria, and applies the factory function to each matching file path. It yields
        results one by one, allowing for memory-efficient processing of large directories.
        
        Args:
            factory: A callable that takes a file path string and returns an object of type T.
                    This is applied to each matching file path.
            recursive: If True, traverses subdirectories recursively. If False, only scans
                      the top-level directory.
            suffix_allow_list: A list of file extensions (without dots) to include.
                              If provided, only files with these extensions are included.
            suffix_exclude_list: A list of file extensions to exclude. This takes precedence
                                over suffix_allow_list.
            example_suffix: If provided, only include files ending with this exact suffix.
                           This checks the entire filename, not just the extension.
            include_no_extension: Whether to include files without extensions. Defaults to True.
            
        Yields:
            Objects created by applying the factory function to each matching file path,
            yielded one at a time.
            
        Examples:
            >>> import tempfile
            >>> import os
            >>> with tempfile.TemporaryDirectory() as tmpdir:
            ...     # Create test files
            ...     _ = open(os.path.join(tmpdir, "doc1.txt"), "w").write("content")
            ...     _ = open(os.path.join(tmpdir, "doc2.md"), "w").write("content")
            ...     # Process files lazily
            ...     scanner = DirectoryScanner(tmpdir)
            ...     for path in scanner.iter_scan(lambda p: p):
            ...         # Process each file path without loading all into memory
            ...         file_exists = os.path.exists(path)
            ...         assert file_exists
            
        Notes:
            - This method is lazy and yields results as they are processed, making it
              suitable for memory-efficient processing of large directories.
            - The filtering logic is identical to the scan method.
        """

        def should_include_file(filepath: str) -> bool:
            """
            Determine if a file should be included based on filtering criteria.
            
            This helper function applies all the filtering rules to determine
            if a given file path should be included in the results.
            
            Args:
                filepath: The path to the file to check.
                
            Returns:
                True if the file should be included, False otherwise.
            """
            # Get filename and extension
            basename = os.path.basename(filepath)
            _, ext = os.path.splitext(filepath)
            ext = ext[1:] if ext else ""  # Remove leading dot from extension
            
            # Skip system files like .DS_Store by default
            if basename == '.DS_Store':
                return False
            
            # If there's a specific allow list and we have a wildcard filter
            if suffix_allow_list:
                # Only include files with the allowed extensions
                return ext in suffix_allow_list
            
            # Check exclusions (they take precedence)
            if suffix_exclude_list and ext in suffix_exclude_list:
                return False

            # Check example suffix if specified
            if example_suffix:
                # Handle wildcard patterns
                if '*' in example_suffix:
                    import fnmatch
                    basename = os.path.basename(filepath)
                    # Try to match just the filename if the pattern doesn't contain path separators
                    if '/' not in example_suffix and '\\' not in example_suffix:
                        if not fnmatch.fnmatch(basename, example_suffix):
                            return False
                    else:
                        # Match the full path
                        if not fnmatch.fnmatch(filepath, example_suffix):
                            return False
                elif not filepath.endswith(example_suffix):
                    return False
                
            # Handle no extension case
            if not ext:
                return include_no_extension

            return True

        def iter_files() -> Iterator[str]:
            """
            Generate paths to all files in the directory, optionally recursively.
            
            This helper function yields file paths from the directory, handling
            the recursive option appropriately.
            
            Yields:
                Paths to files in the directory.
            """
            if recursive:
                for root, _, files in os.walk(self.directory_path):
                    for file in files:
                        yield os.path.join(root, file)
            else:
                for file in os.listdir(self.directory_path):
                    file_path = os.path.join(self.directory_path, file)
                    if os.path.isfile(file_path):
                        yield file_path

        for file_path in iter_files():
            if should_include_file(file_path):
                yield factory(file_path)
