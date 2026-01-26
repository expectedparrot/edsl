"""FileStoreList module for managing collections of FileStore objects."""

from typing import Optional, TYPE_CHECKING

from .scenario_list import ScenarioList
from .file_store import FileStore

if TYPE_CHECKING:
    pass


class FileStoreList(ScenarioList):
    """
    A specialized ScenarioList for managing collections of FileStore objects.

    FileStoreList provides the same functionality as ScenarioList but is specifically
    designed to work with FileStore objects. It inherits all the data manipulation
    capabilities from ScenarioList while ensuring that all entries are FileStore objects,
    which affects serialization and data handling.

    The class maintains the same interface as ScenarioList but provides FileStore-specific
    optimizations and validations.

    Attributes:
        data (list): The underlying list containing FileStore objects.
        codebook (dict): Optional metadata describing the fields in the file stores.

    Examples:
        >>> from edsl.scenarios import FileStore, FileStoreList
        >>> import tempfile
        >>>
        >>> # Create some FileStore objects
        >>> with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f1:
        ...     _ = f1.write("Hello World")
        ...     _ = f1.flush()
        ...     fs1 = FileStore(f1.name)
        ...     with tempfile.NamedTemporaryFile(suffix=".txt", mode="w") as f2:
        ...         _ = f2.write("Hello Universe")
        ...         _ = f2.flush()
        ...         fs2 = FileStore(f2.name)
        ...         fsl = FileStoreList([fs1, fs2])
        ...         len(fsl)
        2
    """

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/scenarios.html#filestorelist"
    )

    def __init__(
        self,
        data: Optional[list] = None,
        codebook: Optional[dict[str, str]] = None,
    ):
        """
        Initialize a new FileStoreList with optional data and codebook.

        Args:
            data: Optional list of FileStore objects to initialize with.
            codebook: Optional metadata describing the fields in the file stores.

        Raises:
            TypeError: If any item in data is not a FileStore object.
        """
        # Initialize using parent class
        super().__init__(data=data, codebook=codebook)

    def append(self, item: FileStore) -> None:
        """
        Append a FileStore object to the list.

        Args:
            item: FileStore object to append.

        Raises:
            TypeError: If item is not a FileStore object.
        """
        if not isinstance(item, FileStore):
            raise TypeError(f"Can only append FileStore objects, got {type(item)}")
        super().append(item)

    def insert(self, index: int, item: FileStore) -> None:
        """
        Insert a FileStore object at the specified index.

        Args:
            index: Position to insert at.
            item: FileStore object to insert.

        Raises:
            TypeError: If item is not a FileStore object.
        """
        if not isinstance(item, FileStore):
            raise TypeError(f"Can only insert FileStore objects, got {type(item)}")
        super().insert(index, item)

    def __setitem__(self, index, item: FileStore) -> None:
        """
        Set item at index to a FileStore object.

        Args:
            index: Position to set.
            item: FileStore object to set.

        Raises:
            TypeError: If item is not a FileStore object.
        """
        if not isinstance(item, FileStore):
            raise TypeError(f"Can only set FileStore objects, got {type(item)}")
        super().__setitem__(index, item)

    def to_dict(self, sort: bool = False, add_edsl_version: bool = True) -> dict:
        """
        Convert the FileStoreList to a dictionary representation.

        This method serializes the FileStoreList in a way that preserves
        FileStore-specific information and allows for proper reconstruction.

        Args:
            sort: Whether to sort the file stores before serialization.
            add_edsl_version: Whether to add EDSL version information.

        Returns:
            A dictionary representation of the FileStoreList.
        """
        result = super().to_dict(sort=sort, add_edsl_version=add_edsl_version)

        # Update the class name to reflect FileStoreList
        if add_edsl_version:
            result["edsl_class_name"] = "FileStoreList"

        # Rename 'scenarios' to 'file_stores' for clarity
        if "scenarios" in result:
            result["file_stores"] = result.pop("scenarios")

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "FileStoreList":
        """
        Create a FileStoreList from a dictionary representation.

        Args:
            data: Dictionary containing FileStoreList data.

        Returns:
            A FileStoreList object reconstructed from the dictionary.
        """
        # Handle both 'file_stores' and 'scenarios' keys for backward compatibility
        file_stores_data = data.get("file_stores", data.get("scenarios", []))
        codebook = data.get("codebook", None)

        # Convert each dict back to a FileStore object
        file_stores = [FileStore.from_dict(fs_dict) for fs_dict in file_stores_data]

        return cls(data=file_stores, codebook=codebook)

    def offload(self, inplace: bool = False) -> "FileStoreList":
        """
        Offload base64 content from all FileStore objects to reduce memory usage.

        Args:
            inplace: If True, modify the current FileStoreList. If False, return a new one.

        Returns:
            FileStoreList with offloaded FileStore objects.
        """
        if inplace:
            for file_store in self.data:
                file_store.offload(inplace=True)
            return self
        else:
            offloaded_file_stores = [fs.offload(inplace=False) for fs in self.data]
            return self.__class__(data=offloaded_file_stores, codebook=self.codebook)

    def get_total_size(self) -> int:
        """
        Get the total size of all FileStore objects in bytes.

        Returns:
            Total size in bytes of all file stores.
        """
        return sum(fs.size for fs in self.data)

    def filter_by_extension(self, extension: str) -> "FileStoreList":
        """
        Filter FileStore objects by file extension.

        Args:
            extension: File extension to filter by (e.g., 'txt', 'pdf').

        Returns:
            A new FileStoreList containing only files with the specified extension.
        """
        if not extension.startswith("."):
            extension = "." + extension

        filtered_files = [fs for fs in self.data if fs.suffix == extension.lstrip(".")]
        return self.__class__(data=filtered_files, codebook=self.codebook)

    def filter_by_mime_type(self, mime_type: str) -> "FileStoreList":
        """
        Filter FileStore objects by MIME type.

        Args:
            mime_type: MIME type to filter by (e.g., 'text/plain', 'image/png').

        Returns:
            A new FileStoreList containing only files with the specified MIME type.
        """
        filtered_files = [fs for fs in self.data if fs.mime_type == mime_type]
        return self.__class__(data=filtered_files, codebook=self.codebook)

    def get_images(self) -> "FileStoreList":
        """
        Get all FileStore objects that are images.

        Returns:
            A new FileStoreList containing only image files.
        """
        image_files = [fs for fs in self.data if fs.is_image()]
        return self.__class__(data=image_files, codebook=self.codebook)

    def get_videos(self) -> "FileStoreList":
        """
        Get all FileStore objects that are videos.

        Returns:
            A new FileStoreList containing only video files.
        """
        video_files = [fs for fs in self.data if fs.is_video()]
        return self.__class__(data=video_files, codebook=self.codebook)

    @classmethod
    def example(cls) -> "FileStoreList":
        """Create an example FileStoreList for testing and demonstration.

        Returns:
            A FileStoreList containing two FileStore objects.

        Note:
            Creates files in the current working directory since FileStore
            requires files to exist on disk.
        """
        import os
        import uuid
        import warnings

        # Create files in cwd with unique names
        filename1 = f"filestore_example_{uuid.uuid4().hex[:8]}.txt"
        filename2 = f"filestore_example_{uuid.uuid4().hex[:8]}.txt"

        cwd = os.getcwd()
        warnings.warn(
            f"FileStoreList.example(): Creating example files in working directory: {cwd}",
            stacklevel=2,
        )

        with open(filename1, "w") as f1:
            f1.write("Hello World")

        with open(filename2, "w") as f2:
            f2.write("Hello Universe")

        fs1 = FileStore(filename1)
        fs2 = FileStore(filename2)

        return cls([fs1, fs2])


if __name__ == "__main__":
    import doctest

    doctest.testmod()
