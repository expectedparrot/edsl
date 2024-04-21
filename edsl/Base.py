"""Base class for all classes in the package. It provides rich printing and persistence of objects."""

from abc import ABC, abstractmethod, ABCMeta
import gzip
import io
import json
from IPython.display import display
from rich.console import Console
from edsl.utilities import is_notebook


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
        if is_notebook():
            display(self.rich_print())
        else:
            from rich.console import Console

            console = Console()
            console.print(self.rich_print())


class PersistenceMixin:
    """Mixin for saving and loading objects to and from files."""

    def push(self, public=False):
        """Post the object to coop."""
        from edsl.coop import Coop

        c = Coop()
        _ = c.create(self, public)
        print(_)

    @classmethod
    def pull(cls, id):
        """Pull the object from coop."""
        from edsl.coop import Coop

        c = Coop()
        return c._get_base(cls, id)

    @classmethod
    def search(cls, query):
        """Search for objects on coop."""
        from edsl.coop import Coop

        c = Coop()
        return c.search(cls, query)

    def save(self, filename):
        """Save the object to a file as zippped JSON.

        >>> obj.save("obj.json.gz")

        """
        with gzip.open(filename, "wb") as f:
            f.write(json.dumps(self.to_dict()).encode("utf-8"))

    @classmethod
    def load(cls, filename):
        """Load the object from a file.

        >>> obj = cls.load("obj.json.gz")

        """
        with gzip.open(filename, "rb") as f:
            file_contents = f.read()
            file_contents_decoded = file_contents.decode("utf-8")
            d = json.loads(file_contents_decoded)
            # d = json.loads(f.read().decode("utf-8"))
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


class Base(RichPrintingMixin, PersistenceMixin, ABC, metaclass=RegisterSubclassesMeta):
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
        return self.to_dict().keys()

    def values(self):
        """Return the values of the object."""
        return self.to_dict().values()

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def html(self):
        html_string = self._repr_html_()
        import tempfile
        import webbrowser

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as f:
            # print("Writing HTML to", f.name)
            f.write(html_string)
            webbrowser.open(f.name)

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
