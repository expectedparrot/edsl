"""Base class for all classes in the package. It provides rich printing and persistence of objects."""

from abc import ABC, abstractmethod, ABCMeta
import gzip
import io
import json
from typing import Any, Optional, Union
from uuid import UUID
from IPython.display import display
from rich.console import Console


class RichPrintingMixin:
    """Mixin for rich printing and persistence of objects."""

    def _for_console(self):
        """Return a string representation of the object for console printing."""
        with io.StringIO() as buf:
            console = Console(file=buf, record=True)
            table = self.rich_print()
            console.print(table)
            return console.export_text()

    def __str__(self):
        """Return a string representation of the object for console printing."""
        return self._for_console()

    def print(self):
        """Print the object to the console."""
        from edsl.utilities.utilities import is_notebook

        if is_notebook():
            display(self.rich_print())
        else:
            from rich.console import Console

            console = Console()
            console.print(self.rich_print())


class PersistenceMixin:
    """Mixin for saving and loading objects to and from files."""

    def push(
        self,
        description: Optional[str] = None,
        visibility: Optional[str] = "unlisted",
    ):
        """Post the object to coop."""
        from edsl.coop import Coop

        c = Coop()
        return c.create(self, description, visibility)

    @classmethod
    def pull(cls, id_or_url: Union[str, UUID], exec_profile=None):
        """Pull the object from coop."""
        from edsl.coop import Coop

        if id_or_url.startswith("http"):
            uuid_value = id_or_url.split("/")[-1]
        else:
            uuid_value = id_or_url

        c = Coop()

        return c._get_base(cls, uuid_value, exec_profile=exec_profile)

    @classmethod
    def delete(cls, id_or_url: Union[str, UUID]):
        """Delete the object from coop."""
        from edsl.coop import Coop

        c = Coop()
        return c._delete_base(cls, id_or_url)

    @classmethod
    def patch(
        cls,
        id_or_url: Union[str, UUID],
        description: Optional[str] = None,
        value: Optional[Any] = None,
        visibility: Optional[str] = None,
    ):
        """
        Patch an uploaded objects attributes.
        - `description` changes the description of the object on Coop
        - `value` changes the value of the object on Coop. **has to be an EDSL object**
        - `visibility` changes the visibility of the object on Coop
        """
        from edsl.coop import Coop

        c = Coop()
        return c._patch_base(cls, id_or_url, description, value, visibility)

    @classmethod
    def search(cls, query):
        """Search for objects on coop."""
        from edsl.coop import Coop

        c = Coop()
        return c.search(cls, query)

    def save(self, filename, compress=True):
        """Save the object to a file as zippped JSON.

        >>> obj.save("obj.json.gz")

        """
        if filename.endswith("json.gz"):
            import warnings

            warnings.warn(
                "Do not apply the file extensions. The filename should not end with 'json.gz'."
            )
            filename = filename[:-7]
        if filename.endswith("json"):
            filename = filename[:-4]
            warnings.warn(
                "Do not apply the file extensions. The filename should not end with 'json'."
            )

        if compress:
            with gzip.open(filename + ".json.gz", "wb") as f:
                f.write(json.dumps(self.to_dict()).encode("utf-8"))
        else:
            with open(filename + ".json", "w") as f:
                f.write(json.dumps(self.to_dict()))

    @staticmethod
    def open_compressed_file(filename):
        with gzip.open(filename, "rb") as f:
            file_contents = f.read()
            file_contents_decoded = file_contents.decode("utf-8")
            d = json.loads(file_contents_decoded)
        return d

    @staticmethod
    def open_regular_file(filename):
        with open(filename, "r") as f:
            d = json.loads(f.read())
        return d

    @classmethod
    def load(cls, filename):
        """Load the object from a file.

        >>> obj = cls.load("obj.json.gz")

        """

        if filename.endswith("json.gz"):
            d = cls.open_compressed_file(filename)
        elif filename.endswith("json"):
            d = cls.open_regular_file(filename)
        else:
            try:
                d = cls.open_compressed_file(filename)
            except:
                d = cls.open_regular_file(filename)
            finally:
                raise ValueError("File must be a json or json.gz file")

        return cls.from_dict(d)


class RegisterSubclassesMeta(ABCMeta):
    """Metaclass for registering subclasses."""

    _registry = {}

    def __init__(cls, name, bases, nmspc):
        """Register the class in the registry upon creation."""
        super(RegisterSubclassesMeta, cls).__init__(name, bases, nmspc)
        if cls.__name__ != "Base":
            RegisterSubclassesMeta._registry[cls.__name__] = cls

    @staticmethod
    def get_registry():
        """Return the registry of subclasses."""
        return dict(RegisterSubclassesMeta._registry)


class DiffMethodsMixin:
    def __sub__(self, other):
        """Return the difference between two objects."""
        from edsl.BaseDiff import BaseDiff

        return BaseDiff(self, other)


class Base(
    RichPrintingMixin,
    PersistenceMixin,
    DiffMethodsMixin,
    ABC,
    metaclass=RegisterSubclassesMeta,
):
    """Base class for all classes in the package."""

    # def __getitem__(self, key):
    #     return getattr(self, key)

    # @abstractmethod
    # def _repr_html_(self) -> str:
    #     raise NotImplementedError("This method is not implemented yet.")

    # @abstractmethod
    # def _repr_(self) -> str:
    #     raise NotImplementedError("This method is not implemented yet.")

    def keys(self):
        """Return the keys of the object."""
        _keys = list(self.to_dict().keys())
        if "edsl_version" in _keys:
            _keys.remove("edsl_version")
        if "edsl_class_name" in _keys:
            _keys.remove("edsl_class_name")
        return _keys

    def values(self):
        """Return the values of the object."""
        data = self.to_dict()
        keys = self.keys()
        return {data[key] for key in keys}

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def __eq__(self, other):
        """Return whether two objects are equal."""
        import inspect

        if not isinstance(other, self.__class__):
            return False
        if "sort" in inspect.signature(self.to_dict).parameters:
            return self.to_dict(sort=True) == other.to_dict(sort=True)
        else:
            return self.to_dict() == other.to_dict()

    @abstractmethod
    def example():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    @abstractmethod
    def rich_print():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    @abstractmethod
    def to_dict():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    @abstractmethod
    def from_dict():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    @abstractmethod
    def code():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    def show_methods(self, show_docstrings=True):
        """Show the methods of the object."""
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
