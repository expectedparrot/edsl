"""Base class for all classes in the package. It provides rich printing and persistence of objects."""

from abc import ABC, abstractmethod, ABCMeta
import gzip
import json
from typing import Any, Optional, Union
from uuid import UUID


class PersistenceMixin:
    """Mixin for saving and loading objects to and from files."""

    def duplicate(self, add_edsl_version=False):
        """Return a duplicate of the object."""
        return self.from_dict(self.to_dict(add_edsl_version=False))
    
    @classmethod
    def help(cls):
        """Return the help for the class."""
        print(cls.__doc__)

    def push(
        self,
        description: Optional[str] = None,
        alias: Optional[str] = None,
        visibility: Optional[str] = "unlisted",
        expected_parrot_url: Optional[str] = None,
    ):
        """Post the object to coop."""
        from edsl.coop import Coop

        c = Coop(url=expected_parrot_url)
        return c.create(self, description, alias, visibility)

    def to_yaml(self, add_edsl_version=False, filename: str = None) -> Union[str, None]:
        import yaml

        output = yaml.dump(self.to_dict(add_edsl_version=add_edsl_version))
        if not filename:
            return output

        with open(filename, "w") as f:
            f.write(output)

    @classmethod
    def from_yaml(cls, yaml_str: Optional[str] = None, filename: Optional[str] = None):
        if yaml_str is None and filename is not None:
            with open(filename, "r") as f:
                yaml_str = f.read()
                return cls.from_yaml(yaml_str=yaml_str)
        elif yaml_str and filename is None:
            import yaml

            d = yaml.load(yaml_str, Loader=yaml.FullLoader)
            return cls.from_dict(d)
        else:
            raise ValueError("Either yaml_str or filename must be provided.")

    def create_download_link(self):
        from tempfile import NamedTemporaryFile
        from edsl.scenarios.FileStore import FileStore

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
        from edsl.coop.utils import ObjectRegistry

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
        """Save the object to a file as zippped JSON.

        >>> obj.save("obj.json.gz")

        """
        if filename.endswith("json.gz"):
            import warnings

            filename = filename[:-8]
        if filename.endswith("json"):
            filename = filename[:-5]

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
    def get_registry(exclude_classes: Optional[list] = None):
        """Return the registry of subclasses."""
        if exclude_classes is None:
            exclude_classes = []
        return {
            k: v
            for k, v in dict(RegisterSubclassesMeta._registry).items()
            if k not in exclude_classes
        }


class DiffMethodsMixin:
    def __sub__(self, other):
        """Return the difference between two objects."""
        from edsl.BaseDiff import BaseDiff

        return BaseDiff(self, other)


def is_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    return True


class RepresentationMixin:
    def json(self):
        return json.loads(json.dumps(self.to_dict(add_edsl_version=False)))

    def to_dataset(self):
        from edsl.results.Dataset import Dataset

        return Dataset.from_edsl_object(self)

    def view(self):
        "Displays an interactive / perspective view of the object"
        return self.to_dataset().view()

    # def print(self, format="rich"):
    #     return self.to_dataset().table()

    def display_dict(self):
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
        from rich.table import Table
        from rich.console import Console

        table = Table(title=self.__class__.__name__)
        table.add_column("Key", style="bold")
        table.add_column("Value", style="bold")

        for key, value in self.display_dict().items():
            table.add_row(key, str(value))

        console = Console(record=True)
        console.print(table)

    # def help(obj):
    #     """
    #     Extract all public instance methods and their docstrings from a class instance.

    #     Args:
    #         obj: The instance to inspect

    #     Returns:
    #         dict: A dictionary where keys are method names and values are their docstrings
    #     """
    #     import inspect

    #     if inspect.isclass(obj):
    #         raise TypeError("Please provide a class instance, not a class")

    #     methods = {}

    #     # Get all members of the instance
    #     for name, member in inspect.getmembers(obj):
    #         # Skip private and special methods (those starting with underscore)
    #         if name.startswith("_"):
    #             continue

    #         # Check if it's specifically an instance method
    #         if inspect.ismethod(member):
    #             # Get the docstring (or empty string if none exists)
    #             docstring = inspect.getdoc(member) or ""
    #             methods[name] = docstring

    #     from edsl.results.Dataset import Dataset

    #     d = Dataset(
    #         [
    #             {"method": list(methods.keys())},
    #             {"documentation": list(methods.values())},
    #         ]
    #     )
    #     return d

    def _repr_html_(self):
        from .dataset.display import TableDisplay
        
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
            documenation = getattr(self, "__documentation__", "")
            summary_line = "<p>" + f"<a href='{documenation}'>{class_name}</a>" + "</p>"
            display_dict = self.display_dict()
            return (
                summary_line
                + TableDisplay.from_dictionary_wide(display_dict)._repr_html_()
            )

    def __str__(self):
        return self.__repr__()


class HashingMixin:
    def __hash__(self) -> int:
        """Return a hash of the question."""
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    def __eq__(self, other):
        """Return whether two objects are equal."""
        return hash(self) == hash(other)


class Base(
    RepresentationMixin,
    PersistenceMixin,
    DiffMethodsMixin,
    HashingMixin,
    ABC,
    metaclass=RegisterSubclassesMeta,
):
    """Base class for all classes in the package."""


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

    @abstractmethod
    def example():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    @abstractmethod
    def to_dict():
        """This method should be implemented by subclasses."""
        raise NotImplementedError("This method is not implemented yet.")

    def to_json(self):
        return json.dumps(self.to_dict())

    def store(self, d: dict, key_name: Optional[str] = None):
        if key_name is None:
            index = len(d)
        else:
            index = key_name
        d[index] = self

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
