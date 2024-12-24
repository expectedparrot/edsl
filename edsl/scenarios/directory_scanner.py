# directory_scanner.py
from dataclasses import dataclass
from typing import Optional, List, Iterator, TypeVar, Generic, Callable, Any
import os

T = TypeVar("T")


@dataclass
class DirectoryScanner:
    """
    Scanner for finding files in a directory based on various criteria.
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
        Eagerly scan directory and return list of objects created by factory.

        Args:
            factory: Callable that creates objects from file paths
            recursive: If True, recursively traverse subdirectories
            suffix_allow_list: List of allowed file extensions (without dots)
            suffix_exclude_list: List of excluded file extensions (takes precedence over allow list)
            example_suffix: If provided, only include files with this example suffix
            include_no_extension: Whether to include files without extensions
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
        Lazily scan directory and yield objects created by factory.
        """

        def should_include_file(filepath: str) -> bool:
            _, ext = os.path.splitext(filepath)
            ext = ext[1:] if ext else ""

            # Handle no extension case
            if not ext:
                return include_no_extension

            # Check exclusions first (they take precedence)
            if suffix_exclude_list and ext in suffix_exclude_list:
                return False

            # Check example suffix if specified
            if example_suffix and not filepath.endswith(example_suffix):
                return False

            # Check allowed suffixes if specified
            if suffix_allow_list and ext not in suffix_allow_list:
                return False

            return True

        def iter_files():
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
