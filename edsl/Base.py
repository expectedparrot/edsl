"""Base class for all classes in the package. It provides rich printing and persistence of objects."""

from abc import ABC, abstractmethod, ABCMeta
import gzip
import io
import json
from typing import Any, Optional, Union
from uuid import UUID

# from edsl.utilities.MethodSuggesterMixin import MethodSuggesterMixin

from edsl.utilities.utilities import is_notebook


class RichPrintingMixin:
    pass

    # def print(self):
    #     print(self)


#     """Mixin for rich printing and persistence of objects."""

#     def _for_console(self):
#         """Return a string representation of the object for console printing."""
#         from rich.console import Console

#         with io.StringIO() as buf:
#             console = Console(file=buf, record=True)
#             table = self.rich_print()
#             console.print(table)
#             return console.export_text()

#     def __str__(self):
#         """Return a string representation of the object for console printing."""
#         # return self._for_console()
#         return self.__repr__()

#     def print(self):
#         """Print the object to the console."""
#         from edsl.utilities.utilities import is_notebook

#         if is_notebook():
#             from IPython.display import display

#             display(self.rich_print())
#         else:
#             from rich.console import Console

#             console = Console()
#             console.print(self.rich_print())


class PersistenceMixin:
    """Mixin for saving and loading objects to and from files."""

    def push(
        self,
        description: Optional[str] = None,
        visibility: Optional[str] = "unlisted",
        expected_parrot_url: Optional[str] = None,
    ):
        """Post the object to coop."""
        from edsl.coop import Coop

        c = Coop(url=expected_parrot_url)
        return c.create(self, description, visibility)

    @classmethod
    def pull(
        cls,
        uuid: Optional[Union[str, UUID]] = None,
        url: Optional[str] = None,
        expected_parrot_url: Optional[str] = None,
    ):
        """Pull the object from coop."""
        from edsl.coop import Coop
        from edsl.coop.utils import ObjectRegistry

        object_type = ObjectRegistry.get_object_type_by_edsl_class(cls)
        coop = Coop(url=expected_parrot_url)
        return coop.get(uuid, url, object_type)

    @classmethod
    def delete(cls, uuid: Optional[Union[str, UUID]] = None, url: Optional[str] = None):
        """Delete the object from coop."""
        from edsl.coop import Coop

        coop = Coop()
        return coop.delete(uuid, url)

    @classmethod
    def patch(
        cls,
        uuid: Optional[Union[str, UUID]] = None,
        url: Optional[str] = None,
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

        coop = Coop()
        return coop.patch(uuid, url, description, value, visibility)

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

            # warnings.warn(
            #    "Do not apply the file extensions. The filename should not end with 'json.gz'."
            # )
            filename = filename[:-7]
        if filename.endswith("json"):
            filename = filename[:-4]
            # warnings.warn(
            #    "Do not apply the file extensions. The filename should not end with 'json'."
            # )

        if compress:
            full_file_name = filename + ".json.gz"
            with gzip.open(full_file_name, "wb") as f:
                f.write(json.dumps(self.to_dict()).encode("utf-8"))
        else:
            full_file_name = filename + ".json"
            with open(filename + ".json", "w") as f:
                f.write(json.dumps(self.to_dict()))

        print("Saved to", full_file_name)

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
                d = cls.open_compressed_file(filename + ".json.gz")
            except:
                d = cls.open_regular_file(filename + ".json")
            # finally:
            #    raise ValueError("File must be a json or json.gz file")

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
    # RichPrintingMixin,
    PersistenceMixin,
    DiffMethodsMixin,
    ABC,
    metaclass=RegisterSubclassesMeta,
):
    """Base class for all classes in the package."""

    def json(self):
        return json.loads(json.dumps(self.to_dict(add_edsl_version=False)))

    def print(self, **kwargs):
        if "format" in kwargs:
            if kwargs["format"] not in ["html", "markdown", "rich", "latex"]:
                raise ValueError(f"Format '{kwargs['format']}' not supported.")

        if hasattr(self, "table"):
            return self.table()
        else:
            return self

    def __str__(self):
        return self.__repr__()

    def summary(self, format="table"):
        from edsl import Scenario

        d = self._summary()
        if format == "table":
            return Scenario(d).table()
        if format == "dict":
            return d
        if format == "json":
            return Scenario(d).json()
        if format == "yaml":
            return Scenario(d).yaml()
        if format == "html":
            return Scenario(d).table(tablefmt="html")

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

    # def html(self):
    #     html_string = self._repr_html_()
    #     import tempfile
    #     import webbrowser

    #     with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as f:
    #         # print("Writing HTML to", f.name)
    #         f.write(html_string)
    #         webbrowser.open(f.name)

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

    def to_json(self):
        return json.dumps(self.to_dict())

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
