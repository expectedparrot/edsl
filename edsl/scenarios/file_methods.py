from typing import Optional, Dict, Type
from abc import ABC, abstractmethod
import importlib.metadata
import importlib.util
from ..utilities import is_notebook


class FileMethods(ABC):
    _handlers: Dict[str, Type["FileMethods"]] = {}

    def __init__(self, path: Optional[str] = None):
        self.path = path

    def __init_subclass__(cls) -> None:
        """Register subclasses automatically when they're defined."""
        super().__init_subclass__()
        if hasattr(cls, "suffix"):
            FileMethods._handlers[cls.suffix] = cls

    @classmethod
    def get_handler(cls, suffix: str) -> Optional[Type["FileMethods"]]:
        """Get the appropriate handler class for a given suffix."""
        # Load plugins if they haven't been loaded yet
        if not cls._handlers:
            cls.load_plugins()
        return cls._handlers.get(suffix.lower())

    @classmethod
    def load_plugins(cls):
        """Load all file handler plugins including built-ins and external plugins."""

        from . import handlers  # noqa: F401 - import needed for handler registration

        # Then load any external plugins
        try:
            entries = importlib.metadata.entry_points(group="file_handlers")
        except TypeError:  # some Python 3.9 bullshit
            # entries = importlib.metadata.entry_points()
            entries = []

        for ep in entries:
            try:
                ep.load()
                # Registration happens automatically via __init_subclass__
            except Exception as e:
                print(f"Failed to load external handler {ep.name}: {e}")

    @classmethod
    def get_handler_for_path(cls, path: str) -> Optional[Type["FileMethods"]]:
        """Get the appropriate handler class for a file path."""
        suffix = path.split(".")[-1].lower() if "." in path else ""
        return cls.get_handler(suffix)

    @classmethod
    def create(cls, path: str) -> Optional["FileMethods"]:
        """Create an appropriate handler instance for the given path."""
        handler_class = cls.get_handler_for_path(path)
        if handler_class:
            return handler_class(path)
        return None

    @classmethod
    def supported_file_types(cls):
        if not cls._handlers:
            cls.load_plugins()
        return list(cls._handlers.keys())

    @abstractmethod
    def view_system(self):
        ...

    @abstractmethod
    def view_notebook(self):
        ...

    def view(self):
        if is_notebook():
            self.view_notebook()
        else:
            self.view_system()

    @abstractmethod
    def example(self):
        ...
