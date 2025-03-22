"""Base class for all classes in the package.

This module provides the foundation for all classes in the EDSL framework, implementing core
functionality such as serialization, persistence, rich representation, and object comparison.
The Base class combines several mixins that provide different aspects of functionality:
    - RepresentationMixin: Handles object display and visualization
    - PersistenceMixin: Manages saving/loading objects and cloud operations
    - DiffMethodsMixin: Enables object comparison and differencing
    - HashingMixin: Provides consistent hashing and equality operations

Classes inheriting from Base get a rich set of capabilities "for free" including
JSON/YAML serialization, file persistence, pretty printing, and object comparison.
"""

from abc import ABC, abstractmethod, ABCMeta
import gzip
import json
from typing import Any, Optional, Union
from uuid import UUID
import difflib
from typing import Dict, Tuple
from collections import UserList
import inspect

from .. import logger

class BaseException(Exception):
    """Base exception class for all EDSL exceptions.
    
    This class extends the standard Python Exception class to provide more helpful error messages
    by including links to relevant documentation and example notebooks when available.
    
    Attributes:
        relevant_doc: URL to documentation explaining this type of exception
        relevant_notebook: Optional URL to a notebook with usage examples
    """
    relevant_doc = "https://docs.expectedparrot.com/"

    def __init__(self, message, *, show_docs=True, log_level="error"):
        """Initialize a new BaseException with formatted error message.
        
        Args:
            message: The primary error message
            show_docs: If True, append documentation links to the error message
            log_level: The logging level to use ("debug", "info", "warning", "error", "critical")
        """
        # Format main error message
        formatted_message = [message.strip()]

        # Add documentation links if requested
        if show_docs:
            if hasattr(self, "relevant_doc"):
                formatted_message.append(
                    f"\nFor more information, see:\n{self.relevant_doc}"
                )
            if hasattr(self, "relevant_notebook"):
                formatted_message.append(
                    f"\nFor a usage example, see:\n{self.relevant_notebook}"
                )

        # Join with double newlines for clear separation
        final_message = "\n\n".join(formatted_message)
        super().__init__(final_message)
        
        # Log the exception
        if log_level == "debug":
            logger.debug(f"{self.__class__.__name__}: {message}")
        elif log_level == "info":
            logger.info(f"{self.__class__.__name__}: {message}")
        elif log_level == "warning":
            logger.warning(f"{self.__class__.__name__}: {message}")
        elif log_level == "error":
            logger.error(f"{self.__class__.__name__}: {message}")
        elif log_level == "critical":
            logger.critical(f"{self.__class__.__name__}: {message}")
        # Default to error if an invalid log level is provided


class DisplayJSON:
    """Display a dictionary as JSON."""

    def __init__(self, input_dict: dict):
        self.text = json.dumps(input_dict, indent=4)

    def __repr__(self):
        return self.text


class DisplayYAML:
    """Display a dictionary as YAML."""

    def __init__(self, input_dict: dict):
        import yaml

        self.text = yaml.dump(input_dict)

    def __repr__(self):
        return self.text


class PersistenceMixin:
    """Mixin for saving and loading objects to and from files.
    
    This mixin provides methods for serializing objects to various formats (JSON, YAML),
    saving to and loading from files, and interacting with cloud storage. It enables
    persistence operations like duplicating objects and uploading/downloading from the
    EDSL cooperative platform.
    """

    def duplicate(self, add_edsl_version=False):
        """Create and return a deep copy of the object.
        
        Args:
            add_edsl_version: Whether to include EDSL version information in the duplicated object
            
        Returns:
            A new instance of the same class with identical properties
        """
        return self.from_dict(self.to_dict(add_edsl_version=False))
    
    @classmethod
    def help(cls):
        """Display the class documentation string.
        
        This is a convenience method to quickly access the docstring of the class.
        
        Returns:
            None, but prints the class docstring to stdout
        """
        print(cls.__doc__)

    def push(
        self,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = "unlisted",
        expected_parrot_url: Optional[str] = None,
    ):
        """Upload this object to the EDSL cooperative platform.
        
        This method serializes the object and posts it to the EDSL coop service,
        making it accessible to others or for your own use across sessions.
        
        Args:
            description: Optional text description of the object
            alias: Optional human-readable identifier for the object
            visibility: Access level setting ("private", "unlisted", or "public")
            expected_parrot_url: Optional custom URL for the coop service
            
        Returns:
            The response from the coop service containing the object's unique identifier
        """
        from edsl.coop import Coop

        c = Coop(url=expected_parrot_url)
        return c.create(self, description, alias, visibility)

    def to_yaml(self, add_edsl_version=False, filename: str = None) -> Union[str, None]:
        """Convert the object to YAML format.
        
        Serializes the object to YAML format and optionally writes it to a file.
        
        Args:
            add_edsl_version: Whether to include EDSL version information
            filename: If provided, write the YAML to this file path
            
        Returns:
            str: The YAML string representation if no filename is provided
            None: If written to file
        """
        import yaml

        output = yaml.dump(self.to_dict(add_edsl_version=add_edsl_version))
        if not filename:
            return output

        with open(filename, "w") as f:
            f.write(output)

    @classmethod
    def from_yaml(cls, yaml_str: Optional[str] = None, filename: Optional[str] = None):
        """Create an instance from YAML data.
        
        Deserializes a YAML string or file into a new instance of the class.
        
        Args:
            yaml_str: YAML string containing object data
            filename: Path to a YAML file containing object data
            
        Returns:
            A new instance of the class populated with the deserialized data
            
        Raises:
            BaseValueError: If neither yaml_str nor filename is provided
        """
        if yaml_str is None and filename is not None:
            with open(filename, "r") as f:
                yaml_str = f.read()
                return cls.from_yaml(yaml_str=yaml_str)
        elif yaml_str and filename is None:
            import yaml

            d = yaml.load(yaml_str, Loader=yaml.FullLoader)
            return cls.from_dict(d)
        else:
            from edsl.base.exceptions import BaseValueError
            raise BaseValueError("Either yaml_str or filename must be provided.")

    def create_download_link(self):
        """Generate a downloadable link for this object.
        
        Creates a temporary file containing the serialized object and generates
        a download link that can be shared with others.
        
        Returns:
            str: A URL that can be used to download the object
        """
        from tempfile import NamedTemporaryFile
        from edsl.scenarios import FileStore

        with NamedTemporaryFile(suffix=".json.gz") as f:
            self.save(f.name)
            print(f.name)
            fs = FileStore(path=f.name)
        return fs.create_link()

    @classmethod
    def pull(
        cls,
        url_or_uuid: Optional[Union[str, UUID]] = None,
    ):
        """Pull the object from coop.

        Args:
            url_or_uuid: Either a UUID string or a URL pointing to the object
        """
        from edsl.coop import Coop
        from edsl.coop import ObjectRegistry

        object_type = ObjectRegistry.get_object_type_by_edsl_class(cls)
        coop = Coop()

        return coop.get(url_or_uuid, expected_object_type=object_type)

    @classmethod
    def delete(cls, url_or_uuid: Union[str, UUID]) -> None:
        """Delete the object from coop."""
        from edsl.coop import Coop

        coop = Coop()

        return coop.delete(url_or_uuid)

    @classmethod
    def patch_cls(
        cls,
        url_or_uuid: Union[str, UUID],
        description: Optional[str] = None,
        value: Optional[Any] = None,
        visibility: Optional[str] = None,
    ):
        """
        Patch an uploaded object's attributes (class method version).
        - `description` changes the description of the object on Coop
        - `value` changes the value of the object on Coop. **has to be an EDSL object**
        - `visibility` changes the visibility of the object on Coop
        """
        from edsl.coop import Coop

        coop = Coop()

        return coop.patch(
            url_or_uuid=url_or_uuid,
            description=description,
            value=value,
            visibility=visibility,
        )

    class ClassOrInstanceMethod:
        """Descriptor that allows a method to be called as both a class method and an instance method."""

        def __init__(self, func):
            self.func = func

        def __get__(self, obj, objtype=None):
            if obj is None:
                # Called as a class method
                def wrapper(*args, **kwargs):
                    return self.func(objtype, *args, **kwargs)

                return wrapper
            else:
                # Called as an instance method
                def wrapper(*args, **kwargs):
                    return self.func(obj, *args, **kwargs)

                return wrapper

    @ClassOrInstanceMethod
    def patch(
        self_or_cls,
        url_or_uuid: Union[str, UUID],
        description: Optional[str] = None,
        value: Optional[Any] = None,
        visibility: Optional[str] = None,
    ):
        """
        Patch an uploaded object's attributes.

        When called as a class method:
        - Requires explicit `value` parameter

        When called as an instance method:
        - Uses the instance itself as the `value` parameter

        Parameters:
        - `id_or_url`: ID or URL of the object to patch
        - `description`: changes the description of the object on Coop
        - `value`: changes the value of the object on Coop (required for class method)
        - `visibility`: changes the visibility of the object on Coop
        """

        # Check if this is being called as a class method
        if isinstance(self_or_cls, type):
            # This is a class method call
            cls = self_or_cls
            return cls.patch_cls(
                url_or_uuid=url_or_uuid,
                description=description,
                value=value,
                visibility=visibility,
            )
        else:
            # This is an instance method call
            instance = self_or_cls
            cls_type = instance.__class__

            # Use the instance as the value if not explicitly provided
            if value is None:
                value = instance
            else:
                pass

            return cls_type.patch_cls(
                url_or_uuid=url_or_uuid,
                description=description,
                value=value,
                visibility=visibility,
            )

    @classmethod
    def search(cls, query):
        """Search for objects on coop."""
        from edsl.coop import Coop

        c = Coop()
        return c.search(cls, query)

    def store(self, d: dict, key_name: Optional[str] = None):
        if key_name is None:
            index = len(d)
        else:
            index = key_name
        d[index] = self

    def save(self, filename, compress=True):
        """Save the object to a file as JSON with optional compression.

        Serializes the object to JSON and writes it to the specified file.
        By default, the file will be compressed using gzip. File extensions
        are handled automatically.
        
        Args:
            filename: Path where the file should be saved
            compress: If True, compress the file using gzip (default: True)
            
        Returns:
            None
            
        Examples:
            >>> obj.save("my_object.json.gz")  # Compressed
            >>> obj.save("my_object.json", compress=False)  # Uncompressed
        """
        logger.debug(f"Saving {self.__class__.__name__} to file: {filename}")
        
        if filename.endswith("json.gz"):
            filename = filename[:-8]
        if filename.endswith("json"):
            filename = filename[:-5]

        try:
            if compress:
                full_file_name = filename + ".json.gz"
                with gzip.open(full_file_name, "wb") as f:
                    f.write(json.dumps(self.to_dict()).encode("utf-8"))
            else:
                full_file_name = filename + ".json"
                with open(filename + ".json", "w") as f:
                    f.write(json.dumps(self.to_dict()))
                    
            logger.info(f"Successfully saved {self.__class__.__name__} to {full_file_name}")
            print("Saved to", full_file_name)
        except Exception as e:
            logger.error(f"Failed to save {self.__class__.__name__} to {filename}: {str(e)}")
            raise

    @staticmethod
    def open_compressed_file(filename):
        """Read and parse a compressed JSON file.
        
        Args:
            filename: Path to a gzipped JSON file
            
        Returns:
            dict: The parsed JSON content
        """
        with gzip.open(filename, "rb") as f:
            file_contents = f.read()
            file_contents_decoded = file_contents.decode("utf-8")
            d = json.loads(file_contents_decoded)
        return d

    @staticmethod
    def open_regular_file(filename):
        """Read and parse an uncompressed JSON file.
        
        Args:
            filename: Path to a JSON file
            
        Returns:
            dict: The parsed JSON content
        """
        with open(filename, "r") as f:
            d = json.loads(f.read())
        return d

    @classmethod
    def load(cls, filename):
        """Load the object from a JSON file (compressed or uncompressed).
        
        This method deserializes an object from a file, automatically detecting
        whether the file is compressed with gzip or not.
        
        Args:
            filename: Path to the file to load
            
        Returns:
            An instance of the class populated with data from the file
            
        Raises:
            Various exceptions may be raised if the file doesn't exist or contains invalid data
        """
        logger.debug(f"Loading {cls.__name__} from file: {filename}")
        
        try:
            if filename.endswith("json.gz"):
                d = cls.open_compressed_file(filename)
                logger.debug(f"Loaded compressed file {filename}")
            elif filename.endswith("json"):
                d = cls.open_regular_file(filename)
                logger.debug(f"Loaded regular file {filename}")
            else:
                try:
                    logger.debug(f"Attempting to load as compressed file: {filename}.json.gz")
                    d = cls.open_compressed_file(filename + ".json.gz")
                except Exception as e:
                    logger.debug(f"Failed to load as compressed file, trying regular: {e}")
                    d = cls.open_regular_file(filename + ".json")
                # finally:
                #    raise ValueError("File must be a json or json.gz file")

            logger.info(f"Successfully loaded {cls.__name__} from {filename}")
            return cls.from_dict(d)
        except Exception as e:
            logger.error(f"Failed to load {cls.__name__} from {filename}: {str(e)}")
            raise


class RegisterSubclassesMeta(ABCMeta):
    """Metaclass for automatically registering all subclasses.
    
    This metaclass maintains a registry of all classes that inherit from Base,
    allowing for dynamic discovery of available classes and capabilities like
    automatic deserialization. When a new class is defined with Base as its
    parent, this metaclass automatically adds it to the registry.
    """

    _registry = {}

    def __init__(cls, name, bases, nmspc):
        """Register the class in the registry upon creation.
        
        Args:
            name: The name of the class being created
            bases: The base classes of the class being created
            nmspc: The namespace of the class being created
        """
        super(RegisterSubclassesMeta, cls).__init__(name, bases, nmspc)
        if cls.__name__ != "Base":
            RegisterSubclassesMeta._registry[cls.__name__] = cls

    @staticmethod
    def get_registry(exclude_classes: Optional[list] = None):
        """Get the registry of all registered subclasses.
        
        Args:
            exclude_classes: Optional list of class names to exclude from the result
            
        Returns:
            dict: A dictionary mapping class names to class objects
        """
        if exclude_classes is None:
            exclude_classes = []
        return {
            k: v
            for k, v in dict(RegisterSubclassesMeta._registry).items()
            if k not in exclude_classes
        }


class DiffMethodsMixin:
    """Mixin that adds the ability to compute differences between objects.
    
    This mixin provides operator overloads that enable convenient comparison and
    differencing between objects of the same class.
    """
    
    def __sub__(self, other):
        """Calculate the difference between this object and another.
        
        This overloads the subtraction operator (-) to provide an intuitive way
        to compare objects and find their differences.
        
        Args:
            other: Another object to compare against this one
            
        Returns:
            BaseDiff: An object representing the differences between the two objects
        """
        from edsl.base import BaseDiff

        return BaseDiff(self, other)


def is_iterable(obj):
    """Check if an object is iterable.
    
    Args:
        obj: The object to check
        
    Returns:
        bool: True if the object is iterable, False otherwise
    """
    try:
        iter(obj)
    except TypeError:
        return False
    return True


class RepresentationMixin:
    """Mixin that provides rich display and representation capabilities.
    
    This mixin enhances objects with methods for displaying their contents in various
    formats including JSON, HTML tables, and rich terminal output. It improves the
    user experience when working with EDSL objects in notebooks and terminals.
    """
    
    def json(self):
        """Get a parsed JSON representation of this object.
        
        Returns:
            dict: The object's data as a Python dictionary
        """
        return json.loads(json.dumps(self.to_dict(add_edsl_version=False)))

    def to_dataset(self):
        """Convert this object to a Dataset for advanced data operations.
        
        Returns:
            Dataset: A Dataset object containing this object's data
        """
        from edsl.dataset import Dataset

        return Dataset.from_edsl_object(self)

    def view(self):
        """Display an interactive visualization of this object.
        
        Returns:
            The result of the dataset's view method
        """
        return self.to_dataset().view()

    # def print(self, format="rich"):
    #     return self.to_dataset().table()

    def display_dict(self):
        """Create a flattened dictionary representation for display purposes.
        
        This method creates a flattened view of nested structures using colon notation
        in keys to represent hierarchy.
        
        Returns:
            dict: A flattened dictionary suitable for display
        """
        display_dict = {}
        d = self.to_dict(add_edsl_version=False)
        for key, value in d.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    display_dict[f"{key}:{k}"] = v
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    display_dict[f"{key}:{i}"] = v
            else:
                display_dict[key] = value
        return display_dict

    def print(self, format="rich"):
        """Print a formatted table representation of this object.
        
        Args:
            format: The output format (currently only 'rich' is supported)
            
        Returns:
            None, but prints a formatted table to the console
        """
        from rich.table import Table
        from rich.console import Console

        table = Table(title=self.__class__.__name__)
        table.add_column("Key", style="bold")
        table.add_column("Value", style="bold")

        for key, value in self.display_dict().items():
            table.add_row(key, str(value))

        console = Console(record=True)
        console.print(table)

    def _repr_html_(self):
        """Generate an HTML representation for Jupyter notebooks.
        
        This method is automatically called by Jupyter to render the object
        as HTML in notebook cells.
        
        Returns:
            str: HTML representation of the object
        """
        from edsl.dataset.display.table_display import TableDisplay
        
        if hasattr(self, "_summary"):
            summary_dict = self._summary()
            summary_line = "".join([f" {k}: {v};" for k, v in summary_dict.items()])
            class_name = self.__class__.__name__
            docs = getattr(self, "__documentation__", "")
            return (
                "<p>"
                + f"<a href='{docs}'>{class_name}</a>"
                + summary_line
                + "</p>"
                + self.table()._repr_html_()
            )
        else:
            class_name = self.__class__.__name__
            documentation = getattr(self, "__documentation__", "")
            summary_line = "<p>" + f"<a href='{documentation}'>{class_name}</a>" + "</p>"
            display_dict = self.display_dict()
            return (
                summary_line
                + TableDisplay.from_dictionary_wide(display_dict)._repr_html_()
            )

    def __str__(self):
        """Return the string representation of the object.
        
        Returns:
            str: String representation of the object
        """
        return self.__repr__()


class HashingMixin:
    """Mixin that provides consistent hashing and equality operations.
    
    This mixin implements __hash__ and __eq__ methods to enable using EDSL objects
    in sets and as dictionary keys. The hash is based on the object's serialized content,
    so two objects with identical content will be considered equal.
    """
    
    def __hash__(self) -> int:
        """Generate a hash value for this object based on its content.
        
        The hash is computed from the serialized dictionary representation of the object,
        excluding any version information.
        
        Returns:
            int: A hash value for the object
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    def __eq__(self, other):
        """Compare this object with another for equality.
        
        Two objects are considered equal if they have the same hash value,
        which means they have identical content.
        
        Args:
            other: Another object to compare with this one
            
        Returns:
            bool: True if the objects are equal, False otherwise
        """
        return hash(self) == hash(other)


class Base(
    RepresentationMixin,
    PersistenceMixin,
    DiffMethodsMixin,
    HashingMixin,
    ABC,
    metaclass=RegisterSubclassesMeta,
):
    """Base class for all classes in the EDSL package.
    
    This abstract base class combines several mixins to provide a rich set of functionality
    to all EDSL objects. It defines the core interface that all EDSL objects must implement,
    including serialization, deserialization, and code generation.
    
    All EDSL classes should inherit from this class to ensure consistent behavior
    and capabilities across the framework.
    """

    def keys(self):
        """Get the key names in the object's dictionary representation.
        
        This method returns all the keys in the serialized form of the object,
        excluding metadata keys like version information.
        
        Returns:
            list: A list of key names
        """
        _keys = list(self.to_dict().keys())
        if "edsl_version" in _keys:
            _keys.remove("edsl_version")
        if "edsl_class_name" in _keys:
            _keys.remove("edsl_class_name")
        return _keys

    def values(self):
        """Get the values in the object's dictionary representation.
        
        Returns:
            set: A set containing all the values in the object
        """
        data = self.to_dict()
        keys = self.keys()
        return {data[key] for key in keys}

    @abstractmethod
    def example():
        """Create an example instance of this class.
        
        This method should be implemented by all subclasses to provide
        a convenient way to create example objects for testing and demonstration.
        
        Returns:
            An instance of the class with sample data
        """
        from edsl.base.exceptions import BaseNotImplementedError
        raise BaseNotImplementedError("This method is not implemented yet.")
    
    def json(self):
        """Get a formatted JSON representation of this object.
        
        Returns:
            DisplayJSON: A displayable JSON representation
        """
        return DisplayJSON(self.to_dict(add_edsl_version=False))

    def yaml(self):
        """Get a formatted YAML representation of this object.
        
        Returns:
            DisplayYAML: A displayable YAML representation
        """
        return DisplayYAML(self.to_dict(add_edsl_version=False))


    @abstractmethod
    def to_dict():
        """Serialize this object to a dictionary.
        
        This method must be implemented by all subclasses to provide a
        standard way to serialize objects to dictionaries. The dictionary
        should contain all the data needed to reconstruct the object.
        
        Returns:
            dict: A dictionary representation of the object
        """
        from edsl.base.exceptions import BaseNotImplementedError
        raise BaseNotImplementedError("This method is not implemented yet.")

    def to_json(self):
        """Serialize this object to a JSON string.
        
        Returns:
            str: A JSON string representation of the object
        """
        return json.dumps(self.to_dict())

    def store(self, d: dict, key_name: Optional[str] = None):
        """Store this object in a dictionary with an optional key.
        
        Args:
            d: The dictionary in which to store the object
            key_name: Optional key to use (defaults to the length of the dictionary)
            
        Returns:
            None
        """
        if key_name is None:
            index = len(d)
        else:
            index = key_name
        d[index] = self

    @abstractmethod
    def from_dict():
        """Create an instance from a dictionary.
        
        This class method must be implemented by all subclasses to provide a
        standard way to deserialize objects from dictionaries.
        
        Returns:
            An instance of the class populated with data from the dictionary
        """
        from edsl.base.exceptions import BaseNotImplementedError
        raise BaseNotImplementedError("This method is not implemented yet.")

    @abstractmethod
    def code():
        """Generate Python code that recreates this object.
        
        This method must be implemented by all subclasses to provide a way to
        generate executable Python code that can recreate the object.
        
        Returns:
            str: Python code that, when executed, creates an equivalent object
        """
        from edsl.base.exceptions import BaseNotImplementedError
        raise BaseNotImplementedError("This method is not implemented yet.")

    def show_methods(self, show_docstrings=True):
        """Display all public methods available on this object.
        
        This utility method helps explore the capabilities of an object by listing
        all its public methods and optionally their documentation.
        
        Args:
            show_docstrings: If True, print method names with docstrings;
                            if False, return the list of method names
                            
        Returns:
            None or list: If show_docstrings is True, prints methods and returns None.
                         If show_docstrings is False, returns a list of method names.
        """
        public_methods_with_docstrings = [
            (method, getattr(self, method).__doc__)
            for method in dir(self)
            if callable(getattr(self, method)) and not method.startswith("_")
        ]
        if show_docstrings:
            for method, documentation in public_methods_with_docstrings:
                print(f"{method}: {documentation}")
        else:
            return [x[0] for x in public_methods_with_docstrings]


class BaseDiffCollection(UserList):
    """A collection of difference objects that can be applied in sequence.
    
    This class represents a series of differences between objects that can be
    applied sequentially to transform one object into another through several steps.
    """
    
    def __init__(self, diffs=None):
        """Initialize a new BaseDiffCollection.
        
        Args:
            diffs: Optional list of BaseDiff objects to include in the collection
        """
        if diffs is None:
            diffs = []
        super().__init__(diffs)

    def apply(self, obj: Any):
        """Apply all diffs in the collection to an object in sequence.
        
        Args:
            obj: The object to transform
            
        Returns:
            The transformed object after applying all diffs
        """
        for diff in self:
            obj = diff.apply(obj)
        return obj

    def add_diff(self, diff) -> "BaseDiffCollection":
        """Add a new diff to the collection.
        
        Args:
            diff: The BaseDiff object to add
            
        Returns:
            BaseDiffCollection: self, for method chaining
        """
        self.append(diff)
        return self


class DummyObject:
    """A simple class that can be used to wrap a dictionary for diffing purposes.
    
    This utility class is used internally to compare dictionaries by adapting them
    to the same interface as EDSL objects.
    """
    
    def __init__(self, object_dict):
        """Initialize a new DummyObject.
        
        Args:
            object_dict: A dictionary to wrap
        """
        self.object_dict = object_dict

    def to_dict(self):
        """Get the wrapped dictionary.
        
        Returns:
            dict: The wrapped dictionary
        """
        return self.object_dict


class BaseDiff:
    """Represents the differences between two EDSL objects.
    
    This class computes and stores the differences between two objects in terms of:
    - Added keys/values (present in obj2 but not in obj1)
    - Removed keys/values (present in obj1 but not in obj2)
    - Modified keys/values (present in both but with different values)
    
    The differences can be displayed for inspection or applied to transform objects.
    """
    
    def __init__(
        self, obj1: Any, obj2: Any, added=None, removed=None, modified=None, level=0
    ):
        """Initialize a new BaseDiff between two objects.
        
        Args:
            obj1: The first object (considered the "from" object)
            obj2: The second object (considered the "to" object)
            added: Optional pre-computed dict of added keys/values
            removed: Optional pre-computed dict of removed keys/values
            modified: Optional pre-computed dict of modified keys/values
            level: Nesting level for diff display formatting
        """
        self.level = level

        self.obj1 = obj1
        self.obj2 = obj2

        if "sort" in inspect.signature(obj1.to_dict).parameters:
            self._dict1 = obj1.to_dict(sort=True)
            self._dict2 = obj2.to_dict(sort=True)
        else:
            self._dict1 = obj1.to_dict()
            self._dict2 = obj2.to_dict()
        self._obj_class = type(obj1)

        self.added = added
        self.removed = removed
        self.modified = modified

    def __bool__(self):
        """Determine if there are any differences between the objects.
        
        Returns:
            bool: True if there are differences, False if objects are identical
        """
        return bool(self.added or self.removed or self.modified)

    @property
    def added(self):
        """Get keys and values present in obj2 but not in obj1.
        
        Returns:
            dict: Keys and values that were added
        """
        if self._added is None:
            self._added = self._find_added()
        return self._added

    def __add__(self, other):
        """Apply this diff to another object.
        
        This overloads the + operator to allow applying diffs with a natural syntax.
        
        Args:
            other: The object to apply the diff to
            
        Returns:
            The transformed object
        """
        return self.apply(other)

    @added.setter
    def added(self, value):
        """Set the added keys/values.
        
        Args:
            value: Dict of added keys/values or None to compute automatically
        """
        self._added = value if value is not None else self._find_added()

    @property
    def removed(self):
        """Get keys and values present in obj1 but not in obj2.
        
        Returns:
            dict: Keys and values that were removed
        """
        if self._removed is None:
            self._removed = self._find_removed()
        return self._removed

    @removed.setter
    def removed(self, value):
        """Set the removed keys/values.
        
        Args:
            value: Dict of removed keys/values or None to compute automatically
        """
        self._removed = value if value is not None else self._find_removed()

    @property
    def modified(self):
        """Get keys present in both objects but with different values.
        
        Returns:
            dict: Keys and their old/new values that were modified
        """
        if self._modified is None:
            self._modified = self._find_modified()
        return self._modified

    @modified.setter
    def modified(self, value):
        """Set the modified keys/values.
        
        Args:
            value: Dict of modified keys/values or None to compute automatically
        """
        self._modified = value if value is not None else self._find_modified()

    def _find_added(self) -> Dict[Any, Any]:
        """Find keys that exist in obj2 but not in obj1.
        
        Returns:
            dict: Keys and values that were added
        """
        return {k: self._dict2[k] for k in self._dict2 if k not in self._dict1}

    def _find_removed(self) -> Dict[Any, Any]:
        """Find keys that exist in obj1 but not in obj2.
        
        Returns:
            dict: Keys and values that were removed
        """
        return {k: self._dict1[k] for k in self._dict1 if k not in self._dict2}

    def _find_modified(self) -> Dict[Any, Tuple[Any, Any, str]]:
        """Find keys that exist in both objects but have different values.
        
        The difference calculation is type-aware and handles strings, dictionaries,
        and lists specially to provide more detailed difference information.
        
        Returns:
            dict: Keys mapped to tuples of (old_value, new_value, diff_details)
        """
        modified = {}
        for k in self._dict1:
            if k in self._dict2 and self._dict1[k] != self._dict2[k]:
                if isinstance(self._dict1[k], str) and isinstance(self._dict2[k], str):
                    diff = self._diff_strings(self._dict1[k], self._dict2[k])
                    modified[k] = (self._dict1[k], self._dict2[k], diff)
                elif isinstance(self._dict1[k], dict) and isinstance(
                    self._dict2[k], dict
                ):
                    diff = self._diff_dicts(self._dict1[k], self._dict2[k])
                    modified[k] = (self._dict1[k], self._dict2[k], diff)
                elif isinstance(self._dict1[k], list) and isinstance(
                    self._dict2[k], list
                ):
                    d1 = dict(zip(range(len(self._dict1[k])), self._dict1[k]))
                    d2 = dict(zip(range(len(self._dict2[k])), self._dict2[k]))
                    diff = BaseDiff(
                        DummyObject(d1), DummyObject(d2), level=self.level + 1
                    )
                    modified[k] = (self._dict1[k], self._dict2[k], diff)
                else:
                    modified[k] = (self._dict1[k], self._dict2[k], "")
        return modified

    @staticmethod
    def is_json(string_that_could_be_json: str) -> bool:
        """Check if a string is valid JSON.
        
        Args:
            string_that_could_be_json: The string to check
            
        Returns:
            bool: True if the string is valid JSON, False otherwise
        """
        try:
            json.loads(string_that_could_be_json)
            return True
        except json.JSONDecodeError:
            return False

    def _diff_dicts(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> "BaseDiff":
        """Calculate the differences between two dictionaries.
        
        Args:
            dict1: The first dictionary
            dict2: The second dictionary
            
        Returns:
            BaseDiff: A difference object between the dictionaries
        """
        diff = BaseDiff(DummyObject(dict1), DummyObject(dict2), level=self.level + 1)
        return diff

    def _diff_strings(self, str1: str, str2: str) -> str:
        """Calculate the differences between two strings.
        
        If both strings are valid JSON, they are compared as dictionaries.
        Otherwise, they are compared line by line.
        
        Args:
            str1: The first string
            str2: The second string
            
        Returns:
            Union[BaseDiff, Iterable[str]]: A diff object or line-by-line differences
        """
        if self.is_json(str1) and self.is_json(str2):
            diff = self._diff_dicts(json.loads(str1), json.loads(str2))
            return diff
        diff = difflib.ndiff(str1.splitlines(), str2.splitlines())
        return diff

    def apply(self, obj: Any):
        """Apply this diff to transform an object.
        
        This method applies the computed differences to an object, adding new keys,
        removing deleted keys, and updating modified values.
        
        Args:
            obj: The object to transform
            
        Returns:
            The transformed object
        """
        new_obj_dict = obj.to_dict()
        for k, v in self.added.items():
            new_obj_dict[k] = v
        for k in self.removed.keys():
            del new_obj_dict[k]
        for k, (v1, v2, diff) in self.modified.items():
            new_obj_dict[k] = v2

        return obj.from_dict(new_obj_dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this difference object to a dictionary.
        
        Returns:
            dict: A dictionary representation of the differences
        """
        return {
            "added": self.added,
            "removed": self.removed,
            "modified": self.modified,
            "obj1": self._dict1,
            "obj2": self._dict2,
            "obj_class": self._obj_class.__name__,
            "level": self.level,
        }

    @classmethod
    def from_dict(cls, diff_dict: Dict[str, Any], obj1: Any, obj2: Any):
        """Create a BaseDiff from a dictionary representation.
        
        Args:
            diff_dict: Dictionary containing the difference data
            obj1: The first object
            obj2: The second object
            
        Returns:
            BaseDiff: A new difference object
        """
        return cls(
            obj1=obj1,
            obj2=obj2,
            added=diff_dict["added"],
            removed=diff_dict["removed"],
            modified=diff_dict["modified"],
            level=diff_dict["level"],
        )

    class Results(UserList):
        """Helper class for storing and formatting difference results.
        
        This class extends UserList to provide indentation and formatting
        capabilities when displaying differences.
        """
        
        def __init__(self, prepend=" ", level=0):
            """Initialize a new Results collection.
            
            Args:
                prepend: The string to use for indentation
                level: The nesting level
            """
            super().__init__()
            self.prepend = prepend
            self.level = level

        def append(self, item):
            """Add an item to the results with proper indentation.
            
            Args:
                item: The string to add
            """
            super().append(self.prepend * self.level + item)

    def __str__(self):
        """Generate a human-readable string representation of the differences.
        
        Returns:
            str: A formatted string showing the differences
        """
        prepend = " "
        result = self.Results(level=self.level, prepend="\t")
        if self.added:
            result.append("Added keys and values:")
            for k, v in self.added.items():
                result.append(prepend + f"  {k}: {v}")
        if self.removed:
            result.append("Removed keys and values:")
            for k, v in self.removed.items():
                result.append(f"  {k}: {v}")
        if self.modified:
            result.append("Modified keys and values:")
            for k, (v1, v2, diff) in self.modified.items():
                result.append(f"Key: {k}:")
                result.append(f"    Old value: {v1}")
                result.append(f"    New value: {v2}")
                if diff:
                    result.append("    Diff:")
                    try:
                        for line in diff:
                            result.append(f"      {line}")
                    except:
                        result.append(f"      {diff}")
        return "\n".join(result)

    def __repr__(self):
        """Generate a developer-friendly string representation.
        
        Returns:
            str: A representation that can be used to recreate the object
        """
        return (
            f"BaseDiff(obj1={self.obj1!r}, obj2={self.obj2!r}, added={self.added!r}, "
            f"removed={self.removed!r}, modified={self.modified!r})"
        )

    def add_diff(self, diff) -> "BaseDiffCollection":
        """Combine this diff with another into a collection.
        
        Args:
            diff: Another BaseDiff object
            
        Returns:
            BaseDiffCollection: A collection containing both diffs
        """
        from edsl.base import BaseDiffCollection
        return BaseDiffCollection([self, diff])


if __name__ == "__main__":
    import doctest 
    doctest.testmod()

    from edsl import Question

    q_ft = Question.example("free_text")
    q_mc = Question.example("multiple_choice")

    diff1 = q_ft - q_mc
    assert q_ft == q_mc + diff1
    assert q_ft == diff1.apply(q_mc)
    
    # ## Test chain of diffs
    q0 = Question.example("free_text")
    q1 = q0.copy()
    q1.question_text = "Why is Buzzard's Bay so named?"
    diff1 = q1 - q0
    q2 = q1.copy()
    q2.question_name = "buzzard_bay"
    diff2 = q2 - q1

    diff_chain = diff1.add_diff(diff2)

    new_q2 = diff_chain.apply(q0)
    assert new_q2 == q2

    new_q2 = diff_chain + q0
    assert new_q2 == q2